"""Composite M01 assay intervals without crossing lithology contacts (M01B)."""

import csv
from collections import defaultdict
from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path

from src.m01.desurvey import HoleTrajectory, desurvey_m01_data
from src.m01.loader import M01Data, TableRecord, load_m01_data
from src.m01.positioning import _position_at_depth
from src.m01.validator import ValidationFinding, validate_m01_data

TARGET_LENGTH_M = 2.0
TOLERANCE_M = 1e-6
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "processed"
    / "m01b"
    / "composites.csv"
)
CSV_COLUMNS = (
    "hole_id",
    "from_m",
    "to_m",
    "length_m",
    "mid_m",
    "x",
    "y",
    "z",
    "lith_code",
    "cu_pct",
    "residual_flag",
    "n_pieces",
)


@dataclass(frozen=True)
class AssaySegment:
    """Part of one assay interval that lies inside a single lithology interval."""

    hole_id: str
    from_m: float
    to_m: float
    lith_code: str
    cu_pct: float
    sample_id: str | None

    @property
    def length_m(self) -> float:
        return self.to_m - self.from_m


@dataclass(frozen=True)
class Composite:
    """Length-weighted Cu composite inside one continuous lithology run."""

    hole_id: str
    from_m: float
    to_m: float
    lith_code: str
    cu_pct: float
    residual_flag: bool
    n_pieces: int
    x: float | None = None
    y: float | None = None
    z: float | None = None

    @property
    def length_m(self) -> float:
        return self.to_m - self.from_m

    @property
    def mid_m(self) -> float:
        return (self.from_m + self.to_m) / 2.0


@dataclass(frozen=True)
class CompositingResult:
    """Segments, composites and compositing findings."""

    segments: tuple[AssaySegment, ...]
    composites: tuple[Composite, ...]
    findings: tuple[ValidationFinding, ...]


def split_assays_at_contacts(
    data: M01Data,
) -> tuple[tuple[AssaySegment, ...], tuple[ValidationFinding, ...]]:
    """Split every assay interval exactly at the lithology contacts it crosses.

    Each piece keeps the assay Cu grade and takes the code of the lithology
    interval that contains it. Invalid, overlapping or uncovered pieces are
    reported as ERROR findings and are not invented or repaired.
    """
    findings: list[ValidationFinding] = []

    lithology_by_hole: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for row_number, record in enumerate(data.lithology.records, start=2):
        hole_id = _text(record.get("hole_id"))
        start = _finite_number(record.get("from_m"))
        end = _finite_number(record.get("to_m"))
        code = _text(record.get("lith_code"))
        if hole_id is None or start is None or end is None or code is None or start >= end:
            findings.append(
                _finding(
                    "COMPOSITE-001",
                    "lithology",
                    row_number,
                    record,
                    "hole_id,from_m,to_m,lith_code",
                    "invalid lithology interval",
                    "lithology interval needs hole_id, finite from_m < to_m and lith_code",
                )
            )
            continue
        lithology_by_hole[hole_id].append((start, end, code))

    for hole_id, intervals in lithology_by_hole.items():
        intervals.sort()
        clean: list[tuple[float, float, str]] = []
        for start, end, code in intervals:
            if clean and start < clean[-1][1] - TOLERANCE_M:
                findings.append(
                    ValidationFinding(
                        rule_id="COMPOSITE-001",
                        severity="ERROR",
                        table="lithology",
                        row_number=None,
                        hole_id=hole_id,
                        sample_id=None,
                        field="from_m,to_m",
                        observed_value=f"{start:g}-{end:g} overlaps previous interval",
                        expected_condition="lithology intervals must not overlap",
                    )
                )
                continue
            clean.append((start, end, code))
        lithology_by_hole[hole_id] = clean

    assay_by_hole: dict[str, list[tuple[int, TableRecord, float, float, float]]] = defaultdict(list)
    for row_number, record in enumerate(data.assay.records, start=2):
        hole_id = _text(record.get("hole_id"))
        start = _finite_number(record.get("from_m"))
        end = _finite_number(record.get("to_m"))
        cu_pct = _finite_number(record.get("cu_pct"))
        if hole_id is None or start is None or end is None or cu_pct is None or start >= end:
            findings.append(
                _finding(
                    "COMPOSITE-002",
                    "assay",
                    row_number,
                    record,
                    "hole_id,from_m,to_m,cu_pct",
                    "invalid assay interval or cu_pct",
                    "assay needs hole_id, finite from_m < to_m and finite cu_pct",
                )
            )
            continue
        assay_by_hole[hole_id].append((row_number, record, start, end, cu_pct))

    segments: list[AssaySegment] = []
    for hole_id in sorted(assay_by_hole):
        previous_end: float | None = None
        for row_number, record, start, end, cu_pct in sorted(
            assay_by_hole[hole_id], key=lambda item: (item[2], item[3])
        ):
            if previous_end is not None and start < previous_end - TOLERANCE_M:
                findings.append(
                    _finding(
                        "COMPOSITE-004",
                        "assay",
                        row_number,
                        record,
                        "from_m,to_m",
                        f"{start:g}-{end:g} overlaps previous assay",
                        "assay intervals within a hole must not overlap; interval skipped",
                    )
                )
                continue
            previous_end = end if previous_end is None else max(previous_end, end)

            covered = 0.0
            for lith_start, lith_end, code in lithology_by_hole.get(hole_id, []):
                piece_start = max(start, lith_start)
                piece_end = min(end, lith_end)
                if piece_end - piece_start > TOLERANCE_M:
                    segments.append(
                        AssaySegment(
                            hole_id=hole_id,
                            from_m=piece_start,
                            to_m=piece_end,
                            lith_code=code,
                            cu_pct=cu_pct,
                            sample_id=_text(record.get("sample_id")),
                        )
                    )
                    covered += piece_end - piece_start
            if (end - start) - covered > TOLERANCE_M:
                findings.append(
                    _finding(
                        "COMPOSITE-003",
                        "assay",
                        row_number,
                        record,
                        "from_m,to_m",
                        f"{(end - start) - covered:.6f} m without lithology",
                        "every assay meter must lie inside a lithology interval; uncovered part excluded",
                    )
                )

    segments.sort(key=lambda segment: (segment.hole_id, segment.from_m))
    return tuple(segments), tuple(findings)


