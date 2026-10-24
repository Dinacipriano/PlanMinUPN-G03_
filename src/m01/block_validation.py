"""Independent controls for the preliminary block model (M01B, P5).

The controls re-read the generated CSV files and re-derive every rule from the
raw columns; they do not call the generation code. A PASS here shows internal
consistency only. It does not show that the geology is right: that needs the
mining inspection (sections, contacts, surface) done by the engineer.

Statuses: PASS (conforming), WARNING (review and document), FAIL (blocks closure).
"""

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import floor
from pathlib import Path

from src.m01.block_model import DEFAULT_GRID, GridSpec
from src.m01.domain_assignment import DOMAIN_BY_LITH, SearchParams

_ROOT = Path(__file__).resolve().parents[2]
_PROCESSED = _ROOT / "data" / "processed" / "m01b"
DEFAULT_TOPO_PATH = _PROCESSED / "blocks_topo.csv"
DEFAULT_DOMAIN_PATH = _PROCESSED / "blocks_domains.csv"
DEFAULT_COMPOSITES_PATH = _PROCESSED / "composites.csv"
DEFAULT_REPORT_PATH = _ROOT / "outputs" / "tables" / "IMP002_block_validation_M01B.md"

PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"
TOL_M = 1e-3  # CSV values are written with three decimals

VALID_TOPO_STATES = {"ROCK", "PARTIAL", "AIR", "OUTSIDE_TOPO_COVERAGE"}
ASSIGNED = {"ASSIGNED_SUPPORTED", "ASSIGNED_EXTRAPOLATED"}
Row = dict[str, str]


@dataclass(frozen=True)
class Control:
    control_id: str
    area: str
    description: str
    status: str
    observed: str
    expected: str


@dataclass(frozen=True)
class ValidationSummary:
    controls: list[Control]

    @property
    def overall(self) -> str:
        statuses = {control.status for control in self.controls}
        if FAIL in statuses:
            return FAIL
        return WARNING if WARNING in statuses else PASS

    @property
    def counts(self) -> dict[str, int]:
        counter = Counter(control.status for control in self.controls)
        return {status: counter.get(status, 0) for status in (PASS, WARNING, FAIL)}


