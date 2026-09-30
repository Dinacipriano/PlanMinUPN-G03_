"""Position downhole intervals on desurveyed trajectories."""

from dataclasses import dataclass
from math import acos, isfinite, sin

from src.m01.desurvey import (
    HoleTrajectory,
    Vector3,
    minimum_curvature_displacement,
)
from src.m01.loader import M01Data, TableRecord
from src.m01.validator import Severity, ValidationFinding


@dataclass(frozen=True)
class PositionedInterval:
    """One source interval with spatial coordinates at its FROM and TO depths."""

    table: str
    row_number: int
    hole_id: str
    from_m: float
    to_m: float
    from_xyz: Vector3
    to_xyz: Vector3
    sample_id: str | None


@dataclass(frozen=True)
class PositioningResult:
    """Successfully positioned intervals and interval-positioning findings."""

    intervals: tuple[PositionedInterval, ...]
    findings: tuple[ValidationFinding, ...]


def position_m01_intervals(
    data: M01Data,
    trajectories: tuple[HoleTrajectory, ...],
) -> PositioningResult:
    """Position interval endpoints only when both MD values are covered.

    No extrapolation is performed. An interval with either endpoint outside
    the calculated trajectory receives an ERROR and no XYZ coordinates.
    """
    trajectory_by_hole = {
        trajectory.hole_id: trajectory for trajectory in trajectories
    }
    positioned: list[PositionedInterval] = []
    findings: list[ValidationFinding] = []

    tables = (
        ("lithology", data.lithology),
        ("alteration", data.alteration),
        ("assay", data.assay),
        ("density", data.density),
    )
    for table_name, table in tables:
        for row_number, record in enumerate(table.records, start=2):
            hole_id = _text(record.get("hole_id"))
            if hole_id is None:
                findings.append(
                    _finding(
                        "POSITION-001",
                        table_name,
                        row_number,
                        record,
                        "hole_id",
                        "MISSING_HOLE_ID",
                        "interval must identify a hole with a calculated trajectory",
                    )
                )
                continue

            trajectory = trajectory_by_hole.get(hole_id)
            if trajectory is None:
                findings.append(
                    _finding(
                        "POSITION-001",
                        table_name,
                        row_number,
                        record,
                        "hole_id",
                        hole_id,
                        "interval hole must have a valid calculated trajectory",
                    )
                )
                continue

            start = _finite_number(record.get("from_m"))
            end = _finite_number(record.get("to_m"))
            if start is None or end is None or start >= end:
                findings.append(
                    _finding(
                        "POSITION-002",
                        table_name,
                        row_number,
                        record,
                        "from_m,to_m",
                        f"{record.get('from_m')!r},{record.get('to_m')!r}",
                        "interval endpoints must be finite measured depths with from_m < to_m",
                    )
                )
                continue

            outside = [
                field
                for field, depth in (("from_m", start), ("to_m", end))
                if depth < trajectory.points[0].depth_m
                or depth > trajectory.maximum_depth_m
            ]
            if outside:
                findings.append(
                    _finding(
                        "POSITION-003",
                        table_name,
                        row_number,
                        record,
                        ",".join(outside),
                        f"trajectory coverage is [0, {trajectory.maximum_depth_m:g}] m",
                        "both from_m and to_m must fall within observed trajectory coverage; no extrapolation or XYZ is produced",
                    )
                )
                continue

            try:
                from_xyz = _position_at_depth(trajectory, start)
                to_xyz = _position_at_depth(trajectory, end)
            except ValueError as error:
                findings.append(
                    _finding(
                        "POSITION-004",
                        table_name,
                        row_number,
                        record,
                        "from_m,to_m",
                        str(error),
                        "interval endpoints resolve to finite coordinates on the calculated trajectory",
                    )
                )
                continue

            positioned.append(
                PositionedInterval(
                    table=table_name,
                    row_number=row_number,
                    hole_id=hole_id,
                    from_m=start,
                    to_m=end,
                    from_xyz=from_xyz,
                    to_xyz=to_xyz,
                    sample_id=_sample_id(record),
                )
            )

    return PositioningResult(tuple(positioned), tuple(findings))


def _position_at_depth(trajectory: HoleTrajectory, depth_m: float) -> Vector3:
    """Evaluate a point inside a survey segment using its minimum-curvature arc."""
    points = trajectory.points
    if depth_m < points[0].depth_m or depth_m > points[-1].depth_m:
        raise ValueError("requested MD is outside observed trajectory coverage")

    for point in points:
        if depth_m == point.depth_m:
            return point.x, point.y, point.z

    for start, end in zip(points, points[1:]):
        if start.depth_m < depth_m < end.depth_m:
            fraction = (depth_m - start.depth_m) / (end.depth_m - start.depth_m)
            direction_at_depth = _slerp_direction(
                start.direction,
                end.direction,
                fraction,
            )
            dx, dy, dz = minimum_curvature_displacement(
                start.depth_m,
                depth_m,
                start.direction,
                direction_at_depth,
            )
            result = start.x + dx, start.y + dy, start.z + dz
            if not all(isfinite(value) for value in result):
                raise ValueError("positioned XYZ coordinates are not finite")
            return result

    raise ValueError("requested MD does not belong to a trajectory segment")


def _slerp_direction(start: Vector3, end: Vector3, fraction: float) -> Vector3:
    """Interpolate a unit direction along the shorter spherical arc."""
    dot_product = sum(first * second for first, second in zip(start, end))
    dogleg = acos(max(-1.0, min(1.0, dot_product)))
    if dogleg <= 1e-12:
        return start
    denominator = sin(dogleg)
    if abs(denominator) <= 1e-12:
        raise ValueError("opposite survey directions do not define a unique arc")
    start_weight = sin((1.0 - fraction) * dogleg) / denominator
    end_weight = sin(fraction * dogleg) / denominator
    vector = tuple(
        start_weight * first + end_weight * second
        for first, second in zip(start, end)
    )
    magnitude = sum(component * component for component in vector) ** 0.5
    if not isfinite(magnitude) or magnitude == 0:
        raise ValueError("interpolated direction is not finite")
    return (
        vector[0] / magnitude,
        vector[1] / magnitude,
        vector[2] / magnitude,
    )


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sample_id(record: TableRecord) -> str | None:
    value = record.get("sample_id", record.get("density_sample_id"))
    return _text(value)


def _finding(
    rule_id: str,
    table: str,
    row_number: int,
    record: TableRecord,
    field: str,
    observed_value: str,
    expected_condition: str,
) -> ValidationFinding:
    severity: Severity = "ERROR"
    return ValidationFinding(
        rule_id=rule_id,
        severity=severity,
        table=table,
        row_number=row_number,
        hole_id=_text(record.get("hole_id")),
        sample_id=_sample_id(record),
        field=field,
        observed_value=observed_value,
        expected_condition=expected_condition,
    )
