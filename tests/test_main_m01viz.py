import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main

try:
    import plotly  # noqa: F401

    HAS_PLOTLY = True
except ImportError:  # pragma: no cover
    HAS_PLOTLY = False


class M01VizStageTests(unittest.TestCase):
    def test_stage_is_registered_and_dispatches_without_running_other_stages(self):
        self.assertIn("m01viz", main.STAGES)
        with (
            patch("main.run_m01_visualization") as viz,
            patch("main.run_m01b_stage") as stage_b,
        ):
            self.assertEqual(main.main(["--stage", "m01viz"]), 0)
        viz.assert_called_once_with()
        stage_b.assert_not_called()

    def test_default_stage_does_not_draw(self):
        with (
            patch("main.run_m01_visualization") as viz,
            patch("main.load_m01_data"),
            patch("main.validate_m01_data"),
            patch("main.print_validation_report"),
        ):
            self.assertEqual(main.main([]), 0)
        viz.assert_not_called()

    def test_orchestration_runs_pipeline_once_then_draws(self):
        calls = []
        with (
            patch("main.load_m01_data", side_effect=lambda: calls.append("load") or "data"),
            patch("main.validate_m01_data", side_effect=lambda d: calls.append("validate") or "report"),
            patch("main.desurvey_m01_data", side_effect=lambda d, r: calls.append("desurvey") or type("D", (), {"trajectories": ()})()),
            patch("main.position_m01_intervals", side_effect=lambda d, t: calls.append("positioning") or "pos"),
            patch("main.Path") as path_cls,
            patch("main.build_exploration_figure", side_effect=lambda *a: calls.append("figure") or "fig"),
            patch("main.write_exploration_html", side_effect=lambda f, p: calls.append("write") or Path(p)),
            patch("main.summarize_figure_inputs", return_value={"collars": 0, "trajectories": 0, "intervals": {}}),
            redirect_stdout(io.StringIO()),
        ):
            path_cls.return_value.is_file.return_value = False
            main.run_m01_visualization("unused.html")
        self.assertEqual(calls, ["load", "validate", "desurvey", "positioning", "figure", "write"])


@unittest.skipUnless(HAS_PLOTLY, "plotly is not installed")
class RealDataTests(unittest.TestCase):
    def test_real_release_produces_html_with_all_layers(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "m01_exploration_3d.html"
            with redirect_stdout(io.StringIO()):
                written = main.run_m01_visualization(target)
            text = written.read_text(encoding="utf-8")
        for name in ("Collares", "Trayectorias", "POR", "Assay Cu", "CA-C01-001"):
            self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
