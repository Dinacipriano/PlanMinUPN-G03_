import unittest

from src.m01.desurvey import desurvey_m01_data
from src.m01.loader import LoadedTable, M01Data, TableRecord
from src.m01.positioning import position_m01_intervals
from src.m01.validator import validate_m01_data


def _interval(start: float, end: float) -> TableRecord:
    return {
        "sample_id": "S-01",
        "hole_id": "H-01",
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "from_m": start,
        "to_m": end,
        "length_m": end - start,
        "cu_pct": 0.5,
        "mo_pct": 0.1,
        "au_gt": 0.2,
    }


def _data(
    interval: TableRecord,
    survey: list[TableRecord] | None = None,
) -> M01Data:
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
    if survey is None:
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
    return M01Data(
        collar=LoadedTable(tuple(collar), [collar]),
        survey=LoadedTable(tuple(survey[0]) if survey else (), survey),
        lithology=LoadedTable((), []),
        alteration=LoadedTable((), []),
        assay=LoadedTable(tuple(interval), [interval]),
        density=LoadedTable((), []),
        data_dictionary=LoadedTable((), []),
        release_manifest={"campaigns": ["C-01"]},
        readme="",
    )


def _position(data: M01Data):
    validation = validate_m01_data(data)
    desurvey = desurvey_m01_data(data, validation)
    return position_m01_intervals(data, desurvey.trajectories)


class PositionM01IntervalsTests(unittest.TestCase):
    def test_positions_interval_endpoints_on_vertical_trajectory(self) -> None:
        result = _position(_data(_interval(2.0, 8.0)))

        self.assertEqual(len(result.intervals), 1)
        interval = result.intervals[0]
        self.assertEqual(interval.from_xyz, (100.0, 200.0, 298.0))
        self.assertEqual(interval.to_xyz, (100.0, 200.0, 292.0))
        self.assertFalse(result.findings)

    def test_interpolates_position_within_curved_minimum_curvature_segment(self) -> None:
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
                "azimuth_deg": 90.0,
                "dip_deg": 0.0,
            },
        ]
        data = _data(_interval(5.0, 10.0), survey)

        result = _position(data)

        self.assertEqual(len(result.intervals), 1)
        midpoint = result.intervals[0].from_xyz
        self.assertGreater(midpoint[0], 100.0)
        self.assertLess(midpoint[2], 300.0)
        self.assertNotEqual(midpoint, (105.0, 200.0, 300.0))

    def test_out_of_coverage_from_endpoint_returns_error_without_coordinates(self) -> None:
        result = _position(_data(_interval(-1.0, 5.0)))

        self.assertFalse(result.intervals)
        finding = next(item for item in result.findings if item.rule_id == "POSITION-003")
        self.assertEqual(finding.severity, "ERROR")
        self.assertEqual(finding.field, "from_m")

    def test_out_of_coverage_to_endpoint_returns_error_without_coordinates(self) -> None:
        result = _position(_data(_interval(5.0, 11.0)))

        self.assertFalse(result.intervals)
        finding = next(item for item in result.findings if item.rule_id == "POSITION-003")
        self.assertEqual(finding.severity, "ERROR")
        self.assertEqual(finding.field, "to_m")

    def test_interval_for_hole_without_trajectory_has_error_and_no_xyz(self) -> None:
        interval = _interval(0.0, 5.0)
        interval["hole_id"] = "MISSING"
        data = _data(interval)

        result = position_m01_intervals(data, ())

        self.assertFalse(result.intervals)
        self.assertEqual(result.findings[0].rule_id, "POSITION-001")
        self.assertEqual(result.findings[0].severity, "ERROR")
