import csv
import tempfile
import unittest
from pathlib import Path

from src.m01.block_model import (
    STATE_AIR,
    STATE_OUTSIDE,
    STATE_PARTIAL,
    STATE_ROCK,
    Block,
)
from src.m01.domain_assignment import (
    CSV_COLUMNS,
    STATUS_EXTRAPOLATED,
    STATUS_NOT_ROCK,
    STATUS_SUPPORTED,
    STATUS_UNKNOWN,
    STATUS_UNKNOWN_TOPO,
    SearchParams,
    SupportPoint,
    assign_domains,
    read_support_points,
    summarize_assignment,
    write_assignment_csv,
)

# SYNTHETIC FIXTURES: invented blocks and composites, for tests only.


def _block(block_id, x, y, z, state=STATE_ROCK):
    return Block(
        block_id=block_id,
        ix=block_id,
        iy=0,
        iz=0,
        xc=x,
        yc=y,
        zc=z,
        dx=25.0,
        dy=25.0,
        dz=10.0,
        ztopo_center=None,
        ztopo_min=None,
        ztopo_max=None,
        topo_state=state,
    )


def _point(hole, x, y, z, domain):
    return SupportPoint(hole_id=hole, x=x, y=y, z=z, domain_id=domain)


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.points = [_point("H1", 0.0, 0.0, 0.0, "POR")]

    def _assign(self, blocks, points=None, params=None):
        return assign_domains(blocks, self.points if points is None else points, params)

    def test_block_within_first_radius_is_supported(self):
        result = self._assign([_block(0, 30.0, 0.0, 0.0)])
        block = result.blocks[0]
        self.assertEqual(block.assign_status, STATUS_SUPPORTED)
        self.assertEqual(block.domain_id, "POR")
        self.assertAlmostEqual(block.nearest_dist_m, 30.0)
        self.assertEqual(block.nearest_hole_id, "H1")

    def test_block_between_radii_is_extrapolated(self):
        block = self._assign([_block(0, 70.0, 0.0, 0.0)]).blocks[0]
        self.assertEqual(block.assign_status, STATUS_EXTRAPOLATED)
        self.assertEqual(block.domain_id, "POR")

    def test_block_beyond_second_radius_stays_unknown(self):
        block = self._assign([_block(0, 150.0, 0.0, 0.0)]).blocks[0]
        self.assertEqual(block.assign_status, STATUS_UNKNOWN)
        self.assertIsNone(block.domain_id)
        self.assertIsNone(block.nearest_dist_m)

    def test_radius_boundaries_are_inclusive(self):
        blocks = [_block(0, 50.0, 0.0, 0.0), _block(1, 100.0, 0.0, 0.0)]
        first, second = self._assign(blocks).blocks
        self.assertEqual(first.assign_status, STATUS_SUPPORTED)
        self.assertEqual(second.assign_status, STATUS_EXTRAPOLATED)

    def test_air_and_outside_blocks_get_no_domain(self):
        blocks = [
            _block(0, 10.0, 0.0, 0.0, STATE_AIR),
            _block(1, 10.0, 0.0, 0.0, STATE_OUTSIDE),
        ]
        air, outside = self._assign(blocks).blocks
        self.assertEqual((air.assign_status, air.domain_id), (STATUS_NOT_ROCK, None))
        self.assertEqual(
            (outside.assign_status, outside.domain_id), (STATUS_UNKNOWN_TOPO, None)
        )

    def test_partial_blocks_are_assigned_like_rock(self):
        block = self._assign([_block(0, 10.0, 0.0, 0.0, STATE_PARTIAL)]).blocks[0]
        self.assertEqual(block.assign_status, STATUS_SUPPORTED)

    def test_nearest_composite_decides_the_domain(self):
        points = [_point("H1", 0.0, 0.0, 0.0, "POR"), _point("H2", 40.0, 0.0, 0.0, "DIO")]
        block = self._assign([_block(0, 30.0, 0.0, 0.0)], points).blocks[0]
        self.assertEqual(block.domain_id, "DIO")
        self.assertEqual(block.nearest_hole_id, "H2")

    def test_mixed_flag_marks_several_domains_within_first_radius(self):
        points = [_point("H1", 0.0, 0.0, 0.0, "POR"), _point("H2", 40.0, 0.0, 0.0, "DIO")]
        mixed = self._assign([_block(0, 30.0, 0.0, 0.0)], points).blocks[0]
        self.assertTrue(mixed.mixed_flag)
        self.assertEqual((mixed.n_holes_r1, mixed.n_domains_r1), (2, 2))
        pure = self._assign([_block(0, 10.0, 0.0, 0.0)]).blocks[0]
        self.assertFalse(pure.mixed_flag)

    def test_tie_is_resolved_deterministically(self):
        points = [_point("H2", 20.0, 0.0, 0.0, "DIO"), _point("H1", -20.0, 0.0, 0.0, "POR")]
        first = self._assign([_block(0, 0.0, 0.0, 0.0)], points).blocks[0]
        second = self._assign([_block(0, 0.0, 0.0, 0.0)], list(reversed(points))).blocks[0]
        self.assertEqual(first.nearest_hole_id, "H1")
        self.assertEqual(first, second)

    def test_vertical_distance_counts(self):
        block = self._assign([_block(0, 0.0, 0.0, 60.0)]).blocks[0]
        self.assertEqual(block.assign_status, STATUS_EXTRAPOLATED)

    def test_no_support_points_means_everything_unknown(self):
        result = self._assign([_block(0, 0.0, 0.0, 0.0)], points=[])
        self.assertEqual(result.blocks[0].assign_status, STATUS_UNKNOWN)

    def test_invalid_radii_are_rejected(self):
        with self.assertRaises(ValueError):
            SearchParams(radius_supported_m=100.0, radius_extrapolated_m=50.0)
        with self.assertRaises(ValueError):
            SearchParams(radius_supported_m=0.0)

    def test_summary_counts_add_up(self):
        blocks = [
            _block(0, 10.0, 0.0, 0.0),
            _block(1, 70.0, 0.0, 0.0),
            _block(2, 500.0, 0.0, 0.0),
            _block(3, 0.0, 0.0, 0.0, STATE_AIR),
        ]
        summary = summarize_assignment(self._assign(blocks))
        self.assertEqual(sum(summary["status_counts"].values()), 4)
        self.assertEqual(summary["n_rock_blocks"], 3)
        self.assertEqual(summary["domain_counts"], {"POR": 2})


