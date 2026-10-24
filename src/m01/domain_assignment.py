"""Preliminary geological domain assignment to blocks (M01B).

Each rock block receives the domain of the nearest composite, in two search
passes. Beyond the second radius the block stays UNKNOWN: no domain is
invented and nothing is estimated (no grade, density or tonnage here).
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from math import floor, isfinite, sqrt
from pathlib import Path

from src.m01.block_model import (
    STATE_AIR,
    STATE_OUTSIDE,
    Block,
)
from src.m01.validator import ValidationFinding

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSITES_PATH = _ROOT / "data" / "processed" / "m01b" / "composites.csv"
DEFAULT_BLOCKS_PATH = _ROOT / "data" / "processed" / "m01b" / "blocks_topo.csv"
DEFAULT_OUTPUT_PATH = _ROOT / "data" / "processed" / "m01b" / "blocks_domains.csv"

# DECISION-02 (IMP-002): one domain per lithology code. AIR is not a domain.
DOMAIN_BY_LITH = {"DIO": "DIO", "POR": "POR", "BRX": "BRX", "REG": "REG"}

STATUS_SUPPORTED = "ASSIGNED_SUPPORTED"
STATUS_EXTRAPOLATED = "ASSIGNED_EXTRAPOLATED"
STATUS_UNKNOWN = "UNKNOWN_NO_SUPPORT"
STATUS_NOT_ROCK = "NOT_ROCK_AIR"
STATUS_UNKNOWN_TOPO = "UNKNOWN_TOPO"
STATUSES = (
    STATUS_SUPPORTED,
    STATUS_EXTRAPOLATED,
    STATUS_UNKNOWN,
    STATUS_NOT_ROCK,
    STATUS_UNKNOWN_TOPO,
)
CSV_COLUMNS = (
    "block_id",
    "ix",
    "iy",
    "iz",
    "xc",
    "yc",
    "zc",
    "topo_state",
    "domain_id",
    "assign_status",
    "nearest_dist_m",
    "nearest_hole_id",
    "n_holes_r1",
    "n_domains_r1",
    "mixed_flag",
)


@dataclass(frozen=True)
class SearchParams:
    """DECISION-05 (IMP-002): two isotropic passes, radii in metres."""

    radius_supported_m: float = 50.0
    radius_extrapolated_m: float = 100.0

    def __post_init__(self) -> None:
        if not 0 < self.radius_supported_m <= self.radius_extrapolated_m:
            raise ValueError("radii must satisfy 0 < supported <= extrapolated")


@dataclass(frozen=True)
class SupportPoint:
    """One composite midpoint used as geological observation."""

    hole_id: str
    x: float
    y: float
    z: float
    domain_id: str


@dataclass(frozen=True)
class BlockDomain:
    block_id: int
    ix: int
    iy: int
    iz: int
    xc: float
    yc: float
    zc: float
    topo_state: str
    domain_id: str | None
    assign_status: str
    nearest_dist_m: float | None
    nearest_hole_id: str | None
    n_holes_r1: int
    n_domains_r1: int

    @property
    def mixed_flag(self) -> bool:
        """More than one domain among the composites within the first radius."""
        return self.n_domains_r1 > 1


@dataclass(frozen=True)
class AssignmentResult:
    params: SearchParams
    blocks: list[BlockDomain]
    n_support_points: int
    findings: list[ValidationFinding]


def read_support_points(
    path: str | Path = DEFAULT_COMPOSITES_PATH,
) -> tuple[list[SupportPoint], list[ValidationFinding]]:
    """Read composites.csv. Composites without XYZ or without a domain are excluded."""
    points: list[SupportPoint] = []
    findings: list[ValidationFinding] = []
    excluded: dict[str, int] = defaultdict(int)
    source = Path(path)
    if not source.is_file():
        findings.append(
            _finding(
                "ASSIGN-001",
                "ERROR",
                "composites",
                "file",
                str(source),
                "composites file must exist; none is invented",
            )
        )
        return points, findings
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            coords = [_to_float(row.get(name)) for name in ("x", "y", "z")]
            code = (row.get("lith_code") or "").strip()
            if any(value is None for value in coords):
                excluded["no XYZ"] += 1
                continue
            domain = DOMAIN_BY_LITH.get(code)
            if domain is None:
                excluded[f"lith_code {code or '<empty>'}"] += 1
                continue
            points.append(
                SupportPoint(
                    hole_id=row.get("hole_id", ""),
                    x=coords[0],  # type: ignore[arg-type]
                    y=coords[1],  # type: ignore[arg-type]
                    z=coords[2],  # type: ignore[arg-type]
                    domain_id=domain,
                )
            )
    for reason, count in sorted(excluded.items()):
        findings.append(
            _finding(
                "ASSIGN-002",
                "WARNING",
                "composites",
                "lith_code",
                f"{count} composites excluded ({reason})",
                "only composites with XYZ and a mapped domain are used",
            )
        )
    return points, findings


def read_blocks(path: str | Path = DEFAULT_BLOCKS_PATH) -> list[Block]:
    """Read blocks_topo.csv back into Block objects."""
    blocks: list[Block] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            blocks.append(
                Block(
                    block_id=int(row["block_id"]),
                    ix=int(row["ix"]),
                    iy=int(row["iy"]),
                    iz=int(row["iz"]),
                    xc=float(row["xc"]),
                    yc=float(row["yc"]),
                    zc=float(row["zc"]),
                    dx=float(row["dx"]),
                    dy=float(row["dy"]),
                    dz=float(row["dz"]),
                    ztopo_center=_to_float(row["ztopo_center"]),
                    ztopo_min=_to_float(row["ztopo_min"]),
                    ztopo_max=_to_float(row["ztopo_max"]),
                    topo_state=row["topo_state"],
                )
            )
    return blocks


def assign_domains(
    blocks: list[Block],
    points: list[SupportPoint],
    params: SearchParams | None = None,
) -> AssignmentResult:
    """Assign the nearest composite's domain within two radii; else UNKNOWN."""
    params = params or SearchParams()
    r1 = params.radius_supported_m
    r2 = params.radius_extrapolated_m
    cell = r2
    buckets: dict[tuple[int, int, int], list[SupportPoint]] = defaultdict(list)
    for point in points:
        buckets[(floor(point.x / cell), floor(point.y / cell), floor(point.z / cell))].append(
            point
        )

    assigned: list[BlockDomain] = []
    for block in blocks:
        if block.topo_state == STATE_AIR:
            assigned.append(_empty(block, STATUS_NOT_ROCK))
            continue
        if block.topo_state == STATE_OUTSIDE:
            assigned.append(_empty(block, STATUS_UNKNOWN_TOPO))
            continue
        bx = floor(block.xc / cell)
        by = floor(block.yc / cell)
        bz = floor(block.zc / cell)
        nearest: tuple[float, str, str] | None = None
        holes_r1: set[str] = set()
        domains_r1: set[str] = set()
        for i in (bx - 1, bx, bx + 1):
            for j in (by - 1, by, by + 1):
                for k in (bz - 1, bz, bz + 1):
                    for point in buckets.get((i, j, k), ()):
                        dist = sqrt(
                            (point.x - block.xc) ** 2
                            + (point.y - block.yc) ** 2
                            + (point.z - block.zc) ** 2
                        )
                        if dist > r2:
                            continue
                        key = (dist, point.hole_id, point.domain_id)
                        if nearest is None or key < nearest:
                            nearest = key
                        if dist <= r1:
                            holes_r1.add(point.hole_id)
                            domains_r1.add(point.domain_id)
        if nearest is None:
            assigned.append(_empty(block, STATUS_UNKNOWN))
            continue
        status = STATUS_SUPPORTED if nearest[0] <= r1 else STATUS_EXTRAPOLATED
        assigned.append(
            BlockDomain(
                block_id=block.block_id,
                ix=block.ix,
                iy=block.iy,
                iz=block.iz,
                xc=block.xc,
                yc=block.yc,
                zc=block.zc,
                topo_state=block.topo_state,
                domain_id=nearest[2],
                assign_status=status,
                nearest_dist_m=nearest[0],
                nearest_hole_id=nearest[1],
                n_holes_r1=len(holes_r1),
                n_domains_r1=len(domains_r1),
            )
        )
    return AssignmentResult(
        params=params, blocks=assigned, n_support_points=len(points), findings=[]
    )


