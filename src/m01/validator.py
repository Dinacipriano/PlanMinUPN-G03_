"""Validate loaded M01 source tables and report traceable findings."""

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Callable, Literal

from src.m01.loader import LoadedTable, M01Data, TableRecord


Severity = Literal["ERROR", "WARNING", "INFO"]


@dataclass(frozen=True)
class ValidationFinding:
    """One observed violation or descriptive validation result."""

    rule_id: str
    severity: Severity
    table: str
    row_number: int | None
    hole_id: str | None
    sample_id: str | None
    field: str | None
    observed_value: str | float | None
    expected_condition: str

    @property
    def blocking(self) -> bool:
        return self.severity == "ERROR"

    @property
    def requires_review(self) -> bool:
        return self.severity == "WARNING"


@dataclass(frozen=True)
class ValidationReport:
    """Findings from one validation run."""

    findings: tuple[ValidationFinding, ...]

    @property
    def error_count(self) -> int:
        return sum(finding.severity == "ERROR" for finding in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(finding.severity == "WARNING" for finding in self.findings)

    @property
    def info_count(self) -> int:
        return sum(finding.severity == "INFO" for finding in self.findings)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0


_INTERVAL_TABLES = ("lithology", "alteration", "assay", "density")
_REQUIRED_FIELDS = {
    "collar": (
        "hole_id", "dataset_id", "project_id", "campaign_id", "x", "y", "z",
        "azimuth_deg", "dip_deg", "final_depth_m",
    ),
    "survey": (
        "hole_id", "dataset_id", "project_id", "campaign_id", "depth_m",
        "azimuth_deg", "dip_deg",
    ),
    "lithology": (
        "hole_id", "dataset_id", "project_id", "campaign_id", "from_m",
        "to_m", "length_m", "lith_code",
    ),
    "alteration": (
        "hole_id", "dataset_id", "project_id", "campaign_id", "from_m",
        "to_m", "length_m", "alteration_code", "alteration_intensity",
    ),
    "assay": (
        "sample_id", "hole_id", "dataset_id", "project_id", "campaign_id",
        "from_m", "to_m", "length_m", "cu_pct", "mo_pct", "au_gt",
    ),
    "density": (
        "density_sample_id", "hole_id", "dataset_id", "project_id",
        "campaign_id", "from_m", "to_m", "length_m", "density_t_m3",
    ),
}
_METADATA_FIELDS = ("dataset_id", "project_id", "campaign_id")
_SAMPLE_ID_FIELDS = {"assay": "sample_id", "density": "density_sample_id"}
_FindingAdder = Callable[..., None]


def validate_m01_data(data: M01Data) -> ValidationReport:
    """Apply documented M01 checks to loaded tables without changing them.

    Numeric tolerances and engineering thresholds that have not been approved
    are intentionally not applied.
    """
    findings: list[ValidationFinding] = []
    tables = {
        "collar": data.collar,
        "survey": data.survey,
        "lithology": data.lithology,
        "alteration": data.alteration,
        "assay": data.assay,
        "density": data.density,
    }

    def add(
        rule_id: str,
        severity: Severity,
        table: str,
        row_number: int | None = None,
        record: TableRecord | None = None,
        field: str | None = None,
        observed_value: str | float | None = None,
        expected_condition: str = "",
    ) -> None:
        record = record or {}
        findings.append(
            ValidationFinding(
                rule_id=rule_id,
                severity=severity,
                table=table,
                row_number=row_number,
                hole_id=_optional_text(record.get("hole_id")),
                sample_id=_sample_id(table, record),
                field=field,
                observed_value=observed_value,
                expected_condition=expected_condition,
            )
        )

    collar_by_hole: dict[str, tuple[int, TableRecord]] = {}
    collar_records = data.collar.records

    for index, record in enumerate(collar_records):
        row_number = index + 2
        hole_id = _optional_text(record.get("hole_id"))
        _check_required_values(
            add, "collar", record, row_number, _REQUIRED_FIELDS["collar"]
        )

        if hole_id is not None:
            if hole_id in collar_by_hole:
                add(
                    "COLLAR-001",
                    "ERROR",
                    "collar",
                    row_number,
                    record,
                    "hole_id",
                    hole_id,
                    "hole_id is unique in collar",
                )
            else:
                collar_by_hole[hole_id] = (row_number, record)

        for field in ("x", "y", "z", "azimuth_deg", "dip_deg", "final_depth_m"):
            value = record.get(field)
            if not _is_missing(value) and not _is_finite_number(value):
                add(
                    "COLLAR-002",
                    "ERROR",
                    "collar",
                    row_number,
                    record,
                    field,
                    _display_value(value),
                    "required coordinate and numeric values are finite numbers",
                )

        depth = _number(record.get("final_depth_m"))
        if depth is not None and depth <= 0:
            add(
                "COLLAR-003",
                "ERROR",
                "collar",
                row_number,
                record,
                "final_depth_m",
                depth,
                "final_depth_m is greater than zero",
            )

        _check_orientation_ranges(add, "collar", row_number, record)

    _check_duplicate_collar_positions(add, collar_records)

    survey_by_hole: dict[str, list[tuple[int, TableRecord]]] = defaultdict(list)
    for index, record in enumerate(data.survey.records):
        row_number = index + 2
        _check_required_values(
            add, "survey", record, row_number, _REQUIRED_FIELDS["survey"]
        )
        hole_id = _optional_text(record.get("hole_id"))
        if hole_id is not None:
            if hole_id not in collar_by_hole:
                add(
                    "SURVEY-001",
                    "ERROR",
                    "survey",
                    row_number,
                    record,
                    "hole_id",
                    hole_id,
                    "survey.hole_id exists in collar.hole_id",
                )
            survey_by_hole[hole_id].append((row_number, record))

        depth = record.get("depth_m")
        if not _is_missing(depth) and (
            not _is_finite_number(depth)
            or (isinstance(depth, (int, float)) and depth < 0)
        ):
            add(
                "SURVEY-002",
                "ERROR",
                "survey",
                row_number,
                record,
                "depth_m",
                _display_value(depth),
                "depth_m is a finite number greater than or equal to zero",
            )

        for field in ("azimuth_deg", "dip_deg"):
            value = record.get(field)
            if not _is_missing(value) and not _is_finite_number(value):
                add(
                    "SURVEY-003",
                    "ERROR",
                    "survey",
                    row_number,
                    record,
                    field,
                    _display_value(record.get(field)),
                    "orientation values are finite numbers",
                )
        _check_orientation_ranges(add, "survey", row_number, record)

        if hole_id in collar_by_hole:
            final_depth = _number(collar_by_hole[hole_id][1].get("final_depth_m"))
            survey_depth = _number(depth)
            if final_depth is not None and survey_depth is not None and survey_depth > final_depth:
                add(
                    "SURVEY-004",
                    "ERROR",
                    "survey",
                    row_number,
                    record,
                    "depth_m",
                    survey_depth,
                    "survey.depth_m does not exceed collar.final_depth_m",
                )

    for hole_id, (collar_row, collar) in collar_by_hole.items():
        stations = survey_by_hole.get(hole_id, [])
        if not stations:
            add(
                "SURVEY-005",
                "ERROR",
                "collar",
                collar_row,
                collar,
                "hole_id",
                hole_id,
                "each collar has survey records for the M01 desurvey input",
            )
            continue

        if not any(_number(station.get("depth_m")) == 0 for _, station in stations):
            add(
                "SURVEY-006",
                "ERROR",
                "survey",
                None,
                collar,
                "depth_m",
                "NO_ZERO_DEPTH_STATION",
                "each surveyed hole has an orientation station at depth_m = 0",
            )

        _check_survey_order(add, hole_id, stations)
        _check_duplicate_survey_stations(add, hole_id, stations)
        _check_initial_orientation(add, collar, stations)
        _check_survey_end_coverage(add, hole_id, collar, stations)

    _check_secondary_relationships(add, tables, collar_by_hole)
    _check_metadata_consistency(add, tables, collar_by_hole)
    _check_manifest_campaigns(add, data, collar_records)

    if not data.alteration.records:
        add(
            "ALTERATION-001",
            "INFO",
            "alteration",
            field="records",
            observed_value=0,
            expected_condition="record the observed row count; no alteration records are present",
        )

    for table_name in _INTERVAL_TABLES:
        _check_interval_table(
            add,
            table_name,
            tables[table_name],
            collar_by_hole,
        )

    _check_assay_values(add, data.assay)
    _check_density_values(add, data.density)

    return ValidationReport(tuple(findings))


def _check_required_values(
    add: _FindingAdder,
    table: str,
    record: TableRecord,
    row_number: int,
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            add(
                f"{table.upper()}-REQ-001",
                "ERROR",
                table,
                row_number,
                record,
                field,
                _display_value(value),
                "required source field is present and non-blank",
            )


def _check_duplicate_collar_positions(
    add: _FindingAdder,
    records: list[TableRecord],
) -> None:
    seen: dict[tuple[float, float, float], tuple[int, TableRecord]] = {}
    for index, record in enumerate(records):
        coordinates = tuple(_number(record.get(field)) for field in ("x", "y", "z"))
        if any(value is None for value in coordinates):
            continue
        key = (coordinates[0], coordinates[1], coordinates[2])
        if key in seen:
            add(
                "COLLAR-008",
                "WARNING",
                "collar",
                index + 2,
                record,
                "x,y,z",
                repr(key),
                "review repeated collar coordinates; do not assume they are invalid",
            )
        else:
            seen[key] = (index + 2, record)


def _check_orientation_ranges(
    add: _FindingAdder,
    table: str,
    row_number: int,
    record: TableRecord,
) -> None:
    collar_rule_prefix = table == "collar"
    azimuth = _number(record.get("azimuth_deg"))
    if azimuth is not None and not 0 <= azimuth < 360:
        add(
            f"{table.upper()}-{6 if collar_rule_prefix else 5:03d}",
            "ERROR",
            table,
            row_number,
            record,
            "azimuth_deg",
            azimuth,
            "azimuth_deg is in [0, 360) degrees",
        )

    dip = _number(record.get("dip_deg"))
    if dip is not None and not -90 <= dip <= 0:
        add(
            f"{table.upper()}-{7 if collar_rule_prefix else 6:03d}",
            "ERROR",
            table,
            row_number,
            record,
            "dip_deg",
            dip,
            "dip_deg is in [-90, 0] degrees",
        )


def _check_survey_order(
    add: _FindingAdder,
    hole_id: str,
    stations: list[tuple[int, TableRecord]],
) -> None:
    previous_depth: float | None = None
    for row_number, record in stations:
        depth = _number(record.get("depth_m"))
        if depth is None:
            continue
        if previous_depth is not None and depth < previous_depth:
            add(
                "SURVEY-007",
                "WARNING",
                "survey",
                row_number,
                record,
                "depth_m",
                depth,
                f"survey stations for hole_id {hole_id!r} are ordered by non-decreasing depth",
            )
        previous_depth = depth


def _check_duplicate_survey_stations(
    add: _FindingAdder,
    hole_id: str,
    stations: list[tuple[int, TableRecord]],
) -> None:
    by_depth: dict[float, list[tuple[int, TableRecord]]] = defaultdict(list)
    for row_number, record in stations:
        depth = _number(record.get("depth_m"))
        if depth is not None:
            by_depth[depth].append((row_number, record))

    for depth, duplicates in by_depth.items():
        if len(duplicates) < 2:
            continue
        orientations = {
            (_number(record.get("azimuth_deg")), _number(record.get("dip_deg")))
            for _, record in duplicates
        }
        severity: Severity = "ERROR" if len(orientations) > 1 else "WARNING"
        expected = (
            "one unambiguous orientation per hole_id and depth_m"
            if severity == "ERROR"
            else "review duplicate survey stations at the same hole_id and depth_m"
        )
        for row_number, record in duplicates[1:]:
            add(
                "SURVEY-008",
                severity,
                "survey",
                row_number,
                record,
                "depth_m",
                depth,
                expected,
            )


def _check_initial_orientation(
    add: _FindingAdder,
    collar: TableRecord,
    stations: list[tuple[int, TableRecord]],
) -> None:
    zero_stations = [
        (row_number, station)
        for row_number, station in stations
        if _number(station.get("depth_m")) == 0
    ]
    if not zero_stations:
        return

    row_number, station = zero_stations[0]
    for field in ("azimuth_deg", "dip_deg"):
        collar_value = _number(collar.get(field))
        survey_value = _number(station.get(field))
        if collar_value is not None and survey_value is not None and collar_value != survey_value:
            add(
                "SURVEY-009",
                "WARNING",
                "survey",
                row_number,
                station,
                field,
                survey_value,
                f"review difference from collar.{field} at depth_m = 0; no tolerance is applied",
            )


def _check_survey_end_coverage(
    add: _FindingAdder,
    hole_id: str,
    collar: TableRecord,
    stations: list[tuple[int, TableRecord]],
) -> None:
    valid_stations: list[tuple[int, float, TableRecord]] = []
    for row_number, record in stations:
        depth = _number(record.get("depth_m"))
        if depth is not None:
            valid_stations.append((row_number, depth, record))
    if not valid_stations:
        return

    row_number, maximum_depth, record = max(valid_stations, key=lambda item: item[1])
    final_depth = _number(collar.get("final_depth_m"))
    if maximum_depth is not None and final_depth is not None and maximum_depth != final_depth:
        add(
            "SURVEY-010",
            "INFO",
            "survey",
            row_number,
            record,
            "depth_m",
            maximum_depth,
            f"record maximum survey depth for hole_id {hole_id!r}; equality with final_depth_m is not assumed",
        )


def _check_secondary_relationships(
    add: _FindingAdder,
    tables: dict[str, LoadedTable],
    collar_by_hole: dict[str, tuple[int, TableRecord]],
) -> None:
    for table_name in _INTERVAL_TABLES:
        for index, record in enumerate(tables[table_name].records):
            hole_id = _optional_text(record.get("hole_id"))
            if hole_id is not None and hole_id not in collar_by_hole:
                add(
                    f"{table_name.upper()}-REL-001",
                    "ERROR",
                    table_name,
                    index + 2,
                    record,
                    "hole_id",
                    hole_id,
                    f"{table_name}.hole_id exists in collar.hole_id",
                )

    holes_with_assay = {
        hole_id
        for record in tables["assay"].records
        if (hole_id := _optional_text(record.get("hole_id"))) is not None
    }
    for hole_id, (row_number, record) in collar_by_hole.items():
        if hole_id not in holes_with_assay:
            add(
                "ASSAY-002",
                "WARNING",
                "collar",
                row_number,
                record,
                "hole_id",
                hole_id,
                "review collar without assay records; assay coverage is not required for geometry",
            )


def _check_metadata_consistency(
    add: _FindingAdder,
    tables: dict[str, LoadedTable],
    collar_by_hole: dict[str, tuple[int, TableRecord]],
) -> None:
    for table_name in ("survey", *_INTERVAL_TABLES):
        for index, record in enumerate(tables[table_name].records):
            hole_id = _optional_text(record.get("hole_id"))
            if hole_id not in collar_by_hole:
                continue
            collar = collar_by_hole[hole_id][1]
            for field in _METADATA_FIELDS:
                observed = _optional_text(record.get(field))
                expected = _optional_text(collar.get(field))
                if observed is not None and expected is not None and observed != expected:
                    add(
                        f"{table_name.upper()}-002",
                        "ERROR",
                        table_name,
                        index + 2,
                        record,
                        field,
                        observed,
                        f"value matches collar.{field} for the related hole",
                    )


def _check_manifest_campaigns(
    add: _FindingAdder,
    data: M01Data,
    collar_records: list[TableRecord],
) -> None:
    manifest_campaigns = data.release_manifest.get("campaigns")
    if not isinstance(manifest_campaigns, list):
        return
    manifest_values = {str(value) for value in manifest_campaigns}
    source_values = {
        value
        for record in collar_records
        if (value := _optional_text(record.get("campaign_id"))) is not None
    }
    if manifest_values and source_values and manifest_values != source_values:
        add(
            "RELEASE-001",
            "WARNING",
            "release_manifest.json",
            field="campaigns",
            observed_value=", ".join(sorted(source_values)),
            expected_condition=(
                "review campaign naming difference between release_manifest.json "
                f"({', '.join(sorted(manifest_values))}) and collar.csv"
            ),
        )


def _check_interval_table(
    add: _FindingAdder,
    table_name: str,
    table: LoadedTable,
    collar_by_hole: dict[str, tuple[int, TableRecord]],
) -> None:
    intervals_by_hole: dict[str, list[tuple[int, TableRecord, float, float]]] = defaultdict(list)
    seen_rows: set[tuple[tuple[str, str], ...]] = set()
    id_field = _SAMPLE_ID_FIELDS.get(table_name)
    seen_ids: set[str] = set()

    for index, record in enumerate(table.records):
        row_number = index + 2
        _check_required_values(
            add, table_name, record, row_number, _REQUIRED_FIELDS[table_name]
        )

        canonical_row = tuple(sorted((key, repr(value)) for key, value in record.items()))
        if canonical_row in seen_rows:
            add(
                f"{table_name.upper()}-003",
                "ERROR",
                table_name,
                row_number,
                record,
                observed_value="DUPLICATE_ROW",
                expected_condition="source records are not exact duplicates",
            )
        seen_rows.add(canonical_row)

        if id_field is not None:
            sample_id = _optional_text(record.get(id_field))
            if sample_id is not None:
                if sample_id in seen_ids:
                    add(
                        f"{table_name.upper()}-004",
                        "ERROR",
                        table_name,
                        row_number,
                        record,
                        id_field,
                        sample_id,
                        f"{id_field} is unique in {table_name}",
                    )
                seen_ids.add(sample_id)

        start = _number(record.get("from_m"))
        end = _number(record.get("to_m"))
        length = _number(record.get("length_m"))
        numeric_fields = ("from_m", "to_m", "length_m")
        invalid_numeric_fields = [
            field
            for field in numeric_fields
            if not _is_missing(record.get(field))
            and not _is_finite_number(record.get(field))
        ]
        if invalid_numeric_fields:
            add(
                f"{table_name.upper()}-005",
                "ERROR",
                table_name,
                row_number,
                record,
                ",".join(invalid_numeric_fields),
                "NON_FINITE_OR_MISSING",
                "interval depths and length are finite numbers",
            )
            continue

        if any(_is_missing(record.get(field)) for field in numeric_fields):
            continue

        if start is None or end is None or length is None:
            continue
        if start >= end:
            add(
                f"{table_name.upper()}-006",
                "ERROR",
                table_name,
                row_number,
                record,
                "from_m,to_m",
                f"{start},{end}",
                "from_m is less than to_m",
            )
            continue
        if start < 0:
            add(
                f"{table_name.upper()}-007",
                "ERROR",
                table_name,
                row_number,
                record,
                "from_m",
                start,
                "from_m is greater than or equal to zero",
            )

        hole_id = _optional_text(record.get("hole_id"))
        if hole_id in collar_by_hole:
            final_depth = _number(collar_by_hole[hole_id][1].get("final_depth_m"))
            if final_depth is not None and end > final_depth:
                add(
                    f"{table_name.upper()}-008",
                    "ERROR",
                    table_name,
                    row_number,
                    record,
                    "to_m",
                    end,
                    "to_m does not exceed collar.final_depth_m",
                )
        if hole_id is not None:
            intervals_by_hole[hole_id].append((row_number, record, start, end))

    for hole_id, intervals in intervals_by_hole.items():
        ordered = sorted(intervals, key=lambda item: (item[2], item[3], item[0]))
        furthest_end: float | None = None
        for current in ordered:
            if furthest_end is not None and current[2] < furthest_end:
                add(
                    f"{table_name.upper()}-009",
                    "ERROR",
                    table_name,
                    current[0],
                    current[1],
                    "from_m,to_m",
                    f"{current[2]},{current[3]}",
                    f"intervals do not overlap within hole_id {hole_id!r}",
                )
            if (
                table_name == "density"
                and furthest_end is not None
                and current[2] > furthest_end
            ):
                add(
                    "DENSITY-010",
                    "INFO",
                    table_name,
                    current[0],
                    current[1],
                    "from_m,to_m",
                    f"{furthest_end},{current[2]}",
                    "record the observed gap between sparse density intervals; no spacing threshold is applied",
                )
            furthest_end = max(furthest_end or current[3], current[3])

    if table_name == "density":
        holes_with_density = set(intervals_by_hole)
        for hole_id, (row_number, collar) in collar_by_hole.items():
            if hole_id not in holes_with_density:
                add(
                    "DENSITY-011",
                    "INFO",
                    "collar",
                    row_number,
                    collar,
                    "hole_id",
                    hole_id,
                    "record collar without density samples; no coverage requirement is assumed",
                )


def _check_assay_values(add: _FindingAdder, table: LoadedTable) -> None:
    for index, record in enumerate(table.records):
        for field in ("cu_pct", "mo_pct", "au_gt"):
            value = record.get(field)
            if _is_missing(value):
                continue
            numeric_value = _number(value)
            if numeric_value is None:
                add(
                    "ASSAY-003",
                    "ERROR",
                    "assay",
                    index + 2,
                    record,
                    field,
                    _display_value(value),
                    "assay value is a finite number",
                )
            elif numeric_value < 0:
                add(
                    "ASSAY-004",
                    "WARNING",
                    "assay",
                    index + 2,
                    record,
                    field,
                    numeric_value,
                    "review negative assay value; its analytical convention is undocumented",
                )

    for field in ("cu_pct", "mo_pct", "au_gt"):
        zero_count = sum(record.get(field) == 0 for record in table.records)
        if zero_count:
            add(
                "ASSAY-005",
                "INFO",
                "assay",
                field=field,
                observed_value=f"0 in {zero_count} records",
                expected_condition="record zero values without assigning undocumented analytical meaning",
            )


def _check_density_values(add: _FindingAdder, table: LoadedTable) -> None:
    for index, record in enumerate(table.records):
        value = record.get("density_t_m3")
        if _is_missing(value):
            continue
        numeric_value = _number(value)
        if numeric_value is None or numeric_value <= 0:
            add(
                "DENSITY-001",
                "ERROR",
                "density",
                index + 2,
                record,
                "density_t_m3",
                _display_value(value),
                "density_t_m3 is a finite number greater than zero",
            )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _is_finite_number(value: object) -> bool:
    return _number(value) is not None


def _display_value(value: object) -> str | float | None:
    if value is None or isinstance(value, (str, float)):
        return value
    if isinstance(value, int):
        return float(value)
    return str(value)


def _sample_id(table: str, record: TableRecord) -> str | None:
    field = _SAMPLE_ID_FIELDS.get(table)
    return _optional_text(record.get(field)) if field is not None else None