def read_rows(path: str | Path) -> list[Row]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_block_model(
    topo_rows: list[Row],
    domain_rows: list[Row],
    composite_rows: list[Row],
    grid: GridSpec = DEFAULT_GRID,
    search: SearchParams | None = None,
    share_tolerance_pp: float = 10.0,
) -> ValidationSummary:
    """Run every control. ``share_tolerance_pp`` is a review trigger, not a criterion."""
    search = search or SearchParams()
    controls: list[Control] = []

    def add(cid, area, description, ok_value, observed, expected, warn=False):
        status = PASS if ok_value else (WARNING if warn else FAIL)
        controls.append(Control(cid, area, description, status, str(observed), expected))

    # ---------------- geometry
    ids = [int(r["block_id"]) for r in topo_rows]
    duplicates = len(ids) - len(set(ids))
    add("GEO-01", "geometría", "block_id únicos", duplicates == 0, f"{duplicates} duplicados", "0")
    add(
        "GEO-02",
        "geometría",
        "número de bloques = nx*ny*nz",
        len(ids) == grid.n_blocks,
        f"{len(ids)} de {grid.n_blocks}",
        f"{grid.n_blocks}",
    )
    bad_size = sum(
        1
        for r in topo_rows
        if min(float(r["dx"]), float(r["dy"]), float(r["dz"])) <= 0
        or abs(float(r["volume_m3"]) - float(r["dx"]) * float(r["dy"]) * float(r["dz"])) > TOL_M
    )
    add("GEO-03", "geometría", "dimensiones y volumen positivos y coherentes", bad_size == 0, f"{bad_size} bloques", "0")
    bad_center = 0
    for r in topo_rows:
        ix, iy, iz = int(r["ix"]), int(r["iy"]), int(r["iz"])
        ok = (
            abs(float(r["xc"]) - (grid.x0 + (ix + 0.5) * grid.dx)) <= TOL_M
            and abs(float(r["yc"]) - (grid.y0 + (iy + 0.5) * grid.dy)) <= TOL_M
            and abs(float(r["zc"]) - (grid.z0 + (iz + 0.5) * grid.dz)) <= TOL_M
            and int(r["block_id"]) == grid.block_id(ix, iy, iz)
            and 0 <= ix < grid.nx
            and 0 <= iy < grid.ny
            and 0 <= iz < grid.nz
        )
        bad_center += 0 if ok else 1
    add("GEO-04", "geometría", "centro e id coinciden con el índice (ix, iy, iz)", bad_center == 0, f"{bad_center} bloques", "0")

    # ---------------- topography
    states = Counter(r["topo_state"] for r in topo_rows)
    invalid = sum(count for state, count in states.items() if state not in VALID_TOPO_STATES)
    add("TOP-01", "topografía", "estados topográficos válidos", invalid == 0, f"{invalid} inválidos", "0")
    inconsistent = 0
    for r in topo_rows:
        state = r["topo_state"]
        if state == "OUTSIDE_TOPO_COVERAGE":
            inconsistent += 1 if r["ztopo_min"] or r["ztopo_max"] else 0
            continue
        if not r["ztopo_min"] or not r["ztopo_max"]:
            inconsistent += 1
            continue
        low, high = float(r["ztopo_min"]), float(r["ztopo_max"])
        base = float(r["zc"]) - float(r["dz"]) / 2
        top = float(r["zc"]) + float(r["dz"]) / 2
        if state == "ROCK":
            ok = top <= low + TOL_M
        elif state == "AIR":
            ok = base >= high - TOL_M
        elif state == "PARTIAL":
            ok = top > low + TOL_M and base < high - TOL_M
        else:
            ok = False
        inconsistent += 0 if ok else 1
    add("TOP-02", "topografía", "estado coherente con las cotas de superficie del bloque", inconsistent == 0, f"{inconsistent} bloques", "0")

    topo_state_by_id = {int(r["block_id"]): r["topo_state"] for r in topo_rows}
    composites = _composite_cells(composite_rows, grid)
    outside_grid = sum(1 for c in composites if c["cell"] is None)
    add("SUP-01", "soporte", "todos los composites caen dentro del grid", outside_grid == 0, f"{outside_grid} fuera", "0")
    no_xyz = sum(1 for c in composites if c["xyz"] is False)
    add("SUP-02", "soporte", "todos los composites tienen XYZ", no_xyz == 0, f"{no_xyz} sin XYZ", "0")
    in_air = sum(1 for c in composites if c["cell"] is not None and topo_state_by_id.get(c["cell"]) == "AIR")
    add("TOP-03", "topografía", "ningún composite dentro de un bloque AIR", in_air == 0, f"{in_air} composites", "0")
    n_outside = states.get("OUTSIDE_TOPO_COVERAGE", 0)
    add("TOP-04", "topografía", "bloques fuera de cobertura topográfica", n_outside == 0, f"{n_outside} bloques", "0 (si hay, documentar)", warn=True)
    n_partial = states.get("PARTIAL", 0)
    add(
        "TOP-05",
        "topografía",
        "bloques PARTIAL (volumen nominal distinto del volumen de roca)",
        n_partial == 0,
        f"{n_partial} bloques ({100 * n_partial / max(len(topo_rows), 1):.1f} %)",
        "0 (si hay, documentar como limitación)",
        warn=True,
    )

    # ---------------- domains
    ids_topo, ids_domain = set(ids), {int(r["block_id"]) for r in domain_rows}
    add("REC-01", "reconciliación", "mismos block_id en blocks_topo y blocks_domains", ids_topo == ids_domain, f"{len(ids_topo ^ ids_domain)} diferencias", "0")
    mismatch_state = sum(1 for r in domain_rows if topo_state_by_id.get(int(r["block_id"])) != r["topo_state"])
    add("REC-02", "reconciliación", "topo_state igual en ambos archivos", mismatch_state == 0, f"{mismatch_state} bloques", "0")

    bad_rule = 0
    bad_domain = 0
    bad_distance = 0
    for r in domain_rows:
        status, topo, domain = r["assign_status"], r["topo_state"], r["domain_id"]
        if topo == "AIR":
            ok = status == "NOT_ROCK_AIR" and domain == ""
        elif topo == "OUTSIDE_TOPO_COVERAGE":
            ok = status == "UNKNOWN_TOPO" and domain == ""
        else:
            ok = (status in ASSIGNED and domain != "") or (status == "UNKNOWN_NO_SUPPORT" and domain == "")
        bad_rule += 0 if ok else 1
        if domain and domain not in set(DOMAIN_BY_LITH.values()):
            bad_domain += 1
        dist = r["nearest_dist_m"]
        if status == "ASSIGNED_SUPPORTED":
            good = bool(dist) and float(dist) <= search.radius_supported_m + TOL_M
        elif status == "ASSIGNED_EXTRAPOLATED":
            good = bool(dist) and search.radius_supported_m - TOL_M < float(dist) <= search.radius_extrapolated_m + TOL_M
        else:
            good = dist == ""
        bad_distance += 0 if good else 1
    add("DOM-01", "dominios", "dominio solo en bloques de roca con soporte; AIR/UNKNOWN sin dominio", bad_rule == 0, f"{bad_rule} bloques", "0")
    add("DOM-02", "dominios", "dominios dentro del conjunto aprobado (DECISION-02)", bad_domain == 0, f"{bad_domain} bloques", "0")
    add("DOM-03", "dominios", "estado de asignación coherente con la distancia y los radios (DECISION-05)", bad_distance == 0, f"{bad_distance} bloques", "0")

    # composite vs block domain
    domain_by_id = {int(r["block_id"]): r["domain_id"] for r in domain_rows}
    inside: dict[int, list[str]] = defaultdict(list)
    for c in composites:
        if c["cell"] is not None and c["domain"]:
            inside[c["cell"]].append(c["domain"])
    disagree = 0
    for cell, found in inside.items():
        majority = Counter(found).most_common(1)[0][0]
        disagree += 0 if domain_by_id.get(cell, "") == majority else 1
    add(
        "DOM-04",
        "dominios",
        "bloques con composites: dominio asignado = dominio mayoritario interno",
        disagree == 0,
        f"{disagree} de {len(inside)} bloques difieren",
        "0 (diferencias esperables junto a contactos)",
        warn=True,
    )

    # share of domains vs metres
    metres: dict[str, float] = defaultdict(float)
    for c in composites:
        if c["domain"]:
            metres[c["domain"]] += c["length"]
    assigned = Counter(r["domain_id"] for r in domain_rows if r["domain_id"])
    total_m, total_b = sum(metres.values()), sum(assigned.values())
    diffs = {}
    if total_m and total_b:
        for domain in sorted(set(metres) | set(assigned)):
            diffs[domain] = 100 * assigned.get(domain, 0) / total_b - 100 * metres.get(domain, 0) / total_m
    worst = max((abs(v) for v in diffs.values()), default=0.0)
    add(
        "DOM-05",
        "dominios",
        "proporción de bloques por dominio frente a proporción de metros compuestados",
        worst <= share_tolerance_pp,
        ", ".join(f"{d} {v:+.1f} pp" for d, v in diffs.items()) or "sin datos",
        f"diferencia máxima <= {share_tolerance_pp:g} pp (disparador de revisión)",
        warn=True,
    )

    # ---------------- support and uncertainty
    rock_rows = [r for r in domain_rows if r["topo_state"] in ("ROCK", "PARTIAL")]
    n_rock = max(len(rock_rows), 1)
    unknown = sum(1 for r in rock_rows if r["assign_status"] == "UNKNOWN_NO_SUPPORT")
    extrapolated = sum(1 for r in rock_rows if r["assign_status"] == "ASSIGNED_EXTRAPOLATED")
    mixed = sum(1 for r in domain_rows if r["mixed_flag"] == "1")
    add("UNC-01", "incertidumbre", "bloques de roca sin soporte (UNKNOWN)", unknown == 0, f"{unknown} ({100 * unknown / n_rock:.1f} % de la roca)", "0 (si hay, documentar)", warn=True)
    add("UNC-02", "incertidumbre", "bloques de roca asignados por extrapolación", extrapolated == 0, f"{extrapolated} ({100 * extrapolated / n_rock:.1f} % de la roca)", "0 (si hay, documentar)", warn=True)
    add("UNC-03", "incertidumbre", "bloques con más de un dominio dentro del primer radio (contactos no modelados)", mixed == 0, f"{mixed} bloques", "0 (si hay, revisar en secciones)", warn=True)

    return ValidationSummary(controls=controls)


