"""Calculate drillhole trajectories from collar and observed survey stations."""

from dataclasses import dataclass
from math import acos, cos, isfinite, pi, sin, tan

from src.m01.loader import M01Data, TableRecord
from src.m01.validator import Severity, ValidationFinding, ValidationReport


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class TrajectoryPoint:
    """Calculated XYZ position and downhole direction at one measured depth."""

    hole_id: str
    depth_m: float
    x: float
    y: float
    z: float
    direction: Vector3


@dataclass(frozen=True)
class HoleTrajectory:
    """Desurveyed points for one hole, limited to observed survey coverage."""

    hole_id: str
    points: tuple[TrajectoryPoint, ...]

    @property
    def maximum_depth_m(self) -> float:
        return self.points[-1].depth_m


@dataclass(frozen=True)
class DesurveyResult:
    """Calculated trajectories and desurvey-specific blocking findings."""

    trajectories: tuple[HoleTrajectory, ...]
    findings: tuple[ValidationFinding, ...]


def _direction_vector(azimuth_deg: float, dip_deg: float) -> Vector3:
    """Convert project azimuth/dip degrees to a normalized East/North/Up vector."""
    azimuth = azimuth_deg * pi / 180.0
    dip = dip_deg * pi / 180.0
    vector = (
        sin(azimuth) * cos(dip),
        cos(azimuth) * cos(dip),
        sin(dip),
    )
    magnitude = sum(component * component for component in vector) ** 0.5
    if not isfinite(magnitude) or magnitude == 0:
        raise ValueError("orientation does not define a finite direction")
    return (
        vector[0] / magnitude,
        vector[1] / magnitude,
        vector[2] / magnitude,
    )


def minimum_curvature_displacement(
    md_start_m: float,
    md_end_m: float,
    direction_start: Vector3,
    direction_end: Vector3,
) -> Vector3:
    """Calculate the minimum-curvature displacement between two stations."""
    delta_md = md_end_m - md_start_m
    if not isfinite(delta_md) or delta_md <= 0:
        raise ValueError("survey station depths must increase")

    dot_product = sum(
        start * end for start, end in zip(direction_start, direction_end)
    )
    dogleg = acos(max(-1.0, min(1.0, dot_product)))
    if pi - dogleg <= 1e-12:
        raise ValueError("180-degree dogleg has no stable minimum-curvature solution")

    if dogleg <= 1e-12:
        ratio_factor = 1.0
    else:
        ratio_factor = (2.0 / dogleg) * tan(dogleg / 2.0)

    displacement = tuple(
        delta_md / 2.0 * (start + end) * ratio_factor
        for start, end in zip(direction_start, direction_end)
    )
    if not all(isfinite(component) for component in displacement):
        raise ValueError("minimum-curvature displacement is not finite")
    return displacement[0], displacement[1], displacement[2]


