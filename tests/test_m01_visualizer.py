import json
import re
import tempfile
import unittest
from pathlib import Path

from src.m01.desurvey import DesurveyResult, HoleTrajectory, TrajectoryPoint
from src.m01.loader import LoadedTable, M01Data
from src.m01.positioning import PositionedInterval, PositioningResult
from src.m01.visualizer import (
    build_exploration_figure,
    sample_topography,
    source_record,
    summarize_figure_inputs,
    write_exploration_html,
)

try:  # Plotly is an optional dependency of the project
    import plotly  # noqa: F401

    HAS_PLOTLY = True
except ImportError:  # pragma: no cover
    HAS_PLOTLY = False

# SYNTHETIC FIXTURES: invented rows for tests only; not data of the deposit.


def _table(columns, records):
    return LoadedTable(columns=tuple(columns), records=list(records))


def _data():
    empty = _table(("hole_id",), [])
    collar = _table(
        ("hole_id", "x", "y", "z", "azimuth_deg", "dip_deg", "final_depth_m"),
        [
            {"hole_id": "T-001", "x": 0.0, "y": 0.0, "z": 100.0, "azimuth_deg": 90.0, "dip_deg": -90.0, "final_depth_m": 20.0},
            {"hole_id": "T-002", "x": 50.0, "y": 0.0, "z": 100.0, "azimuth_deg": 0.0, "dip_deg": -60.0, "final_depth_m": 20.0},
        ],
    )
    lithology = _table(
        ("hole_id", "from_m", "to_m", "lith_code"),
        [
            {"hole_id": "T-001", "from_m": 0.0, "to_m": 10.0, "lith_code": "POR"},
            {"hole_id": "T-001", "from_m": 10.0, "to_m": 20.0, "lith_code": "XYZ"},
        ],
    )
    assay = _table(
        ("sample_id", "hole_id", "from_m", "to_m", "cu_pct"),
        [
            {"sample_id": "S1", "hole_id": "T-001", "from_m": 0.0, "to_m": 2.0, "cu_pct": 0.5},
            {"sample_id": "S2", "hole_id": "T-001", "from_m": 2.0, "to_m": 4.0, "cu_pct": ""},
        ],
    )
    return M01Data(
        collar=collar, survey=empty, lithology=lithology, alteration=empty, assay=assay,
        density=empty, data_dictionary=empty, release_manifest={}, readme="",
    )


def _desurvey():
    def traj(name, x):
        points = tuple(
            TrajectoryPoint(name, depth, x, 0.0, 100.0 - depth, (0.0, 0.0, -1.0))
            for depth in (0.0, 10.0, 20.0)
        )
        return HoleTrajectory(name, points)

    return DesurveyResult((traj("T-001", 0.0), traj("T-002", 50.0)), ())


def _interval(table, row, from_m, to_m, sample_id=None):
    return PositionedInterval(
        table, row, "T-001", from_m, to_m,
        (0.0, 0.0, 100.0 - from_m), (0.0, 0.0, 100.0 - to_m), sample_id,
    )


def _positioning():
    return PositioningResult(
        (
            _interval("lithology", 2, 0.0, 10.0),
            _interval("lithology", 3, 10.0, 20.0),
            _interval("assay", 2, 0.0, 2.0, "S1"),
            _interval("assay", 3, 2.0, 4.0, "S2"),
        ),
        (),
    )


class HelperTests(unittest.TestCase):
    def test_source_record_uses_row_numbers_that_start_after_the_header(self):
        data = _data()
        self.assertEqual(source_record(data, _interval("lithology", 2, 0, 10))["lith_code"], "POR")
        self.assertEqual(source_record(data, _interval("lithology", 3, 10, 20))["lith_code"], "XYZ")
        self.assertIsNone(source_record(data, _interval("lithology", 99, 0, 1)))
        self.assertIsNone(source_record(data, _interval("unknown_table", 2, 0, 1)))

    def test_summary_counts_inputs(self):
        summary = summarize_figure_inputs(_data(), _desurvey(), _positioning())
        self.assertEqual(summary["collars"], 2)
        self.assertEqual(summary["trajectories"], 2)
        self.assertEqual(summary["intervals"], {"assay": 2, "lithology": 2})

    def test_sample_topography_keeps_none_where_uncovered(self):
        class Flat:
            def elevation(self, x, y):
                return 10.0 if x < 20 else None

        grid = sample_topography(Flat(), (0.0, 40.0), (0.0, 20.0), step_m=10.0)
        self.assertEqual(grid["x"], [0.0, 10.0, 20.0, 30.0, 40.0])
        self.assertEqual(len(grid["z"]), 3)
        self.assertEqual(grid["z"][0], [10.0, 10.0, None, None, None])

    def test_sample_topography_rejects_non_positive_step(self):
        with self.assertRaises(ValueError):
            sample_topography(object(), (0, 1), (0, 1), step_m=0)


@unittest.skipUnless(HAS_PLOTLY, "plotly is not installed")
class FigureTests(unittest.TestCase):
    def test_trace_names_cover_the_requested_layers(self):
        topography = {"x": [0.0, 10.0], "y": [0.0, 10.0], "z": [[1.0, 1.0], [1.0, None]]}
        fig = build_exploration_figure(_data(), _desurvey(), _positioning(), topography)
        names = [trace.name for trace in fig.data]
        for expected in ("Topografía", "Collares", "Trayectorias", "Litología POR", "Litología XYZ", "Assay Cu (%)"):
            self.assertIn(expected, names)

    def test_topography_is_optional(self):
        fig = build_exploration_figure(_data(), _desurvey(), _positioning(), None)
        self.assertNotIn("Topografía", [trace.name for trace in fig.data])

    def test_assay_without_cu_is_skipped_and_layer_starts_hidden(self):
        fig = build_exploration_figure(_data(), _desurvey(), _positioning())
        assay = next(trace for trace in fig.data if trace.name == "Assay Cu (%)")
        self.assertEqual(assay.visible, "legendonly")
        # one valid interval -> 2 points + 1 separator
        self.assertEqual(len(assay.x), 3)

    def test_collars_and_trajectories_use_precomputed_coordinates(self):
        fig = build_exploration_figure(_data(), _desurvey(), _positioning())
        collars = next(trace for trace in fig.data if trace.name == "Collares")
        self.assertEqual(list(collars.x), [0.0, 50.0])
        trajectories = next(trace for trace in fig.data if trace.name == "Trayectorias")
        # 2 holes * (3 points + 1 separator)
        self.assertEqual(len(trajectories.x), 8)
        self.assertIsNone(trajectories.x[3])

    def test_html_is_self_contained_and_written_with_folders(self):
        fig = build_exploration_figure(_data(), _desurvey(), _positioning())
        with tempfile.TemporaryDirectory() as folder:
            path = write_exploration_html(fig, Path(folder) / "figures" / "m01.html")
            text = path.read_text(encoding="utf-8")
        self.assertIn("plotly-graph-div", text)
        self.assertNotIn('src="https://cdn.plot.ly', text)
        self.assertGreater(len(text), 1_000_000)  # Plotly JS is embedded


class MissingPlotlyTests(unittest.TestCase):
    def test_clear_error_when_plotly_is_missing(self):
        import builtins
        from unittest.mock import patch

        real_import = builtins.__import__

        def fake(name, *args, **kwargs):
            if name.startswith("plotly"):
                raise ImportError("no plotly")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake):
            with self.assertRaises(RuntimeError) as raised:
                build_exploration_figure(_data(), _desurvey(), _positioning())
        self.assertIn("pip install plotly", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