def composite_segments(
    segments: tuple[AssaySegment, ...],
    target_length_m: float = TARGET_LENGTH_M,
) -> tuple[Composite, ...]:
    """Composite each hole independently inside continuous lithology runs.

    A run is a chain of touching segments with the same lithology code.
    Windows start at the run start, so a composite never crosses a contact or
    a gap. A final window shorter than the target is kept as a residual.
    """
    composites: list[Composite] = []
    runs: list[list[AssaySegment]] = []
    for segment in segments:
        previous = runs[-1][-1] if runs else None
        if (
            previous is not None
            and previous.hole_id == segment.hole_id
            and previous.lith_code == segment.lith_code
            and abs(segment.from_m - previous.to_m) <= TOLERANCE_M
        ):
            runs[-1].append(segment)
        else:
            runs.append([segment])

    for run in runs:
        run_end = run[-1].to_m
        position = run[0].from_m
        while position < run_end - TOLERANCE_M:
            window_end = min(position + target_length_m, run_end)
            if run_end - window_end < TOLERANCE_M:
                window_end = run_end

            weighted_sum = 0.0
            total_length = 0.0
            pieces = 0
            for segment in run:
                overlap_start = max(position, segment.from_m)
                overlap_end = min(window_end, segment.to_m)
                overlap = overlap_end - overlap_start
                if overlap > TOLERANCE_M:
                    weighted_sum += segment.cu_pct * overlap
                    total_length += overlap
                    pieces += 1

            length = window_end - position
            composites.append(
                Composite(
                    hole_id=run[0].hole_id,
                    from_m=position,
                    to_m=window_end,
                    lith_code=run[0].lith_code,
                    cu_pct=weighted_sum / total_length,
                    residual_flag=length < target_length_m - TOLERANCE_M,
                    n_pieces=pieces,
                )
            )
            position = window_end

    return tuple(composites)


def position_composites(
    composites: tuple[Composite, ...],
    trajectories: tuple[HoleTrajectory, ...],
) -> tuple[tuple[Composite, ...], tuple[ValidationFinding, ...]]:
    """Add XYZ at each composite midpoint, never extrapolating past coverage."""
    trajectory_by_hole = {trajectory.hole_id: trajectory for trajectory in trajectories}
    positioned: list[Composite] = []
    findings: list[ValidationFinding] = []
    for composite in composites:
        trajectory = trajectory_by_hole.get(composite.hole_id)
        reason: str | None = None
        if trajectory is None:
            reason = "hole has no calculated trajectory"
        elif (
            composite.mid_m < trajectory.points[0].depth_m
            or composite.mid_m > trajectory.maximum_depth_m
        ):
            reason = f"midpoint outside trajectory coverage [0, {trajectory.maximum_depth_m:g}] m"
        if reason is None and trajectory is not None:
            try:
                x, y, z = _position_at_depth(trajectory, composite.mid_m)
            except ValueError as error:
                reason = str(error)
            else:
                positioned.append(replace(composite, x=x, y=y, z=z))
                continue
        positioned.append(composite)
        findings.append(
            ValidationFinding(
                rule_id="COMPOSITE-005",
                severity="ERROR",
                table="composites",
                row_number=None,
                hole_id=composite.hole_id,
                sample_id=None,
                field="mid_m",
                observed_value=f"{composite.mid_m:.6f}",
                expected_condition=f"composite midpoint must have XYZ on the trajectory ({reason}); no XYZ produced",
            )
        )
    return tuple(positioned), tuple(findings)


