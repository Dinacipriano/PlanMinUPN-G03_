import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main
from src.m01.loader import load_m01_data
from src.m01.validator import validate_m01_data


class MainTests(unittest.TestCase):
    def test_main_loads_validates_and_prints_the_release_report(self) -> None:
        loaded_data = load_m01_data()
        with (
            patch("main.load_m01_data", return_value=loaded_data) as load_data,
            patch("main.validate_m01_data", wraps=validate_m01_data) as validate_data,
            redirect_stdout(io.StringIO()) as output,
        ):
            main.main()

        load_data.assert_called_once_with()
        validate_data.assert_called_once_with(loaded_data)
        self.assertIn("M01 validation: 0 ERROR, 1 WARNING, 261 INFO", output.getvalue())
        self.assertIn("[WARNING] RELEASE-001", output.getvalue())
        self.assertIn("[INFO] ALTERATION-001", output.getvalue())
        self.assertIn("[INFO] DENSITY-010 (258 finding(s))", output.getvalue())

    def test_report_printer_handles_empty_report(self) -> None:
        from src.m01.validator import ValidationReport

        with redirect_stdout(io.StringIO()) as output:
            main.print_validation_report(ValidationReport(()))

        self.assertEqual(
            output.getvalue(),
            "M01 validation: 0 ERROR, 0 WARNING, 0 INFO\nNo findings.\n",
        )


if __name__ == "__main__":
    unittest.main()
