"""PlanMinUPN student project entry point.

La lógica minera no debe concentrarse en este archivo. Los módulos se incorporarán
progresivamente durante el curso conforme exista una necesidad de ingeniería real.
"""

from collections import Counter

from src.m01.loader import load_m01_data
from src.m01.validator import ValidationReport, validate_m01_data


def print_validation_report(report: ValidationReport) -> None:
    """Print validation counts and traceable findings."""
    print(
        "M01 validation: "
        f"{report.error_count} ERROR, "
        f"{report.warning_count} WARNING, "
        f"{report.info_count} INFO"
    )
    if not report.findings:
        print("No findings.")
        return

    finding_counts = Counter(
        (finding.severity, finding.rule_id) for finding in report.findings
    )
    examples = {
        (finding.severity, finding.rule_id): finding
        for finding in reversed(report.findings)
    }
    for (severity, rule_id), count in sorted(finding_counts.items()):
        finding = examples[(severity, rule_id)]
        location = finding.table
        if finding.row_number is not None:
            location += f", row {finding.row_number}"
        if finding.hole_id is not None:
            location += f", hole_id {finding.hole_id}"
        if finding.sample_id is not None:
            location += f", sample_id {finding.sample_id}"
        if finding.field is not None:
            location += f", field {finding.field}"

        print(
            f"[{finding.severity}] {finding.rule_id} ({count} finding(s)) — "
            f"{location}: example_observed={finding.observed_value!r}; "
            f"expected={finding.expected_condition}"
        )


def main() -> None:
    """Load and validate the default M01 release."""
    data = load_m01_data()
    report = validate_m01_data(data)
    print_validation_report(report)


if __name__ == "__main__":
    main()