def composite_m01_assays(
    data: M01Data,
    trajectories: tuple[HoleTrajectory, ...],
    target_length_m: float = TARGET_LENGTH_M,
) -> CompositingResult:
    """Split at contacts, composite inside lithology runs and add XYZ."""
    segments, split_findings = split_assays_at_contacts(data)
    composites = composite_segments(segments, target_length_m)
    positioned, position_findings = position_composites(composites, trajectories)
    return CompositingResult(
        segments=segments,
        composites=positioned,
        findings=split_findings + position_findings,
    )


def summarize_compositing(data: M01Data, result: CompositingResult) -> dict[str, object]:
    """Return mining-validation figures: meters, counts, lengths and Cu means."""
    assay_meters = 0.0
    assay_weighted = 0.0
    valid_assays = 0
    for record in data.assay.records:
        start = _finite_number(record.get("from_m"))
        end = _finite_number(record.get("to_m"))
        cu_pct = _finite_number(record.get("cu_pct"))
        if start is None or end is None or cu_pct is None or start >= end:
            continue
        valid_assays += 1
        assay_meters += end - start
        assay_weighted += cu_pct * (end - start)

    composite_meters = sum(c.length_m for c in result.composites)
    composite_weighted = sum(c.cu_pct * c.length_m for c in result.composites)
    by_lith: dict[str, int] = defaultdict(int)
    length_counts: dict[float, int] = defaultdict(int)
    for composite in result.composites:
        by_lith[composite.lith_code] += 1
        length_counts[round(composite.length_m, 3)] += 1

    return {
        "assay_records": len(data.assay.records),
        "assay_valid_records": valid_assays,
        "assay_meters": assay_meters,
        "segments_after_contact_split": len(result.segments),
        "composites": len(result.composites),
        "composite_meters": composite_meters,
        "meters_difference": composite_meters - assay_meters,
        "target_length_composites": sum(1 for c in result.composites if not c.residual_flag),
        "residual_composites": sum(1 for c in result.composites if c.residual_flag),
        "composites_without_xyz": sum(1 for c in result.composites if c.x is None),
        "cu_weighted_mean_assay": assay_weighted / assay_meters if assay_meters else None,
        "cu_weighted_mean_composites": (
            composite_weighted / composite_meters if composite_meters else None
        ),
        "composites_by_lith_code": dict(sorted(by_lith.items())),
        "length_distribution_m": dict(sorted(length_counts.items())),
        "findings": len(result.findings),
    }


def write_composites_csv(
    composites: tuple[Composite, ...],
    path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Write composites to a derived CSV; never touches data/raw."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for composite in composites:
            writer.writerow(
                [
                    composite.hole_id,
                    f"{composite.from_m:.9f}",
                    f"{composite.to_m:.9f}",
                    f"{composite.length_m:.9f}",
                    f"{composite.mid_m:.9f}",
                    _format_optional(composite.x),
                    _format_optional(composite.y),
                    _format_optional(composite.z),
                    composite.lith_code,
                    f"{composite.cu_pct:.9f}",
                    str(composite.residual_flag),
                    composite.n_pieces,
                ]
            )
    return output


def run_m01b_compositing(
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> tuple[CompositingResult, dict[str, object]]:
    """Load, validate, desurvey, composite and write the default M01 release."""
    data = load_m01_data()
    report = validate_m01_data(data)
    desurvey = desurvey_m01_data(data, report)
    result = composite_m01_assays(data, desurvey.trajectories)
    write_composites_csv(result.composites, output_path)
    return result, summarize_compositing(data, result)


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.9f}"


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


def _finding(
    rule_id: str,
    table: str,
    row_number: int,
    record: TableRecord,
    field: str,
    observed_value: str,
    expected_condition: str,
) -> ValidationFinding:
    return ValidationFinding(
        rule_id=rule_id,
        severity="ERROR",
        table=table,
        row_number=row_number,
        hole_id=_text(record.get("hole_id")),
        sample_id=_text(record.get("sample_id")),
        field=field,
        observed_value=observed_value,
        expected_condition=expected_condition,
    )


if __name__ == "__main__":
    _result, _summary = run_m01b_compositing()
    for _key, _value in _summary.items():
        print(f"{_key}: {_value}")
