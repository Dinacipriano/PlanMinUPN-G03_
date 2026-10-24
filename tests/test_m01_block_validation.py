import tempfile
import unittest
from pathlib import Path

from src.m01.block_model import GridSpec
from src.m01.block_validation import (
    FAIL,
    PASS,
    WARNING,
    busiest_indices,
    domain_section,
    render_report,
    validate_block_model,
)

# SYNTHETIC FIXTURES: a tiny invented model (2 x 2 x 2 blocks) for tests only.
GRID = GridSpec(x0=0.0, y0=0.0, z0=0.0, dx=10.0, dy=10.0, dz=10.0, nx=2, ny=2, nz=2)


def _topo(ix, iy, iz, state, low="", high=""):
    return {
        "block_id": str(GRID.block_id(ix, iy, iz)),
        "ix": str(ix),
        "iy": str(iy),
        "iz": str(iz),
        "xc": f"{(ix + 0.5) * 10:.3f}",
        "yc": f"{(iy + 0.5) * 10:.3f}",
        "zc": f"{(iz + 0.5) * 10:.3f}",
        "dx": "10",
        "dy": "10",
        "dz": "10",
        "volume_m3": "1000",
        "ztopo_center": low,
        "ztopo_min": low,
        "ztopo_max": high,
        "topo_state": state,
    }


def _domain(topo_row, domain="", status="", dist="", mixed="0"):
    return {
        "block_id": topo_row["block_id"],
        "ix": topo_row["ix"],
        "iy": topo_row["iy"],
        "iz": topo_row["iz"],
        "topo_state": topo_row["topo_state"],
        "domain_id": domain,
        "assign_status": status,
        "nearest_dist_m": dist,
        "mixed_flag": mixed,
    }


def _good_model():
    """Surface at z=10 everywhere: layer iz=0 is ROCK, layer iz=1 is AIR."""
    topo, domain = [], []
    for iz in (0, 1):
        for iy in (0, 1):
            for ix in (0, 1):
                if iz == 0:
                    t = _topo(ix, iy, iz, "ROCK", "10.000", "10.000")
                    d = _domain(t, "POR", "ASSIGNED_SUPPORTED", "5.000")
                else:
                    t = _topo(ix, iy, iz, "AIR", "10.000", "10.000")
                    d = _domain(t, "", "NOT_ROCK_AIR")
                topo.append(t)
                domain.append(d)
    composites = [
        {"x": "5", "y": "5", "z": "5", "lith_code": "POR", "length_m": "2"},
    ]
    return topo, domain, composites


def _status(summary, control_id):
    return next(c.status for c in summary.controls if c.control_id == control_id)


class ConformingModelTests(unittest.TestCase):
    def test_clean_model_has_no_fail(self):
        topo, domain, composites = _good_model()
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertNotEqual(summary.overall, FAIL)
        self.assertEqual(summary.counts[FAIL], 0)

    def test_pure_domain_model_passes_every_control(self):
        topo, domain, composites = _good_model()
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(summary.overall, PASS)

    def test_overall_is_warning_when_partial_blocks_exist(self):
        topo, domain, composites = _good_model()
        topo[0] = _topo(0, 0, 0, "PARTIAL", "5.000", "15.000")
        domain[0] = _domain(topo[0], "POR", "ASSIGNED_SUPPORTED", "5.000")
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(summary.overall, WARNING)
        self.assertEqual(_status(summary, "TOP-05"), WARNING)