def domain_section(
    domain_rows: list[Row], axis: str, index: int, grid: GridSpec = DEFAULT_GRID
) -> str:
    """Text section. axis 'y': west-east section at iy=index; axis 'x': south-north at ix=index.

    Symbols: '.' air, '?' unknown, uppercase D/P/B/R = supported domain,
    lowercase d/p/b/r = extrapolated domain, '-' outside topographic coverage.
    """
    if axis not in ("x", "y"):
        raise ValueError("axis must be 'x' or 'y'")
    width = grid.nx if axis == "y" else grid.ny
    cells: dict[tuple[int, int], str] = {}
    for r in domain_rows:
        ix, iy, iz = int(r["ix"]), int(r["iy"]), int(r["iz"])
        if (axis == "y" and iy != index) or (axis == "x" and ix != index):
            continue
        along = ix if axis == "y" else iy
        cells[(along, iz)] = _symbol(r)
    lines = []
    for iz in range(grid.nz - 1, -1, -1):
        z_base = grid.z0 + iz * grid.dz
        row = "".join(cells.get((along, iz), " ") for along in range(width))
        lines.append(f"{z_base:7.0f} | {row}")
    return "\n".join(lines)


def busiest_indices(composite_rows: list[Row], grid: GridSpec = DEFAULT_GRID) -> tuple[int, int]:
    """Return (iy, ix) with the most composites, to choose where to cut sections."""
    by_iy: Counter[int] = Counter()
    by_ix: Counter[int] = Counter()
    for c in _composite_cells(composite_rows, grid):
        if c["index"] is not None:
            by_ix[c["index"][0]] += 1
            by_iy[c["index"][1]] += 1
    return (
        by_iy.most_common(1)[0][0] if by_iy else 0,
        by_ix.most_common(1)[0][0] if by_ix else 0,
    )


