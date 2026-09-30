import copy
import unittest

from src.m01.loader import LoadedTable, M01Data, TableRecord, load_m01_data
from src.m01.validator import ValidationReport, validate_m01_data


def _table(records: list[TableRecord]) -> LoadedTable:
    columns = tuple(records[0]) if records else ()
    return LoadedTable(columns, records)


def _fixture_data() -> M01Data:
    collar = {
        "hole_id": "H-01",
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "x": 100.0,
        "y": 200.0,
        "z": 300.0,
        "azimuth_deg": 0.0,
        "dip_deg": -90.0,
        "final_depth_m": 10.0,
    }
    survey = [
        {
            "hole_id": "H-01",
            "dataset_id": "DS-01",
            "project_id": "P-01",
            "campaign_id": "C-01",
            "depth_m": 0.0,
            "azimuth_deg": 0.0,
            "dip_deg": -90.0,
        },
        {
            "hole_id": "H-01",
            "dataset_id": "DS-01",
            "project_id": "P-01",
            "campaign_id": "C-01",
            "depth_m": 10.0,
            "azimuth_deg": 0.0,
            "dip_deg": -90.0,
        },
    ]
    assay = [
        {
            "sample_id": "S-01",
            "hole_id": "H-01",
            "dataset_id": "DS-01",
            "project_id": "P-01",
            "campaign_id": "C-01",
            "from_m": 0.0,
            "to_m": 10.0,
            "length_m": 10.0,
            "cu_pct": 0.2,
            "mo_pct": 0.0,
            "au_gt": 0.0,
        }
    ]
    interval_metadata = {
        "hole_id": "H-01",
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
    }
    lithology = [
        {
            **interval_metadata,
            "from_m": 0.0,
            "to_m": 10.0,
            "length_m": 10.0,
            "lith_code": "L-01",
        }
    ]
    density = [
        {
            "density_sample_id": "D-01",
            **interval_metadata,
            "from_m": 0.0,
            "to_m": 1.0,
            "length_m": 1.0,
            "density_t_m3": 2.5,
        }
    ]

    return M01Data(
        collar=_table([collar]),
        survey=_table(survey),
        lithology=_table(lithology),
        alteration=LoadedTable(
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
            [],
        ),
        assay=_table(assay),
        density=_table(density),
        data_dictionary=LoadedTable((), []),
        release_manifest={"campaigns": ["C-01"]},
        readme="",
    )