class FailureDetectionTests(unittest.TestCase):
    def test_duplicate_block_ids_fail(self):
        topo, domain, composites = _good_model()
        topo[1]["block_id"] = topo[0]["block_id"]
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "GEO-01"), FAIL)

    def test_missing_blocks_fail(self):
        topo, domain, composites = _good_model()
        summary = validate_block_model(topo[:-1], domain[:-1], composites, GRID)
        self.assertEqual(_status(summary, "GEO-02"), FAIL)

    def test_wrong_center_fails(self):
        topo, domain, composites = _good_model()
        topo[0]["xc"] = "7.000"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "GEO-04"), FAIL)

    def test_state_inconsistent_with_surface_fails(self):
        topo, domain, composites = _good_model()
        topo[0]["ztopo_min"] = "3.000"  # ROCK block cannot reach above the surface
        topo[0]["ztopo_max"] = "3.000"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "TOP-02"), FAIL)

    def test_composite_inside_air_block_fails(self):
        topo, domain, composites = _good_model()
        composites.append({"x": "5", "y": "5", "z": "15", "lith_code": "POR", "length_m": "2"})
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "TOP-03"), FAIL)

    def test_composite_outside_grid_fails(self):
        topo, domain, composites = _good_model()
        composites.append({"x": "500", "y": "5", "z": "5", "lith_code": "POR", "length_m": "2"})
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "SUP-01"), FAIL)

    def test_composite_without_xyz_fails(self):
        topo, domain, composites = _good_model()
        composites.append({"x": "", "y": "", "z": "", "lith_code": "POR", "length_m": "2"})
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "SUP-02"), FAIL)

    def test_domain_in_air_block_fails(self):
        topo, domain, composites = _good_model()
        domain[-1]["domain_id"] = "POR"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "DOM-01"), FAIL)

    def test_unapproved_domain_fails(self):
        topo, domain, composites = _good_model()
        domain[0]["domain_id"] = "XYZ"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "DOM-02"), FAIL)

    def test_distance_beyond_radius_with_supported_status_fails(self):
        topo, domain, composites = _good_model()
        domain[0]["nearest_dist_m"] = "75.000"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "DOM-03"), FAIL)

    def test_files_with_different_block_ids_fail(self):
        topo, domain, composites = _good_model()
        domain[0]["block_id"] = "99"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "REC-01"), FAIL)


class WarningTests(unittest.TestCase):
    def test_extrapolated_unknown_and_mixed_are_warnings_not_failures(self):
        topo, domain, composites = _good_model()
        domain[0] = _domain(topo[0], "POR", "ASSIGNED_EXTRAPOLATED", "75.000")
        domain[1] = _domain(topo[1], "", "UNKNOWN_NO_SUPPORT")
        domain[2]["mixed_flag"] = "1"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "UNC-01"), WARNING)
        self.assertEqual(_status(summary, "UNC-02"), WARNING)
        self.assertEqual(_status(summary, "UNC-03"), WARNING)
        self.assertEqual(summary.counts[FAIL], 0)

    def test_domain_disagreeing_with_interior_composite_is_warning(self):
        topo, domain, composites = _good_model()
        domain[0]["domain_id"] = "DIO"
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "DOM-04"), WARNING)

    def test_share_difference_above_tolerance_is_warning(self):
        topo, domain, composites = _good_model()
        composites.append({"x": "15", "y": "5", "z": "5", "lith_code": "DIO", "length_m": "200"})
        summary = validate_block_model(topo, domain, composites, GRID)
        self.assertEqual(_status(summary, "DOM-05"), WARNING)


class SectionTests(unittest.TestCase):
    def test_section_symbols_and_orientation(self):
        topo, domain, _ = _good_model()
        domain[0] = _domain(topo[0], "POR", "ASSIGNED_EXTRAPOLATED", "75.000")
        text = domain_section(domain, "y", 0, GRID)
        lines = text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith("| .."))  # top layer is air
        self.assertTrue(lines[1].endswith("| pP"))  # extrapolated then supported

    def test_invalid_axis_is_rejected(self):
        with self.assertRaises(ValueError):
            domain_section([], "z", 0, GRID)

    def test_busiest_indices_follow_composite_counts(self):
        composites = [
            {"x": "15", "y": "5", "z": "5"},
            {"x": "15", "y": "5", "z": "6"},
            {"x": "5", "y": "15", "z": "5"},
        ]
        self.assertEqual(busiest_indices(composites, GRID), (0, 1))

    def test_report_is_written_with_all_controls(self):
        topo, domain, composites = _good_model()
        summary = validate_block_model(topo, domain, composites, GRID)
        text = render_report(summary, [("Sección", "x")])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.md"
            path.write_text(text, encoding="utf-8")
            content = path.read_text(encoding="utf-8")
        self.assertIn("Resultado global", content)
        self.assertEqual(content.count("| GEO-01 |"), 1)


if __name__ == "__main__":
    unittest.main()