def render_report(
    summary: ValidationSummary,
    sections: list[tuple[str, str]],
) -> str:
    lines = [
        "# IMP-002 · Validación del modelo de bloques preliminar (M01B)",
        "",
        f"Resultado global: **{summary.overall}** "
        f"(PASS {summary.counts[PASS]}, WARNING {summary.counts[WARNING]}, FAIL {summary.counts[FAIL]}).",
        "",
        "Los controles recalculan las reglas desde los CSV generados. Un PASS indica consistencia "
        "interna; no demuestra que la geología sea correcta.",
        "",
        "| Control | Área | Descripción | Estado | Observado | Esperado |",
        "|---|---|---|---|---|---|",
    ]
    for c in summary.controls:
        lines.append(
            f"| {c.control_id} | {c.area} | {c.description} | {c.status} | {c.observed} | {c.expected} |"
        )
    lines += ["", "## Secciones para inspección minera", ""]
    lines.append(
        "Símbolos: `.` aire, `?` UNKNOWN, `D P B R` dominio soportado, `d p b r` dominio extrapolado, "
        "`-` fuera de cobertura topográfica. Cota = base de la capa (m)."
    )
    for title, text in sections:
        lines += ["", f"### {title}", "", "```text", text, "```"]
    return "\n".join(lines) + "\n"


def run_m01b_block_validation(
    topo_path: str | Path = DEFAULT_TOPO_PATH,
    domain_path: str | Path = DEFAULT_DOMAIN_PATH,
    composites_path: str | Path = DEFAULT_COMPOSITES_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> ValidationSummary:
    topo_rows = read_rows(topo_path)
    domain_rows = read_rows(domain_path)
    composite_rows = read_rows(composites_path)
    summary = validate_block_model(topo_rows, domain_rows, composite_rows)
    iy, ix = busiest_indices(composite_rows)
    sections = [
        (f"Sección oeste-este en iy={iy}", domain_section(domain_rows, "y", iy)),
        (f"Sección sur-norte en ix={ix}", domain_section(domain_rows, "x", ix, DEFAULT_GRID)),
    ]
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_report(summary, sections), encoding="utf-8")
    return summary


def _symbol(row: Row) -> str:
    topo, status, domain = row["topo_state"], row["assign_status"], row["domain_id"]
    if topo == "AIR":
        return "."
    if topo == "OUTSIDE_TOPO_COVERAGE":
        return "-"
    if status == "UNKNOWN_NO_SUPPORT" or not domain:
        return "?"
    letter = domain[0]
    return letter if status == "ASSIGNED_SUPPORTED" else letter.lower()


def _composite_cells(composite_rows: list[Row], grid: GridSpec) -> list[dict]:
    cells = []
    for r in composite_rows:
        try:
            x, y, z = float(r["x"]), float(r["y"]), float(r["z"])
        except (KeyError, TypeError, ValueError):
            cells.append({"cell": None, "index": None, "xyz": False, "domain": "", "length": 0.0})
            continue
        ix = floor((x - grid.x0) / grid.dx)
        iy = floor((y - grid.y0) / grid.dy)
        iz = floor((z - grid.z0) / grid.dz)
        inside = 0 <= ix < grid.nx and 0 <= iy < grid.ny and 0 <= iz < grid.nz
        cells.append(
            {
                "cell": grid.block_id(ix, iy, iz) if inside else None,
                "index": (ix, iy, iz) if inside else None,
                "xyz": True,
                "domain": DOMAIN_BY_LITH.get((r.get("lith_code") or "").strip(), ""),
                "length": float(r.get("length_m") or 0.0),
            }
        )
    return cells


if __name__ == "__main__":
    _summary = run_m01b_block_validation()
    for _c in _summary.controls:
        print(f"{_c.status:7} {_c.control_id}  {_c.description}: {_c.observed}")
    print(f"OVERALL {_summary.overall}  {_summary.counts}")
