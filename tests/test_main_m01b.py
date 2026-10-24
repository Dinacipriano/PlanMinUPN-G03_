import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main


class StageDispatchTests(unittest.TestCase):
    def test_default_stage_does_not_run_m01b(self) -> None:
        with (
            patch("main.run_m01b_stage") as stage,
            patch("main.load_m01_data"),
            patch("main.validate_m01_data"),
            patch("main.print_validation_report"),
        ):
            self.assertEqual(main.main([]), 0)
        stage.assert_not_called()

    def test_m01b_stage_returns_zero_unless_validation_fails(self) -> None:
        for overall, expected in (("PASS", 0), ("WARNING", 0), ("FAIL", 1)):
            with patch("main.run_m01b_stage", return_value=overall) as stage:
                self.assertEqual(main.main(["--stage", "m01b"]), expected)
            stage.assert_called_once_with()

    def test_unknown_stage_is_rejected(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main.main(["--stage", "m99"])
        self.assertEqual(raised.exception.code, 2)


class StageOrderTests(unittest.TestCase):
    def test_m01b_steps_run_in_order_and_only_orchestrate(self) -> None:
        calls: list[str] = []

        def fake(name, result):
            def runner(*args, **kwargs):
                calls.append(name)
                return result

            return runner

        class FakeValidation:
            overall = "PASS"
            counts = {"PASS": 1, "WARNING": 0, "FAIL": 0}

        comp = {"composites": 1, "residual_composites": 0, "meters_difference": 0.0, "findings": 0}
        blocks = {
            "n_blocks": 1,
            "counts": {"ROCK": 1, "PARTIAL": 0, "AIR": 0, "OUTSIDE_TOPO_COVERAGE": 0},
            "n_findings": 0,
        }
        domains = {
            "n_rock_blocks": 1,
            "status_counts": {
                "ASSIGNED_SUPPORTED": 1,
                "ASSIGNED_EXTRAPOLATED": 0,
                "UNKNOWN_NO_SUPPORT": 0,
            },
        }
        with (
            patch("main.run_m01b_compositing", fake("compositing", (None, comp))),
            patch("main.run_m01b_block_model", fake("block_model", (None, blocks))),
            patch("main.run_m01b_domain_assignment", fake("domains", (None, domains))),
            patch("main.run_m01b_block_validation", fake("validation", FakeValidation())),
            patch("main.run_m01b_visualizer", fake("viewer", None)),
            redirect_stdout(io.StringIO()),
        ):
            overall = main.run_m01b_stage("unused-dir")
        self.assertEqual(overall, "PASS")
        self.assertEqual(calls, ["compositing", "block_model", "domains", "validation", "viewer"])


class RealDataIntegrationTests(unittest.TestCase):
    """Runs M01B on the real release, writing only into a temporary folder."""

    def test_full_stage_on_real_data_has_no_fail(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            with redirect_stdout(io.StringIO()) as output:
                overall = main.run_m01b_stage(
                    base / "processed", base / "report.md", base / "figures" / "viewer.html"
                )
            self.assertNotEqual(overall, "FAIL")
            for name in ("composites.csv", "blocks_topo.csv", "blocks_domains.csv"):
                self.assertTrue((base / "processed" / name).is_file(), name)
            self.assertTrue((base / "report.md").is_file())
            self.assertTrue((base / "figures" / "viewer.html").is_file())
        text = output.getvalue()
        for prefix in ("M01B compositing:", "M01B block model:", "M01B domains:", "M01B validation:"):
            self.assertIn(prefix, text)


if __name__ == "__main__":
    unittest.main()
