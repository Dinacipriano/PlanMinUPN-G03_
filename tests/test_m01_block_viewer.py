import json
import re
import tempfile
import unittest
from pathlib import Path

from src.m01.block_model import GridSpec, TopographySurface
from src.m01.block_viewer import (
    DOMAINS,
    build_viewer_data,
    render_html,
    sample_surface,
    write_viewer,
)

# SYNTHETIC FIXTURES: invented rows for tests only.
GRID = GridSpec(x0=0.0, y0=0.0, z0=0.0, dx=10.0, dy=10.0, dz=10.0, nx=2, ny=2, nz=2)


def _row(block_id, ix, iy, iz, topo, domain, status, dist="5.000", hole="H1", mixed="0"):
    return {
        "block_id": str(block_id),
        "ix": str(ix),
        "iy": str(iy),
        "iz": str(iz),
        "topo_state": topo,
        "domain_id": domain,
        "assign_status": status,
        "nearest_dist_m": dist,
        "nearest_hole_id": hole,
        "mixed_flag": mixed,
    }


def _rows():
    return [
        _row(0, 0, 0, 0, "ROCK", "POR", "ASSIGNED_SUPPORTED"),
        _row(1, 1, 0, 0, "PARTIAL", "DIO", "ASSIGNED_EXTRAPOLATED", "70.0", "H2", "1"),
        _row(2, 0, 1, 0, "ROCK", "", "UNKNOWN_NO_SUPPORT", "", ""),
        _row(3, 1, 1, 0, "AIR", "", "NOT_ROCK_AIR", "", ""),
    ]


def _composites():
    return [
        {"hole_id": "H1", "from_m": "2", "x": "5", "y": "5", "z": "8", "lith_code": "POR"},
        {"hole_id": "H1", "from_m": "0", "x": "5", "y": "5", "z": "9", "lith_code": "POR"},
        {"hole_id": "H1", "from_m": "4", "x": "", "y": "", "z": "", "lith_code": "POR"},
    ]


def _surface_grid():
    points = [(i * 5.0, j * 5.0, 10.0) for i in range(-8, 13) for j in range(-8, 13)]
    return sample_surface(TopographySurface(points), GRID)


def _data():
    collars = [{"hole_id": "H1", "x": "5", "y": "5", "z": "10"}]
    return build_viewer_data(GRID, _rows(), _composites(), collars, _surface_grid())


class DataTests(unittest.TestCase):
    def test_air_blocks_are_not_drawn_but_counted(self):
        data = _data()
        self.assertEqual(len(data["blocks"]["ix"]), 3)
        self.assertEqual(data["n_air_blocks"], 1)
        self.assertEqual(data["n_blocks_total"], 4)

    def test_all_block_arrays_have_the_same_length(self):
        blocks = _data()["blocks"]
        self.assertEqual(len({len(values) for values in blocks.values()}), 1)

    def test_domain_status_and_topo_codes(self):
        blocks = _data()["blocks"]
        self.assertEqual(blocks["dom"], [DOMAINS.index("POR"), DOMAINS.index("DIO"), len(DOMAINS) - 1])
        self.assertEqual(blocks["st"], [0, 1, 2])
        self.assertEqual(blocks["tp"], [0, 1, 0])
        self.assertEqual(blocks["mx"], [0, 1, 0])
        self.assertEqual(blocks["dist"], [5.0, 70.0, None])

    def test_unknown_blocks_keep_the_unknown_color_index_and_no_hole(self):
        data = _data()
        self.assertEqual(data["blocks"]["hole"][2], -1)
        self.assertEqual(data["hole_names"], ["H1", "H2"])

    def test_composites_without_xyz_are_skipped_and_holes_start_at_collar(self):
        data = _data()
        self.assertEqual(len(data["composites"]["x"]), 2)
        pts = data["holes"][0]["pts"]
        self.assertEqual(pts[0], [5.0, 5.0, 10.0])
        self.assertEqual([p[2] for p in pts[1:]], [9.0, 8.0])  # sorted by from_m

    def test_surface_grid_has_none_where_there_is_no_coverage(self):
        far = sample_surface(TopographySurface([(1000.0, 1000.0, 5.0)]), GRID)
        self.assertTrue(all(value is None for row in far["z"] for value in row))
        near = _surface_grid()
        self.assertEqual(len(near["z"]), len(near["y"]))
        self.assertEqual(len(near["z"][0]), len(near["x"]))
        self.assertAlmostEqual(near["z"][2][2], 10.0)


class HtmlTests(unittest.TestCase):
    def test_html_embeds_valid_json_and_the_controls(self):
        html = render_html(_data())
        match = re.search(r"const D=(\{.*?\});\n\(function", html, re.S)
        self.assertIsNotNone(match)
        parsed = json.loads(match.group(1))
        self.assertEqual(parsed["n_air_blocks"], 1)
        for element in ("colorby", "f-dom", "f-st", "f-tp", "clip", "opacity", "layers"):
            self.assertIn(f'id="{element}"', html)
        self.assertIn("three.js/r128/three.min.js", html)
        self.assertNotIn("__DATA__", html)

    def test_payload_cannot_close_the_script_tag(self):
        data = _data()
        data["hole_names"] = ["</script><b>x"]
        html = render_html(data)
        self.assertNotIn("</script><b>x", html)

    def test_write_viewer_creates_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figures" / "viewer.html"
            write_viewer(_data(), path)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
