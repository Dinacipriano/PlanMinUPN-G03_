import csv
import tempfile
import unittest
from pathlib import Path

from src.m01.compositing import (
    AssaySegment,
    Composite,
    composite_m01_assays,
    composite_segments,
    position_composites,
    split_assays_at_contacts,
    summarize_compositing,
    write_composites_csv,
)
from src.m01.desurvey import desurvey_m01_data
from src.m01.loader import LoadedTable, M01Data, TableRecord
from src.m01.validator import validate_m01_data


def _assay(hole: str, start: float, end: float, cu: float, n: int = 1) -> TableRecord:
    return {
        "sample_id": f"{hole}-A{n:03d}",
        "hole_id": hole,
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "from_m": start,
        "to_m": end,
        "length_m": end - start,
        "cu_pct": cu,
        "mo_pct": 0.0,
        "au_gt": 0.0,
    }


def _lith(hole: str, start: float, end: float, code: str) -> TableRecord:
    return {
        "hole_id": hole,
        "dataset_id": "DS-01",
        "project_id": "P-01",
        "campaign_id": "C-01",
        "from_m": start,
        "to_m": end,
        "length_m": end - start,
        "lith_code": code,
    }


def _data(assays: list[TableRecord], lithology: list[TableRecord]) -> M01Data:
    return M01Data(
        collar=LoadedTable((), []),
        survey=LoadedTable((), []),
        lithology=LoadedTable(("hole_id",), lithology),
        alteration=LoadedTable((), []),
        assay=LoadedTable(("hole_id",), assays),
        density=LoadedTable((), []),
        data_dictionary=LoadedTable((), []),
        release_manifest={},
        readme="",
    )


def _composite(data: M01Data):
    segments, findings = split_assays_at_contacts(data)
    return segments, composite_segments(segments), findings


