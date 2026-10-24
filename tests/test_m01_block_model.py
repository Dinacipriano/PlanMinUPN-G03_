import csv
import tempfile
import unittest
from pathlib import Path

from src.m01.block_model import (
    CSV_COLUMNS,
    STATE_AIR,
    STATE_OUTSIDE,
    STATE_PARTIAL,
    STATE_ROCK,
    GridSpec,
    TopographySurface,
    build_block_model,
    read_topography,
    summarize_block_model,
    write_block_model_csv,
)

# SYNTHETIC FIXTURES: every topography below is invented for tests only and
# is not data of the deposit.


def _lattice(z_of_xy, step=5.0, size=200.0):
    count = int(size / step) + 1
    return [
        (i * step, j * step, z_of_xy(i * step, j * step))
        for i in range(count)
        for j in range(count)
    ]


def _grid(z0=80.0, nz=4, x0=50.0, y0=50.0):
    return GridSpec(x0=x0, y0=y0, z0=z0, dx=25.0, dy=25.0, dz=10.0, nx=4, ny=4, nz=nz)


def _states_by_layer(result):
    layers = {}
    for block in result.blocks:
        layers.setdefault(block.iz, set()).add(block.topo_state)
    return layers


class GridSpecTests(unittest.TestCase):
    def test_invalid_sizes_are_rejected(self):
        with self.assertRaises(ValueError):
            GridSpec(0, 0, 0, 0.0, 1.0, 1.0, 1, 1, 1)
        with self.assertRaises(ValueError):
            GridSpec(0, 0, 0, 1.0, 1.0, 1.0, 0, 1, 1)

    def test_block_ids_are_unique_and_count_matches(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        result = build_block_model(surface, _grid())
        ids = [block.block_id for block in result.blocks]
        self.assertEqual(len(ids), 4 * 4 * 4)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(sorted(ids), list(range(len(ids))))

    def test_centers_and_volumes(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        result = build_block_model(surface, _grid())
        first = result.blocks[0]
        self.assertEqual((first.xc, first.yc, first.zc), (62.5, 62.5, 85.0))
        self.assertTrue(all(block.volume_m3 == 25.0 * 25.0 * 10.0 for block in result.blocks))


class ClassificationTests(unittest.TestCase):
    def test_flat_surface_splits_rock_and_air_without_partial(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        layers = _states_by_layer(build_block_model(surface, _grid()))
        self.assertEqual(layers[0], {STATE_ROCK})
        self.assertEqual(layers[1], {STATE_ROCK})
        self.assertEqual(layers[2], {STATE_AIR})
        self.assertEqual(layers[3], {STATE_AIR})

    def test_surface_inside_a_layer_gives_partial(self):
        surface = TopographySurface(_lattice(lambda x, y: 105.0))
        layers = _states_by_layer(build_block_model(surface, _grid()))
        self.assertEqual(layers[1], {STATE_ROCK})
        self.assertEqual(layers[2], {STATE_PARTIAL})
        self.assertEqual(layers[3], {STATE_AIR})

    def test_sloped_surface_has_partial_layer_between_rock_and_air(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0 + 0.2 * x))
        result = build_block_model(surface, _grid(z0=88.0, nz=4))
        column = {b.iz: b.topo_state for b in result.blocks if b.ix == 0 and b.iy == 1}
        self.assertEqual(column[0], STATE_ROCK)
        self.assertEqual(column[1], STATE_ROCK)
        self.assertEqual(column[2], STATE_PARTIAL)
        self.assertEqual(column[3], STATE_AIR)

    def test_blocks_outside_coverage_are_kept_with_explicit_state(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        result = build_block_model(surface, _grid(x0=500.0, y0=500.0))
        self.assertEqual(len(result.blocks), 64)
        self.assertEqual({b.topo_state for b in result.blocks}, {STATE_OUTSIDE})
        self.assertTrue(all(b.ztopo_center is None for b in result.blocks))

    def test_empty_topography_marks_everything_outside(self):
        result = build_block_model(TopographySurface([]), _grid())
        self.assertEqual({b.topo_state for b in result.blocks}, {STATE_OUTSIDE})

    def test_surface_above_grid_top_raises_warning(self):
        surface = TopographySurface(_lattice(lambda x, y: 200.0))
        result = build_block_model(surface, _grid())
        self.assertEqual([f.rule_id for f in result.findings], ["GRID-001"])
        self.assertEqual(result.findings[0].severity, "WARNING")

    def test_result_is_reproducible(self):
        points = _lattice(lambda x, y: 100.0 + 0.1 * y)
        first = build_block_model(TopographySurface(points), _grid())
        second = build_block_model(TopographySurface(points), _grid())
        self.assertEqual(first.blocks, second.blocks)


class SurfaceTests(unittest.TestCase):
    def test_exact_hit_returns_the_point_elevation(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0 + x))
        self.assertEqual(surface.elevation(100.0, 100.0), 200.0)

    def test_interior_flat_value_is_recovered(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        self.assertAlmostEqual(surface.elevation(101.3, 97.1), 100.0, places=9)

    def test_edge_and_far_locations_are_not_extrapolated(self):
        surface = TopographySurface(_lattice(lambda x, y: 100.0))
        self.assertIsNone(surface.elevation(-30.0, 100.0))
        self.assertIsNone(surface.elevation(1000.0, 1000.0))

    def test_isolated_point_has_no_coverage(self):
        surface = TopographySurface([(0.0, 0.0, 10.0)])
        self.assertIsNone(surface.elevation(5.0, 5.0))


class InputOutputTests(unittest.TestCase):
    def test_read_topography_reports_bad_rows_and_keeps_good_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "topo.csv"
            path.write_text("PID,X,Y,Z\n1,1.0,2.0,3.0\n2,abc,2.0,3.0\n3,1.0,2.0,nan\n")
            points, findings = read_topography(path)
        self.assertEqual(points, [(1.0, 2.0, 3.0)])
        self.assertEqual([f.rule_id for f in findings], ["TOPO-002", "TOPO-002"])

    def test_missing_topography_is_an_error_not_an_invented_file(self):
        points, findings = read_topography("does/not/exist.csv")
        self.assertEqual(points, [])
        self.assertEqual([f.rule_id for f in findings], ["TOPO-001"])

    def test_summary_counts_add_up_and_csv_is_written(self):
        surface = TopographySurface(_lattice(lambda x, y: 105.0))
        result = build_block_model(surface, _grid())
        summary = summarize_block_model(result)
        self.assertEqual(sum(summary["counts"].values()), summary["n_blocks"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sub" / "blocks.csv"
            write_block_model_csv(result.blocks, path)
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(rows[0].keys()), CSV_COLUMNS)
        self.assertEqual(len(rows), 64)
        self.assertEqual({r["topo_state"] for r in rows}, {STATE_ROCK, STATE_PARTIAL, STATE_AIR})


if __name__ == "__main__":
    unittest.main()
