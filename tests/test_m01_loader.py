import csv
import tempfile
import unittest
from pathlib import Path

from src.m01.loader import (
    COLLAR_COLUMNS,
    LoaderError,
    load_collar,
    load_m01_data,
)


class LoadCollarTests(unittest.TestCase):
    def test_loads_release_collar_and_converts_numeric_columns(self) -> None:
        records = load_collar()

        self.assertEqual(len(records), 32)
        self.assertEqual(records[0]["hole_id"], "CA-C01-001")
        self.assertEqual(records[0]["dataset_id"], "DS01")
        self.assertIsInstance(records[0]["x"], float)
        self.assertIsInstance(records[0]["final_depth_m"], float)
        self.assertEqual(records[0]["x"], 242263.825802219)

    def test_rejects_missing_required_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collar.csv"
            path.write_text("hole_id,x\nH-01,1\n", encoding="utf-8")

            with self.assertRaisesRegex(LoaderError, "missing required columns"):
                load_collar(path)

    def test_reports_numeric_conversion_error_with_row_and_field(self) -> None:
        row = {column: "1" for column in COLLAR_COLUMNS}
        row.update({"hole_id": "H-01", "x": "not-a-number"})

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collar.csv"
            with path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=COLLAR_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

            with self.assertRaisesRegex(
                LoaderError, r"row 2, column 'x'.*cannot be converted"
            ):
                load_collar(path)

    def test_reports_missing_numeric_value(self) -> None:
        row = {column: "1" for column in COLLAR_COLUMNS}
        row.update({"hole_id": "H-01", "x": ""})

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collar.csv"
            with path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=COLLAR_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

            with self.assertRaisesRegex(LoaderError, r"column 'x'.*cannot be converted"):
                load_collar(path)


class LoadM01DataTests(unittest.TestCase):
    def test_loads_all_release_tables_and_metadata(self) -> None:
        data = load_m01_data()

        self.assertEqual(len(data.collar.records), 32)
        self.assertEqual(len(data.survey.records), 208)
        self.assertEqual(len(data.lithology.records), 95)
        self.assertEqual(len(data.alteration.records), 0)
        self.assertEqual(len(data.assay.records), 3619)
        self.assertEqual(len(data.density.records), 290)
        self.assertEqual(len(data.data_dictionary.records), 54)
        self.assertEqual(data.release_manifest["dataset_id"], "DS01")
        self.assertIn("Cerro Azul", data.readme)

    def test_converts_numeric_values_and_preserves_text_values(self) -> None:
        data = load_m01_data()

        self.assertIsInstance(data.survey.records[0]["depth_m"], float)
        self.assertIsInstance(data.assay.records[0]["cu_pct"], float)
        self.assertIsInstance(data.density.records[0]["density_t_m3"], float)
        self.assertIsInstance(data.lithology.records[0]["lith_code"], str)
        self.assertEqual(data.data_dictionary.records[0]["unit"], "")

    def test_empty_alteration_table_preserves_source_columns(self) -> None:
        data = load_m01_data()

        self.assertIn("alteration_code", data.alteration.columns)
        self.assertIn("alteration_intensity", data.alteration.columns)
        self.assertEqual(data.alteration.records, [])


if __name__ == "__main__":
    unittest.main()