def desurvey_m01_data(
    data: M01Data,
    validation_report: ValidationReport,
) -> DesurveyResult:
    """Calculate each valid hole trajectory through its last observed survey.

    Collar XYZ anchors each trajectory. A zero-depth survey direction governs
    when present; otherwise the collar direction is used provisionally. The
    caller must run ``validate_m01_data`` first and pass its report.
    """
    survey_by_hole: dict[str, list[tuple[int, TableRecord]]] = {}
    for row_number, station in enumerate(data.survey.records, start=2):
        hole_id = _text(station.get("hole_id"))
        if hole_id is not None:
            survey_by_hole.setdefault(hole_id, []).append((row_number, station))

    errors_by_hole: dict[str, list[ValidationFinding]] = {}
    for finding in validation_report.findings:
        if (
            finding.severity == "ERROR"
            and finding.table in {"collar", "survey"}
            and finding.hole_id is not None
        ):
            errors_by_hole.setdefault(finding.hole_id, []).append(finding)

    trajectories: list[HoleTrajectory] = []
    findings: list[ValidationFinding] = []

    for collar_row, collar in enumerate(data.collar.records, start=2):
        hole_id = _text(collar.get("hole_id"))
        if hole_id is None:
            continue

        blocking_findings = errors_by_hole.get(hole_id, [])
        if blocking_findings:
            findings.append(
                _finding(
                    "DESURVEY-001",
                    "ERROR",
                    "collar",
                    collar_row,
                    collar,
                    "hole_id",
                    ",".join(sorted({item.rule_id for item in blocking_findings})),
                    "resolve collar/survey ERROR findings before desurvey",
                )
            )
            continue

        stations = survey_by_hole.get(hole_id, [])
        if not stations:
            findings.append(
                _finding(
                    "DESURVEY-002",
                    "ERROR",
                    "collar",
                    collar_row,
                    collar,
                    "hole_id",
                    hole_id,
                    "at least one observed survey station is required; no stations are synthesized",
                )
            )
            continue

        try:
            x = _finite_number(collar.get("x"), "collar.x")
            y = _finite_number(collar.get("y"), "collar.y")
            z = _finite_number(collar.get("z"), "collar.z")
            collar_direction = _direction_vector(
                _finite_number(collar.get("azimuth_deg"), "collar.azimuth_deg"),
                _finite_number(collar.get("dip_deg"), "collar.dip_deg"),
            )
            unique_stations = _unique_stations(stations)
            zero_station = next(
                (
                    record
                    for _, record in unique_stations
                    if _finite_number(record.get("depth_m"), "survey.depth_m") == 0
                ),
                None,
            )
            initial_direction = (
                _survey_direction(zero_station)
                if zero_station is not None
                else collar_direction
            )
            points = [
                TrajectoryPoint(
                    hole_id=hole_id,
                    depth_m=0.0,
                    x=x,
                    y=y,
                    z=z,
                    direction=initial_direction,
                )
            ]

            for _, station in unique_stations:
                depth = _finite_number(station.get("depth_m"), "survey.depth_m")
                if depth == 0:
                    continue
                direction = _survey_direction(station)
                previous = points[-1]
                dx, dy, dz = minimum_curvature_displacement(
                    previous.depth_m,
                    depth,
                    previous.direction,
                    direction,
                )
                points.append(
                    TrajectoryPoint(
                        hole_id=hole_id,
                        depth_m=depth,
                        x=previous.x + dx,
                        y=previous.y + dy,
                        z=previous.z + dz,
                        direction=direction,
                    )
                )

            trajectories.append(HoleTrajectory(hole_id, tuple(points)))
        except (ValueError, OverflowError) as error:
            findings.append(
                _finding(
                    "DESURVEY-003",
                    "ERROR",
                    "survey",
                    None,
                    {"hole_id": hole_id},
                    "trajectory",
                    str(error),
                    "trajectory coordinates and minimum-curvature displacements are finite and defined",
                )
            )

    return DesurveyResult(tuple(trajectories), tuple(findings))


def _unique_stations(
    stations: list[tuple[int, TableRecord]],
) -> list[tuple[int, TableRecord]]:
    """Keep the first CSV record at each MD after validator-approved deduplication."""
    first_at_depth: dict[float, tuple[int, TableRecord]] = {}
    for row_number, station in stations:
        depth = _finite_number(station.get("depth_m"), "survey.depth_m")
        first_at_depth.setdefault(depth, (row_number, station))
    return sorted(
        first_at_depth.values(),
        key=lambda item: _finite_number(
            item[1].get("depth_m"), "survey.depth_m"
        ),
    )


def _survey_direction(station: TableRecord) -> Vector3:
    return _direction_vector(
        _finite_number(station.get("azimuth_deg"), "survey.azimuth_deg"),
        _finite_number(station.get("dip_deg"), "survey.dip_deg"),
    )


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finding(
    rule_id: str,
    severity: Severity,
    table: str,
    row_number: int | None,
    record: TableRecord,
    field: str,
    observed_value: str,
    expected_condition: str,
) -> ValidationFinding:
    hole_id = _text(record.get("hole_id"))
    sample_id = record.get("sample_id")
    if sample_id is None:
        sample_id = record.get("density_sample_id")
    return ValidationFinding(
        rule_id=rule_id,
        severity=severity,
        table=table,
        row_number=row_number,
        hole_id=hole_id,
        sample_id=_text(sample_id),
        field=field,
        observed_value=observed_value,
        expected_condition=expected_condition,
    )
