"""Load source data required by M01."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast


class CollarRecord(TypedDict):
    hole_id: str
    dataset_id: str
    project_id: str
    campaign_id: str
    x: float
    y: float
    z: float
    azimuth_deg: float
    dip_deg: float
    final_depth_m: float


TableRecord = dict[str, str | float]


@dataclass
class LoadedTable:
    """CSV header and rows; an empty table retains its source columns."""

    columns: tuple[str, ...]
    records: list[TableRecord]


@dataclass
class M01Data:
    """Raw release inputs loaded for M01 processing and visualization."""

    collar: LoadedTable
    survey: LoadedTable
    lithology: LoadedTable
    alteration: LoadedTable
    assay: LoadedTable
    density: LoadedTable
    data_dictionary: LoadedTable
    release_manifest: dict[str, object]
    readme: str


class LoaderError(Exception):
    """Raised when a source file cannot be loaded or parsed."""


COLLAR_COLUMNS = (
    "hole_id",
    "dataset_id",
    "project_id",
    "campaign_id",
    "x",
    "y",
    "z",
    "azimuth_deg",
    "dip_deg",
    "final_depth_m",
)

TABLE_SCHEMAS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "collar.csv": (
        COLLAR_COLUMNS,
        ("x", "y", "z", "azimuth_deg", "dip_deg", "final_depth_m"),
    ),
    "survey.csv": (
        (
            "hole_id",
            "dataset_id",
            "project_id",
            "campaign_id",
            "depth_m",
            "azimuth_deg",
            "dip_deg",
        ),
        ("depth_m", "azimuth_deg", "dip_deg"),
    ),
    "lithology.csv": (
        (
            "hole_id",
            "dataset_id",
            "project_id",
            "campaign_id",
            "from_m",
            "to_m",
            "length_m",
            "lith_code",
        ),
        ("from_m", "to_m", "length_m"),
    ),
    "alteration.csv": (
        (
            "hole_id",
            "dataset_id",
            "project_id",
            "campaign_id",
            "from_m",
            "to_m",
            "length_m",
            "alteration_code",
            "alteration_intensity",
        ),
        ("from_m", "to_m", "length_m"),
    ),
    "assay.csv": (
        (
            "sample_id",
            "hole_id",
            "dataset_id",
            "project_id",
            "campaign_id",
            "from_m",
            "to_m",
            "length_m",
            "cu_pct",
            "mo_pct",
            "au_gt",
        ),
        ("from_m", "to_m", "length_m", "cu_pct", "mo_pct", "au_gt"),
    ),
    "density.csv": (
        (
            "density_sample_id",
            "hole_id",
            "dataset_id",
            "project_id",
            "campaign_id",
            "from_m",
            "to_m",
            "length_m",
            "density_t_m3",
        ),
        ("from_m", "to_m", "length_m", "density_t_m3"),
    ),
    "data_dictionary.csv": (
        ("file", "column", "description", "unit", "dtype", "nullable"),
        (),
    ),
}

DEFAULT_RAW_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "raw"


def _load_csv_table(
    path: Path,
    required_columns: tuple[str, ...],
    numeric_columns: tuple[str, ...],
) -> LoadedTable:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            headers = reader.fieldnames
            if headers is None:
                raise LoaderError(f"{path}: missing CSV header")
            if len(headers) != len(set(headers)):
                raise LoaderError(f"{path}: duplicate column names in header")

            missing_columns = [column for column in required_columns if column not in headers]
            if missing_columns:
                raise LoaderError(
                    f"{path}: missing required columns: {', '.join(missing_columns)}"
                )

            records: list[TableRecord] = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise LoaderError(
                        f"{path}: row {row_number} has more values than the header"
                    )

                record: TableRecord = {}
                for column in headers:
                    value = row[column]
                    if value is None:
                        raise LoaderError(
                            f"{path}: row {row_number}, column {column!r} is missing"
                        )

                    if column in numeric_columns:
                        try:
                            record[column] = float(value)
                        except ValueError as error:
                            raise LoaderError(
                                f"{path}: row {row_number}, column {column!r} "
                                f"cannot be converted to a number: {value!r}"
                            ) from error
                    else:
                        record[column] = value

                records.append(record)

    except OSError as error:
        raise LoaderError(f"Cannot read source file {path}: {error}") from error
    except csv.Error as error:
        raise LoaderError(f"Cannot parse CSV file {path}: {error}") from error

    return LoadedTable(tuple(headers), records)


def load_collar(path: str | Path = DEFAULT_RAW_DIRECTORY / "collar.csv") -> list[CollarRecord]:
    """Load collar rows while preserving the established loader interface."""
    table = _load_csv_table(Path(path), *TABLE_SCHEMAS["collar.csv"])
    return [cast(CollarRecord, record) for record in table.records]


def load_m01_data(raw_directory: str | Path = DEFAULT_RAW_DIRECTORY) -> M01Data:
    """Load every release source table required by the M01 flow.

    CSV/schema parsing and numeric conversion happen here. Mining validation
    such as duplicate IDs, physical ranges, and cross-table relationships
    belongs in ``validator.py``.
    """
    raw_path = Path(raw_directory)
    tables = {
        filename: _load_csv_table(
            raw_path / filename,
            required_columns,
            numeric_columns,
        )
        for filename, (required_columns, numeric_columns) in TABLE_SCHEMAS.items()
    }

    manifest_path = raw_path / "release_manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8-sig") as manifest_file:
            manifest = json.load(manifest_file)
    except (OSError, json.JSONDecodeError) as error:
        raise LoaderError(f"Cannot read release manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict):
        raise LoaderError(f"{manifest_path}: expected a JSON object")

    readme_path = raw_path / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise LoaderError(f"Cannot read release README {readme_path}: {error}") from error

    return M01Data(
        collar=tables["collar.csv"],
        survey=tables["survey.csv"],
        lithology=tables["lithology.csv"],
        alteration=tables["alteration.csv"],
        assay=tables["assay.csv"],
        density=tables["density.csv"],
        data_dictionary=tables["data_dictionary.csv"],
        release_manifest=cast(dict[str, object], manifest),
        readme=readme,
    )