class CompositeSegmentsTests(unittest.TestCase):
    def test_two_one_meter_assays_form_one_two_meter_composite(self) -> None:
        data = _data(
            [_assay("H-01", 0, 1, 0.4, 1), _assay("H-01", 1, 2, 0.8, 2)],
            [_lith("H-01", 0, 2, "AAA")],
        )

        _, composites, _ = _composite(data)

        self.assertEqual(len(composites), 1)
        self.assertAlmostEqual(composites[0].length_m, 2.0)
        self.assertFalse(composites[0].residual_flag)
        self.assertEqual(composites[0].n_pieces, 2)

    def test_grade_is_weighted_by_length(self) -> None:
        data = _data(
            [_assay("H-01", 0, 0.5, 1.0, 1), _assay("H-01", 0.5, 2, 0.2, 2)],
            [_lith("H-01", 0, 2, "AAA")],
        )

        _, composites, _ = _composite(data)

        expected = (1.0 * 0.5 + 0.2 * 1.5) / 2.0
        self.assertAlmostEqual(composites[0].cu_pct, expected)

    def test_two_meter_assay_is_preserved(self) -> None:
        data = _data([_assay("H-01", 0, 2, 0.35)], [_lith("H-01", 0, 2, "AAA")])

        _, composites, _ = _composite(data)

        self.assertEqual(len(composites), 1)
        self.assertAlmostEqual(composites[0].from_m, 0.0)
        self.assertAlmostEqual(composites[0].to_m, 2.0)
        self.assertAlmostEqual(composites[0].cu_pct, 0.35)
        self.assertFalse(composites[0].residual_flag)

    def test_terminal_residual_shorter_than_target_is_kept_and_flagged(self) -> None:
        data = _data(
            [_assay("H-01", 0, 2, 0.5, 1), _assay("H-01", 2, 3.5, 0.3, 2)],
            [_lith("H-01", 0, 3.5, "AAA")],
        )

        _, composites, _ = _composite(data)

        self.assertEqual([round(c.length_m, 6) for c in composites], [2.0, 1.5])
        self.assertEqual([c.residual_flag for c in composites], [False, True])
        self.assertAlmostEqual(composites[1].cu_pct, 0.3)

    def test_contact_inside_assay_splits_exactly_at_contact(self) -> None:
        data = _data(
            [_assay("H-01", 4, 6, 0.7)],
            [_lith("H-01", 0, 5, "AAA"), _lith("H-01", 5, 10, "BBB")],
        )

        segments, _, findings = _composite(data)

        self.assertEqual(len(segments), 2)
        self.assertEqual((segments[0].from_m, segments[0].to_m), (4.0, 5.0))
        self.assertEqual(segments[0].lith_code, "AAA")
        self.assertEqual((segments[1].from_m, segments[1].to_m), (5.0, 6.0))
        self.assertEqual(segments[1].lith_code, "BBB")
        self.assertFalse(findings)

    def test_no_composite_crosses_a_lithology_contact(self) -> None:
        lithology = [_lith("H-01", 0, 5, "AAA"), _lith("H-01", 5, 10, "BBB")]
        assays = [_assay("H-01", 2 * i, 2 * i + 2, 0.1 * (i + 1), i + 1) for i in range(5)]
        data = _data(assays, lithology)

        _, composites, _ = _composite(data)

        for composite in composites:
            containing = [
                interval
                for interval in lithology
                if interval["from_m"] <= composite.from_m + 1e-9
                and composite.to_m <= interval["to_m"] + 1e-9
            ]
            self.assertEqual(len(containing), 1)
            self.assertEqual(containing[0]["lith_code"], composite.lith_code)
        self.assertEqual(
            [(c.lith_code, round(c.length_m, 6), c.residual_flag) for c in composites],
            [
                ("AAA", 2.0, False),
                ("AAA", 2.0, False),
                ("AAA", 1.0, True),
                ("BBB", 2.0, False),
                ("BBB", 2.0, False),
                ("BBB", 1.0, True),
            ],
        )

    def test_composite_meters_equal_assay_meters(self) -> None:
        lithology = [_lith("H-01", 0, 5, "AAA"), _lith("H-01", 5, 10, "BBB")]
        assays = [_assay("H-01", 2 * i, 2 * i + 2, 0.1 * (i + 1), i + 1) for i in range(5)]
        data = _data(assays, lithology)

        _, composites, _ = _composite(data)

        self.assertAlmostEqual(sum(c.length_m for c in composites), 10.0)

    def test_from_is_less_than_to_and_length_is_positive(self) -> None:
        lithology = [_lith("H-01", 0, 4.3, "AAA"), _lith("H-01", 4.3, 9.1, "BBB")]
        assays = [
            _assay("H-01", 0, 2, 0.2, 1),
            _assay("H-01", 2, 4, 0.3, 2),
            _assay("H-01", 4, 6, 0.4, 3),
            _assay("H-01", 6, 8, 0.5, 4),
            _assay("H-01", 8, 9.1, 0.6, 5),
        ]

        _, composites, _ = _composite(_data(assays, lithology))

        for composite in composites:
            self.assertLess(composite.from_m, composite.to_m)
            self.assertGreater(composite.length_m, 0.0)

    def test_holes_are_composited_independently(self) -> None:
        data = _data(
            [_assay("H-01", 0, 1, 0.4), _assay("H-02", 1, 2, 0.8)],
            [_lith("H-01", 0, 1, "AAA"), _lith("H-02", 1, 2, "AAA")],
        )

        _, composites, _ = _composite(data)

        self.assertEqual([c.hole_id for c in composites], ["H-01", "H-02"])
        self.assertTrue(all(c.residual_flag for c in composites))

    def test_gap_between_assays_breaks_the_run(self) -> None:
        data = _data(
            [_assay("H-01", 0, 1, 0.4, 1), _assay("H-01", 1.5, 2.5, 0.8, 2)],
            [_lith("H-01", 0, 3, "AAA")],
        )

        _, composites, _ = _composite(data)

        self.assertEqual(len(composites), 2)
        self.assertTrue(all(c.residual_flag for c in composites))


class SplitFindingsTests(unittest.TestCase):
    def test_uncovered_assay_part_is_reported_not_invented(self) -> None:
        data = _data([_assay("H-01", 0, 4, 0.5)], [_lith("H-01", 0, 3, "AAA")])

        segments, findings = split_assays_at_contacts(data)

        self.assertAlmostEqual(sum(s.length_m for s in segments), 3.0)
        self.assertEqual([f.rule_id for f in findings], ["COMPOSITE-003"])
        self.assertEqual(findings[0].severity, "ERROR")

    def test_overlapping_assay_is_skipped_and_reported(self) -> None:
        data = _data(
            [_assay("H-01", 0, 2, 0.5, 1), _assay("H-01", 1, 3, 0.9, 2)],
            [_lith("H-01", 0, 3, "AAA")],
        )

        segments, findings = split_assays_at_contacts(data)

        self.assertAlmostEqual(sum(s.length_m for s in segments), 2.0)
        self.assertEqual([f.rule_id for f in findings], ["COMPOSITE-004"])

    def test_invalid_assay_interval_is_skipped_and_reported(self) -> None:
        data = _data([_assay("H-01", 2, 2, 0.5)], [_lith("H-01", 0, 3, "AAA")])

        segments, findings = split_assays_at_contacts(data)

        self.assertFalse(segments)
        self.assertEqual([f.rule_id for f in findings], ["COMPOSITE-002"])