def summarize_assignment(result: AssignmentResult) -> dict[str, object]:
    """Counts per status and per domain (assigned blocks only), plus mixed blocks."""
    status_counts = {status: 0 for status in STATUSES}
    domain_counts: dict[str, int] = defaultdict(int)
    mixed = 0
    for block in result.blocks:
        status_counts[block.assign_status] += 1
        if block.domain_id is not None:
            domain_counts[block.domain_id] += 1
        if block.mixed_flag:
            mixed += 1
    rock = sum(
        count
        for status, count in status_counts.items()
        if status not in (STATUS_NOT_ROCK, STATUS_UNKNOWN_TOPO)
    )
    return {
        "n_blocks": len(result.blocks),
        "n_rock_blocks": rock,
        "status_counts": status_counts,
        "domain_counts": dict(sorted(domain_counts.items())),
        "mixed_blocks": mixed,
        "n_support_points": result.n_support_points,
        "n_findings": len(result.findings),
    }


def write_assignment_csv(blocks: list[BlockDomain], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for block in blocks:
            writer.writerow(
                [
                    block.block_id,
                    block.ix,
                    block.iy,
                    block.iz,
                    f"{block.xc:.3f}",
                    f"{block.yc:.3f}",
                    f"{block.zc:.3f}",
                    block.topo_state,
                    block.domain_id or "",
                    block.assign_status,
                    "" if block.nearest_dist_m is None else f"{block.nearest_dist_m:.3f}",
                    block.nearest_hole_id or "",
                    block.n_holes_r1,
                    block.n_domains_r1,
                    int(block.mixed_flag),
                ]
            )


def run_m01b_domain_assignment(
    composites_path: str | Path = DEFAULT_COMPOSITES_PATH,
    blocks_path: str | Path = DEFAULT_BLOCKS_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    params: SearchParams | None = None,
) -> tuple[AssignmentResult, dict[str, object]]:
    """Read composites and classified blocks, assign domains and write the CSV."""
    points, findings = read_support_points(composites_path)
    result = assign_domains(read_blocks(blocks_path), points, params)
    result = AssignmentResult(
        params=result.params,
        blocks=result.blocks,
        n_support_points=result.n_support_points,
        findings=findings,
    )
    write_assignment_csv(result.blocks, output_path)
    return result, summarize_assignment(result)


def _empty(block: Block, status: str) -> BlockDomain:
    return BlockDomain(
        block_id=block.block_id,
        ix=block.ix,
        iy=block.iy,
        iz=block.iz,
        xc=block.xc,
        yc=block.yc,
        zc=block.zc,
        topo_state=block.topo_state,
        domain_id=None,
        assign_status=status,
        nearest_dist_m=None,
        nearest_hole_id=None,
        n_holes_r1=0,
        n_domains_r1=0,
    )


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _finding(
    rule_id: str,
    severity: str,
    table: str,
    field: str,
    observed_value: str,
    expected_condition: str,
) -> ValidationFinding:
    return ValidationFinding(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        table=table,
        row_number=None,
        hole_id=None,
        sample_id=None,
        field=field,
        observed_value=observed_value,
        expected_condition=expected_condition,
    )


if __name__ == "__main__":
    _result, _summary = run_m01b_domain_assignment()
    print(f"blocks: {_summary['n_blocks']} (rock: {_summary['n_rock_blocks']})")
    for _status, _count in _summary["status_counts"].items():  # type: ignore[union-attr]
        print(f"{_status}: {_count}")
    print(f"domains: {_summary['domain_counts']}")
    print(f"mixed blocks within r1: {_summary['mixed_blocks']}")
    print(f"findings: {_summary['n_findings']}")
