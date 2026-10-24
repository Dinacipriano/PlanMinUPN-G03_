"""Regular preliminary block grid and topographic state per block (M01B).

Scope: geometry and relation of each block with the topographic surface only.
No grade, density or tonnage estimation, and no geological assignment here.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from math import atan2, floor, isfinite, pi
from pathlib import Path

from src.m01.validator import ValidationFinding

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOPOGRAPHY_PATH = _ROOT / "data" / "raw" / "topography" / "Topopl.csv"
DEFAULT_OUTPUT_PATH = _ROOT / "data" / "processed" / "m01b" / "blocks_topo.csv"

STATE_AIR = "AIR"
STATE_ROCK = "ROCK"
STATE_PARTIAL = "PARTIAL"
STATE_OUTSIDE = "OUTSIDE_TOPO_COVERAGE"
STATES = (STATE_ROCK, STATE_PARTIAL, STATE_AIR, STATE_OUTSIDE)

TOLERANCE_M = 1e-6
N_SECTORS = 8
CSV_COLUMNS = (
    "block_id",
    "ix",
    "iy",
    "iz",
    "xc",
    "yc",
    "zc",
    "dx",
    "dy",
    "dz",
    "volume_m3",
    "ztopo_center",
    "ztopo_min",
    "ztopo_max",
    "topo_state",
)


@dataclass(frozen=True)
class GridSpec:
    """Regular grid defined by its minimum corner, block size and block counts."""

    x0: float
    y0: float
    z0: float
    dx: float
    dy: float
    dz: float
    nx: int
    ny: int
    nz: int

    def __post_init__(self) -> None:
        if min(self.dx, self.dy, self.dz) <= 0:
            raise ValueError("block sizes must be positive")
        if min(self.nx, self.ny, self.nz) <= 0:
            raise ValueError("block counts must be positive")

    @property
    def n_blocks(self) -> int:
        return self.nx * self.ny * self.nz

    @property
    def z_top(self) -> float:
        return self.z0 + self.nz * self.dz

    def block_id(self, ix: int, iy: int, iz: int) -> int:
        return ix + self.nx * (iy + self.ny * iz)


# DECISION-03 (IMP-002): 25 x 25 x 10 m, drilled footprint + one block of margin;
# top raised to 3540 m after GRID-001 (surface reaches 3533.8 m in the footprint).
DEFAULT_GRID = GridSpec(
    x0=242225.0,
    y0=8196100.0,
    z0=3060.0,
    dx=25.0,
    dy=25.0,
    dz=10.0,
    nx=26,
    ny=24,
    nz=48,
)


@dataclass(frozen=True)
class SurfaceParams:
    """Local search used to evaluate the surface; nothing is extrapolated."""

    radius_m: float = 40.0
    min_sectors: int = 4


class TopographySurface:
    """Elevation z(x, y) from scattered points, with an explicit coverage rule.

    The nearest point inside each of eight angular sectors is combined by
    inverse-distance weighting (power 2). A location is covered only when at
    least ``min_sectors`` sectors have a point within the radius and the
    points surround it (largest angular gap below 180 degrees). Otherwise the
    elevation is ``None``: the surface is not extrapolated.
    """

    def __init__(
        self,
        points: list[tuple[float, float, float]],
        params: SurfaceParams | None = None,
    ) -> None:
        self.params = params or SurfaceParams()
        self._cell = self.params.radius_m
        self._buckets: dict[tuple[int, int], list[tuple[float, float, float]]] = (
            defaultdict(list)
        )
        for x, y, z in points:
            self._buckets[(floor(x / self._cell), floor(y / self._cell))].append(
                (x, y, z)
            )
        self.n_points = len(points)

    def elevation(self, x: float, y: float) -> float | None:
        radius_sq = self.params.radius_m**2
        bx = floor(x / self._cell)
        by = floor(y / self._cell)
        best: list[tuple[float, float, float] | None] = [None] * N_SECTORS
        for i in (bx - 1, bx, bx + 1):
            for j in (by - 1, by, by + 1):
                for px, py, pz in self._buckets.get((i, j), ()):
                    ddx = px - x
                    ddy = py - y
                    dist_sq = ddx * ddx + ddy * ddy
                    if dist_sq > radius_sq:
                        continue
                    if dist_sq < 1e-12:
                        return pz
                    angle = atan2(ddy, ddx)
                    sector = min(int((angle + pi) / (2 * pi) * N_SECTORS), N_SECTORS - 1)
                    current = best[sector]
                    if current is None or dist_sq < current[0]:
                        best[sector] = (dist_sq, pz, angle)
        chosen = [item for item in best if item is not None]
        if len(chosen) < self.params.min_sectors:
            return None
        angles = sorted(item[2] for item in chosen)
        gaps = [b - a for a, b in zip(angles, angles[1:])]
        gaps.append(angles[0] + 2 * pi - angles[-1])
        if max(gaps) >= pi:
            return None
        weights = [1.0 / item[0] for item in chosen]
        return sum(w * item[1] for w, item in zip(weights, chosen)) / sum(weights)


@dataclass(frozen=True)
class Block:
    block_id: int
    ix: int
    iy: int
    iz: int
    xc: float
    yc: float
    zc: float
    dx: float
    dy: float
    dz: float
    ztopo_center: float | None
    ztopo_min: float | None
    ztopo_max: float | None
    topo_state: str

    @property
    def volume_m3(self) -> float:
        """Nominal geometric volume; NOT the rock volume of PARTIAL blocks."""
        return self.dx * self.dy * self.dz


@dataclass(frozen=True)
class BlockModelResult:
    grid: GridSpec
    blocks: list[Block]
    findings: list[ValidationFinding]


def read_topography(
    path: str | Path = DEFAULT_TOPOGRAPHY_PATH,
) -> tuple[list[tuple[float, float, float]], list[ValidationFinding]]:
    """Read PID,X,Y,Z points; invalid rows are reported and skipped."""
    findings: list[ValidationFinding] = []
    points: list[tuple[float, float, float]] = []
    source = Path(path)
    if not source.is_file():
        findings.append(
            _finding(
                "TOPO-001",
                "ERROR",
                None,
                "file",
                str(source),
                "topography file must exist; none is invented",
            )
        )
        return points, findings
    with source.open(newline="", encoding="utf-8") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            values = [_to_float(row.get(name)) for name in ("X", "Y", "Z")]
            if any(value is None for value in values):
                findings.append(
                    _finding(
                        "TOPO-002",
                        "ERROR",
                        row_number,
                        "X,Y,Z",
                        str({k: row.get(k) for k in ("X", "Y", "Z")}),
                        "X, Y and Z must be finite numbers",
                    )
                )
                continue
            points.append((values[0], values[1], values[2]))  # type: ignore[arg-type]
    return points, findings


def build_block_model(
    surface: TopographySurface, grid: GridSpec = DEFAULT_GRID
) -> BlockModelResult:
    """Create every block and classify it against the surface.

    The surface is evaluated at the four corners and the center of each block
    column. A block is ROCK when its top is not above the lowest of those
    elevations, AIR when its base is not below the highest, PARTIAL otherwise,
    and OUTSIDE_TOPO_COVERAGE when any of the five points has no coverage.
    """
    findings: list[ValidationFinding] = []
    node_cache: dict[tuple[float, float], float | None] = {}

    def z_at(x: float, y: float) -> float | None:
        key = (x, y)
        if key not in node_cache:
            node_cache[key] = surface.elevation(x, y)
        return node_cache[key]

    columns: dict[tuple[int, int], tuple[float | None, float | None, float | None]] = {}
    truncated_columns = 0
    for iy in range(grid.ny):
        for ix in range(grid.nx):
            xmin = grid.x0 + ix * grid.dx
            ymin = grid.y0 + iy * grid.dy
            samples = [
                z_at(xmin, ymin),
                z_at(xmin + grid.dx, ymin),
                z_at(xmin, ymin + grid.dy),
                z_at(xmin + grid.dx, ymin + grid.dy),
            ]
            center = z_at(xmin + grid.dx / 2, ymin + grid.dy / 2)
            samples.append(center)
            if any(value is None for value in samples):
                columns[(ix, iy)] = (None, None, None)
                continue
            values = [value for value in samples if value is not None]
            columns[(ix, iy)] = (center, min(values), max(values))
            if max(values) > grid.z_top + TOLERANCE_M:
                truncated_columns += 1
    if truncated_columns:
        findings.append(
            _finding(
                "GRID-001",
                "WARNING",
                None,
                "z_top",
                f"{truncated_columns} columns have surface above {grid.z_top:g}",
                "grid top should reach the highest surface elevation",
            )
        )

    blocks: list[Block] = []
    for iz in range(grid.nz):
        z_min = grid.z0 + iz * grid.dz
        z_max = z_min + grid.dz
        for iy in range(grid.ny):
            for ix in range(grid.nx):
                center, low, high = columns[(ix, iy)]
                if low is None or high is None:
                    state = STATE_OUTSIDE
                elif z_max <= low + TOLERANCE_M:
                    state = STATE_ROCK
                elif z_min >= high - TOLERANCE_M:
                    state = STATE_AIR
                else:
                    state = STATE_PARTIAL
                blocks.append(
                    Block(
                        block_id=grid.block_id(ix, iy, iz),
                        ix=ix,
                        iy=iy,
                        iz=iz,
                        xc=grid.x0 + (ix + 0.5) * grid.dx,
                        yc=grid.y0 + (iy + 0.5) * grid.dy,
                        zc=z_min + grid.dz / 2,
                        dx=grid.dx,
                        dy=grid.dy,
                        dz=grid.dz,
                        ztopo_center=center,
                        ztopo_min=low,
                        ztopo_max=high,
                        topo_state=state,
                    )
                )
    return BlockModelResult(grid=grid, blocks=blocks, findings=findings)


def summarize_block_model(result: BlockModelResult) -> dict[str, object]:
    """Counts and nominal volume per topographic state (no rock volume claimed)."""
    counts = {state: 0 for state in STATES}
    for block in result.blocks:
        counts[block.topo_state] += 1
    total = len(result.blocks)
    return {
        "n_blocks": total,
        "grid": result.grid,
        "counts": counts,
        "percent": {
            state: (100.0 * count / total if total else 0.0)
            for state, count in counts.items()
        },
        "nominal_block_volume_m3": result.grid.dx * result.grid.dy * result.grid.dz,
        "n_findings": len(result.findings),
    }


def write_block_model_csv(blocks: list[Block], path: str | Path) -> None:
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
                    f"{block.dx:g}",
                    f"{block.dy:g}",
                    f"{block.dz:g}",
                    f"{block.volume_m3:g}",
                    _format_optional(block.ztopo_center),
                    _format_optional(block.ztopo_min),
                    _format_optional(block.ztopo_max),
                    block.topo_state,
                ]
            )


def run_m01b_block_model(
    topography_path: str | Path = DEFAULT_TOPOGRAPHY_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    grid: GridSpec = DEFAULT_GRID,
) -> tuple[BlockModelResult, dict[str, object]]:
    """Read the topography, build the grid, classify blocks and write the CSV."""
    points, findings = read_topography(topography_path)
    result = build_block_model(TopographySurface(points), grid)
    result = BlockModelResult(
        grid=result.grid, blocks=result.blocks, findings=findings + result.findings
    )
    write_block_model_csv(result.blocks, output_path)
    return result, summarize_block_model(result)


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _finding(
    rule_id: str,
    severity: str,
    row_number: int | None,
    field: str,
    observed_value: str,
    expected_condition: str,
) -> ValidationFinding:
    return ValidationFinding(
        rule_id=rule_id,
        severity=severity,  # type: ignore[arg-type]
        table="topography" if rule_id.startswith("TOPO") else "block_model",
        row_number=row_number,
        hole_id=None,
        sample_id=None,
        field=field,
        observed_value=observed_value,
        expected_condition=expected_condition,
    )


if __name__ == "__main__":
    _result, _summary = run_m01b_block_model()
    print(f"blocks: {_summary['n_blocks']}")
    for _state, _count in _summary["counts"].items():  # type: ignore[union-attr]
        print(f"{_state}: {_count}")
    print(f"findings: {_summary['n_findings']}")