class PositionCompositesTests(unittest.TestCase):
    def _vertical_data(self) -> M01Data:
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
                "depth_m": depth,
                "azimuth_deg": 0.0,
                "dip_deg": -90.0,
            }
            for depth in (0.0, 10.0)
        ]
        assays = [_assay("H-01", 0, 2, 0.5, 1), _assay("H-01", 2, 3, 0.7, 2)]
        return M01Data(
            collar=LoadedTable(tuple(collar), [collar]),
            survey=LoadedTable(tuple(survey[0]), survey),
            lithology=LoadedTable(("hole_id",), [_lith("H-01", 0, 3, "AAA")]),
            alteration=LoadedTable((), []),
            assay=LoadedTable(("hole_id",), assays),
            density=LoadedTable((), []),
            data_dictionary=LoadedTable((), []),
            release_manifest={"campaigns": ["C-01"]},
            readme="",
        )

    def test_composite_midpoint_gets_xyz_on_vertical_hole(self) -> None:
        data = self._vertical_data()
        trajectories = desurvey_m01_data(data, validate_m01_data(data)).trajectories

        result = composite_m01_assays(data, trajectories)

        self.assertEqual(len(result.composites), 2)
        first, second = result.composites
        self.assertEqual((first.x, first.y, first.z), (100.0, 200.0, 299.0))
        self.assertEqual(second.z, 297.5)
        self.assertFalse(result.findings)

    def test_composite_beyond_trajectory_coverage_has_error_and_no_xyz(self) -> None:
        data = self._vertical_data()
        trajectories = desurvey_m01_data(data, validate_m01_data(data)).trajectories
        outside = Composite("H-01", 11.0, 13.0, "AAA", 0.5, False, 1)

        positioned, findings = position_composites((outside,), trajectories)

        self.assertIsNone(positioned[0].x)
        self.assertIsNone(positioned[0].z)
        self.assertEqual([f.rule_id for f in findings], ["COMPOSITE-005"])
        self.assertEqual(findings[0].severity, "ERROR")

    def test_summary_conserves_meters_and_weighted_mean(self) -> None:
        data = self._vertical_data()
        trajectories = desurvey_m01_data(data, validate_m01_data(data)).trajectories

        summary = summarize_compositing(data, composite_m01_assays(data, trajectories))

        self.assertAlmostEqual(summary["assay_meters"], 3.0)
        self.assertAlmostEqual(summary["composite_meters"], 3.0)
        self.assertAlmostEqual(summary["meters_difference"], 0.0)
        self.assertAlmostEqual(
            summary["cu_weighted_mean_assay"], summary["cu_weighted_mean_composites"]
        )
        self.assertEqual(summary["residual_composites"], 1)
        self.assertEqual(summary["target_length_composites"], 1)


class WriteCompositesTests(unittest.TestCase):
    def test_csv_has_expected_columns_and_residual_flag(self) -> None:
        composites = (
            Composite("H-01", 0.0, 2.0, "AAA", 0.5, False, 2, 1.0, 2.0, 3.0),
            Composite("H-01", 2.0, 3.0, "AAA", 0.7, True, 1),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_composites_csv(composites, Path(directory) / "m01b" / "c.csv")
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["residual_flag"], "False")
        self.assertEqual(rows[1]["residual_flag"], "True")
        self.assertEqual(rows[1]["x"], "")
        self.assertEqual(
            list(rows[0]),
            [
                "hole_id", "from_m", "to_m", "length_m", "mid_m", "x", "y", "z",
                "lith_code", "cu_pct", "residual_flag", "n_pieces",
            ],
        )

    def test_assay_segment_length(self) -> None:
        segment = AssaySegment("H-01", 1.0, 3.5, "AAA", 0.2, None)
        self.assertAlmostEqual(segment.length_m, 2.5)


if __name__ == "__main__":
    unittest.main()
