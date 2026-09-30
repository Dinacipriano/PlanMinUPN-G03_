import math
import unittest

from src.m01.desurvey import (
    _direction_vector,
    desurvey_m01_data,
    minimum_curvature_displacement,
)
from src.m01.loader import LoadedTable, M01Data, TableRecord
from src.m01.validator import validate_m01_data


def _survey(depth: float, azimuth: float, dip: float) -> TableRecord:
    return {
        "hole_id": "H-01",
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "depth_m": depth,
        "azimuth_deg": azimuth,
        "dip_deg": dip,
    }


def _data(
    survey: list[TableRecord],
    *,
    collar_azimuth: float = 0.0,
    collar_dip: float = -90.0,
    final_depth: float = 20.0,
) -> M01Data:
    collar = {
        "hole_id": "H-01",
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "x": 100.0,
        "y": 200.0,
        "z": 300.0,
        "azimuth_deg": collar_azimuth,
        "dip_deg": collar_dip,
        "final_depth_m": final_depth,
    }
    return M01Data(
        collar=LoadedTable(tuple(collar), [collar]),
        survey=LoadedTable(tuple(survey[0]) if survey else (), survey),
        lithology=LoadedTable((), []),
        alteration=LoadedTable((), []),
        assay=LoadedTable((), []),
        density=LoadedTable((), []),
        data_dictionary=LoadedTable((), []),
        release_manifest={"campaigns": ["C-01"]},
        readme="",
    )


def _desurvey(data: M01Data):
    return desurvey_m01_data(data, validate_m01_data(data))


class MinimumCurvatureTests(unittest.TestCase):
    def test_vertical_downhole_trajectory_descends_without_horizontal_shift(self) -> None:
        data = _data([_survey(0.0, 0.0, -90.0), _survey(10.0, 0.0, -90.0)])

        result = _desurvey(data)
        trajectory = result.trajectories[0]
        endpoint = trajectory.points[-1]

        self.assertEqual([point.depth_m for point in trajectory.points], [0.0, 10.0])
        self.assertAlmostEqual(endpoint.x, 100.0, places=10)
        self.assertAlmostEqual(endpoint.y, 200.0, places=10)
        self.assertAlmostEqual(endpoint.z, 290.0, places=10)

    def test_horizontal_east_trajectory_changes_easting_only(self) -> None:
        data = _data([_survey(0.0, 90.0, 0.0), _survey(10.0, 90.0, 0.0)])

        endpoint = _desurvey(data).trajectories[0].points[-1]

        self.assertAlmostEqual(endpoint.x, 110.0, places=10)
        self.assertAlmostEqual(endpoint.y, 200.0, places=10)
        self.assertAlmostEqual(endpoint.z, 300.0, places=10)

    def test_zero_dogleg_matches_independent_straight_line_calculation(self) -> None:
        direction = _direction_vector(35.0, -20.0)
        displacement = minimum_curvature_displacement(
            0.0, 12.0, direction, direction
        )

        expected = tuple(12.0 * component for component in direction)
        for actual, manual in zip(displacement, expected):
            self.assertAlmostEqual(actual, manual, places=12)

    def test_zero_depth_survey_orientation_governs_over_collar(self) -> None:
        data = _data(
            [_survey(0.0, 90.0, 0.0), _survey(10.0, 90.0, 0.0)],
            collar_azimuth=0.0,
            collar_dip=-90.0,
        )

        endpoint = _desurvey(data).trajectories[0].points[-1]

        self.assertAlmostEqual(endpoint.x, 110.0, places=10)
        self.assertAlmostEqual(endpoint.z, 300.0, places=10)

    def test_missing_zero_depth_survey_uses_collar_and_reports_warning(self) -> None:
        data = _data([_survey(10.0, 0.0, -90.0)])

        result = _desurvey(data)
        trajectory = result.trajectories[0]
        report = validate_m01_data(data)

        self.assertEqual([point.depth_m for point in trajectory.points], [0.0, 10.0])
        self.assertAlmostEqual(trajectory.points[-1].z, 290.0, places=10)
        finding = next(item for item in report.findings if item.rule_id == "SURVEY-006")
        self.assertEqual(finding.severity, "WARNING")

    def test_trajectory_contains_no_synthetic_survey_depths(self) -> None:
        data = _data(
            [
                _survey(5.0, 0.0, -90.0),
                _survey(15.0, 0.0, -90.0),
            ]
        )

        points = _desurvey(data).trajectories[0].points

        self.assertEqual([point.depth_m for point in points], [0.0, 5.0, 15.0])

    def test_near_duplicate_station_warns_and_retains_first_csv_orientation(self) -> None:
        data = _data(
            [
                _survey(0.0, 0.0, -90.0),
                _survey(5.0, 0.0, -90.0),
                _survey(5.0, 1.0, -90.0),
                _survey(10.0, 0.0, -90.0),
            ]
        )

        report = validate_m01_data(data)
        result = desurvey_m01_data(data, report)

        self.assertFalse(report.has_errors)
        self.assertEqual(
            [point.depth_m for point in result.trajectories[0].points],
            [0.0, 5.0, 10.0],
        )
        self.assertAlmostEqual(result.trajectories[0].points[1].direction[0], 0.0)

    def test_contradictory_duplicate_blocks_hole_trajectory(self) -> None:
        data = _data(
            [
                _survey(0.0, 0.0, -90.0),
                _survey(5.0, 0.0, -90.0),
                _survey(5.0, 2.0, -90.0),
                _survey(10.0, 0.0, -90.0),
            ]
        )

        report = validate_m01_data(data)
        result = desurvey_m01_data(data, report)

        self.assertFalse(result.trajectories)
        self.assertTrue(any(item.rule_id == "SURVEY-008" for item in report.findings))
        self.assertTrue(any(item.rule_id == "DESURVEY-001" for item in result.findings))

    def test_survey_beyond_final_depth_blocks_hole_trajectory(self) -> None:
        data = _data(
            [_survey(0.0, 0.0, -90.0), _survey(11.0, 0.0, -90.0)],
            final_depth=10.0,
        )

        report = validate_m01_data(data)
        result = desurvey_m01_data(data, report)

        finding = next(item for item in report.findings if item.rule_id == "SURVEY-004")
        self.assertEqual(finding.severity, "ERROR")
        self.assertFalse(result.trajectories)

    def test_opposite_direction_dogleg_is_reported_not_returned_as_xyz(self) -> None:
        data = _data([_survey(0.0, 0.0, 0.0), _survey(10.0, 180.0, 0.0)])
        data.collar.records[0]["dip_deg"] = 0.0

        result = _desurvey(data)

        self.assertFalse(result.trajectories)
        self.assertTrue(any(item.rule_id == "DESURVEY-003" for item in result.findings))

    def test_direction_vectors_are_unit_length_and_vertical_sign_is_down(self) -> None:
        direction = _direction_vector(123.0, -90.0)

        self.assertTrue(math.isclose(sum(value * value for value in direction), 1.0))
        self.assertLess(direction[2], 0.0)
        self.assertAlmostEqual(direction[0], 0.0, places=10)
        self.assertAlmostEqual(direction[1], 0.0, places=10)