class ValidateM01DataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _fixture_data()

    def test_valid_fixture_has_no_errors_or_warnings(self) -> None:
        report = validate_m01_data(self.data)

        self.assertIsInstance(report, ValidationReport)
        self.assertFalse(report.has_errors)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.info_count, 3)

    def test_reports_out_of_range_survey_orientation_with_location(self) -> None:
        self.data.survey.records[0]["azimuth_deg"] = 360.1

        findings = validate_m01_data(self.data).findings
        finding = next(item for item in findings if item.rule_id == "SURVEY-005")

        self.assertEqual(finding.severity, "ERROR")
        self.assertEqual(finding.table, "survey")
        self.assertEqual(finding.row_number, 2)
        self.assertEqual(finding.hole_id, "H-01")
        self.assertEqual(finding.field, "azimuth_deg")
        self.assertEqual(finding.observed_value, 360.1)
        self.assertTrue(finding.blocking)

    def test_accepts_azimuth_zero_and_values_below_360_in_collar_and_survey(self) -> None:
        self.data.collar.records[0]["azimuth_deg"] = 0.0
        for station in self.data.survey.records:
            station["azimuth_deg"] = 359.999

        findings = validate_m01_data(self.data).findings

        self.assertFalse(
            any(item.rule_id in {"COLLAR-006", "SURVEY-005"} for item in findings)
        )

    def test_rejects_azimuth_outside_half_open_range(self) -> None:
        self.data.collar.records[0]["azimuth_deg"] = -0.1
        self.data.survey.records[0]["azimuth_deg"] = 360.0

        findings = validate_m01_data(self.data).findings

        range_findings = [
            item
            for item in findings
            if item.rule_id in {"COLLAR-006", "SURVEY-005"}
        ]
        self.assertEqual(
            {(item.table, item.observed_value) for item in range_findings},
            {("collar", -0.1), ("survey", 360.0)},
        )

    def test_accepts_inclusive_descending_dip_boundaries_in_collar_and_survey(self) -> None:
        self.data.collar.records[0]["dip_deg"] = 0.0
        for station in self.data.survey.records:
            station["dip_deg"] = -90.0

        findings = validate_m01_data(self.data).findings

        self.assertFalse(
            any(item.rule_id in {"COLLAR-007", "SURVEY-006"} for item in findings)
        )

    def test_rejects_dip_outside_descending_range(self) -> None:
        self.data.collar.records[0]["dip_deg"] = -90.1
        self.data.survey.records[0]["dip_deg"] = 0.1

        findings = validate_m01_data(self.data).findings

        range_findings = [
            item
            for item in findings
            if item.rule_id in {"COLLAR-007", "SURVEY-006"}
        ]
        self.assertEqual(
            {(item.table, item.observed_value) for item in range_findings},
            {("collar", -90.1), ("survey", 0.1)},
        )

    def test_reports_duplicate_collar_hole_id(self) -> None:
        duplicate = self.data.collar.records[0].copy()
        duplicate["x"] = 101.0
        self.data.collar.records.append(duplicate)

        findings = validate_m01_data(self.data).findings

        self.assertTrue(
            any(item.rule_id == "COLLAR-001" and item.row_number == 3 for item in findings)
        )

    def test_reports_missing_zero_depth_survey_station(self) -> None:
        self.data.survey.records.pop(0)

        findings = validate_m01_data(self.data).findings
        finding = next(item for item in findings if item.rule_id == "SURVEY-006")

        self.assertEqual(finding.severity, "WARNING")
        self.assertEqual(finding.hole_id, "H-01")
        self.assertEqual(finding.observed_value, "NO_ZERO_DEPTH_STATION")

    def test_reports_near_duplicate_survey_station_as_warning(self) -> None:
        duplicate = self.data.survey.records[0].copy()
        duplicate["azimuth_deg"] = 1.5
        self.data.survey.records.append(duplicate)

        report = validate_m01_data(self.data)
        finding = next(
            item for item in report.findings if item.rule_id == "SURVEY-008"
        )

        self.assertEqual(finding.severity, "WARNING")
        self.assertEqual(finding.row_number, 4)
        self.assertFalse(report.has_errors)

    def test_reports_duplicate_survey_at_two_degrees_as_error(self) -> None:
        duplicate = self.data.survey.records[0].copy()
        duplicate["azimuth_deg"] = 2.0
        self.data.survey.records.append(duplicate)

        report = validate_m01_data(self.data)
        finding = next(
            item for item in report.findings if item.rule_id == "SURVEY-008"
        )

        self.assertEqual(finding.severity, "ERROR")
        self.assertTrue(report.has_errors)

    def test_duplicate_survey_azimuth_uses_circular_difference(self) -> None:
        self.data.survey.records[0]["azimuth_deg"] = 359.0
        duplicate = self.data.survey.records[0].copy()
        duplicate["azimuth_deg"] = 1.0
        self.data.survey.records.append(duplicate)

        report = validate_m01_data(self.data)
        finding = next(
            item for item in report.findings if item.rule_id == "SURVEY-008"
        )

        self.assertEqual(finding.severity, "ERROR")

    def test_initial_orientation_difference_below_two_degrees_is_info(self) -> None:
        self.data.collar.records[0]["azimuth_deg"] = 10.0
        self.data.survey.records[0]["azimuth_deg"] = 11.5

        report = validate_m01_data(self.data)
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "SURVEY-009" and item.field == "azimuth_deg"
        )

        self.assertEqual(finding.severity, "INFO")
        self.assertEqual(finding.observed_value, 1.5)
        self.assertFalse(finding.blocking)
        self.assertEqual(report.error_count, 0)

    def test_initial_orientation_difference_at_two_degrees_is_warning(self) -> None:
        self.data.collar.records[0]["dip_deg"] = -90.0
        self.data.survey.records[0]["dip_deg"] = -88.0

        report = validate_m01_data(self.data)
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "SURVEY-009" and item.field == "dip_deg"
        )

        self.assertEqual(finding.severity, "WARNING")
        self.assertEqual(finding.observed_value, 2.0)
        self.assertTrue(finding.requires_review)
        self.assertFalse(finding.blocking)
        self.assertEqual(report.error_count, 0)

    def test_initial_azimuth_difference_uses_shortest_angular_distance(self) -> None:
        self.data.collar.records[0]["azimuth_deg"] = 359.0
        self.data.survey.records[0]["azimuth_deg"] = 1.0

        report = validate_m01_data(self.data)
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "SURVEY-009" and item.field == "azimuth_deg"
        )

        self.assertEqual(finding.severity, "WARNING")
        self.assertEqual(finding.observed_value, 2.0)

    def test_reports_nested_overlapping_intervals(self) -> None:
        nested = self.data.assay.records[0].copy()
        nested.update({"sample_id": "S-02", "from_m": 2.0, "to_m": 3.0, "length_m": 1.0})
        self.data.assay.records.append(nested)

        findings = validate_m01_data(self.data).findings

        self.assertTrue(any(item.rule_id == "ASSAY-009" for item in findings))

    def test_reports_negative_assay_as_review_and_zero_values_as_info(self) -> None:
        self.data.assay.records[0]["cu_pct"] = -0.1

        findings = validate_m01_data(self.data).findings

        negative = next(item for item in findings if item.rule_id == "ASSAY-004")
        zero_findings = [item for item in findings if item.rule_id == "ASSAY-005"]
        self.assertEqual(negative.severity, "WARNING")
        self.assertTrue(negative.requires_review)
        self.assertEqual({item.field for item in zero_findings}, {"mo_pct", "au_gt"})
        self.assertTrue(all(item.severity == "INFO" for item in zero_findings))

    def test_reports_missing_required_assay_value_once(self) -> None:
        self.data.assay.records[0]["cu_pct"] = ""

        findings = [
            item
            for item in validate_m01_data(self.data).findings
            if item.field == "cu_pct"
        ]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "ASSAY-REQ-001")
        self.assertEqual(findings[0].severity, "ERROR")

    def test_reports_release_campaign_name_difference_as_warning(self) -> None:
        self.data.release_manifest["campaigns"] = ["C-02"]

        findings = validate_m01_data(self.data).findings
        finding = next(item for item in findings if item.rule_id == "RELEASE-001")

        self.assertEqual(finding.severity, "WARNING")
        self.assertEqual(finding.field, "campaigns")

    def test_reports_density_gap_as_descriptive_information(self) -> None:
        second = self.data.density.records[0].copy()
        second.update(
            {
                "density_sample_id": "D-02",
                "from_m": 2.0,
                "to_m": 3.0,
                "length_m": 1.0,
            }
        )
        self.data.density.records.append(second)

        report = validate_m01_data(self.data)
        finding = next(item for item in report.findings if item.rule_id == "DENSITY-010")

        self.assertEqual(finding.severity, "INFO")
        self.assertEqual(finding.observed_value, "1.0,2.0")
        self.assertEqual(report.error_count, 0)

    def test_reports_survey_end_depth_without_assuming_it_must_equal_final_depth(self) -> None:
        self.data.survey.records[-1]["depth_m"] = 9.0

        findings = validate_m01_data(self.data).findings
        finding = next(item for item in findings if item.rule_id == "SURVEY-010")

        self.assertEqual(finding.severity, "INFO")
        self.assertEqual(finding.observed_value, 9.0)

    def test_validator_does_not_mutate_loaded_tables(self) -> None:
        original = copy.deepcopy(self.data)

        validate_m01_data(self.data)

        self.assertEqual(self.data, original)


class ValidateM01ReleaseTests(unittest.TestCase):
    def test_validates_release_without_error_findings(self) -> None:
        report = validate_m01_data(load_m01_data())

        self.assertFalse(report.has_errors)
        self.assertEqual(report.error_count, 0)
        self.assertGreater(report.warning_count, 0)
        self.assertGreater(report.info_count, 0)


if __name__ == "__main__":
    unittest.main()