class InputOutputTests(unittest.TestCase):
    def _write(self, folder, text):
        path = Path(folder) / "composites.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_air_unknown_codes_and_missing_xyz_are_excluded_with_warning(self):
        text = (
            "hole_id,x,y,z,lith_code\n"
            "H1,1,2,3,POR\n"
            "H1,1,2,3,AIR\n"
            "H1,1,2,3,XXX\n"
            "H1,,,,DIO\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            points, findings = read_support_points(self._write(folder, text))
        self.assertEqual([p.domain_id for p in points], ["POR"])
        self.assertTrue(all(f.rule_id == "ASSIGN-002" for f in findings))
        self.assertEqual(len(findings), 3)

    def test_missing_composites_file_is_an_error(self):
        points, findings = read_support_points("does/not/exist.csv")
        self.assertEqual(points, [])
        self.assertEqual([f.rule_id for f in findings], ["ASSIGN-001"])

    def test_csv_has_expected_columns_and_rows(self):
        blocks = [_block(0, 10.0, 0.0, 0.0), _block(1, 0.0, 0.0, 0.0, STATE_AIR)]
        result = assign_domains(blocks, [_point("H1", 0.0, 0.0, 0.0, "POR")])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out" / "blocks.csv"
            write_assignment_csv(result.blocks, path)
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(rows[0].keys()), CSV_COLUMNS)
        self.assertEqual([r["assign_status"] for r in rows], [STATUS_SUPPORTED, STATUS_NOT_ROCK])
        self.assertEqual(rows[1]["domain_id"], "")


if __name__ == "__main__":
    unittest.main()
