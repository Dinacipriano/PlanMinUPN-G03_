"""PlanMinUPN student project entry point.

La lógica minera no debe concentrarse en este archivo. Los módulos se incorporarán
progresivamente durante el curso conforme exista una necesidad de ingeniería real.

Uso:
    python main.py                 # etapa m01: carga y validación (por defecto)
    python main.py --stage m01b    # compositado, grid, topografía, dominios, validación y visor 3D
    python main.py --stage m01viz  # desurvey + positioning + visualización 3D Plotly de M01 (requiere plotly)
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from src.m01.block_model import (
    DEFAULT_TOPOGRAPHY_PATH,
    TopographySurface,
    read_topography,
    run_m01b_block_model,
)
from src.m01.block_viewer import run_m01b_visualizer
from src.m01.block_validation import FAIL, run_m01b_block_validation
from src.m01.compositing import run_m01b_compositing
from src.m01.desurvey import desurvey_m01_data
from src.m01.domain_assignment import run_m01b_domain_assignment
from src.m01.loader import load_m01_data
from src.m01.positioning import position_m01_intervals
from src.m01.validator import ValidationReport, validate_m01_data
from src.m01.visualizer import (
    DEFAULT_OUTPUT_PATH as M01_FIGURE_PATH,
    build_exploration_figure,
    sample_topography,
    summarize_figure_inputs,
    write_exploration_html,
)

STAGES = ("m01", "m01b", "m01viz")
M01B_PROCESSED_DIR = Path(__file__).resolve().parent / "data" / "processed" / "m01b"


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


def run_m01b_stage(
    processed_dir: str | Path = M01B_PROCESSED_DIR,
    report_path: str | Path | None = None,
    figure_path: str | Path | None = None,
) -> str:
    """Run M01B in order and return the overall block validation status.

    Only orchestrates: composites -> block grid and topography -> domains ->
    independent validation -> 3D viewer. Each step lives in its own module.
    """
    processed = Path(processed_dir)
    composites_path = processed / "composites.csv"
    topo_path = processed / "blocks_topo.csv"
    domains_path = processed / "blocks_domains.csv"

    _, comp = run_m01b_compositing(composites_path)
    print(
        f"M01B compositing: {comp['composites']} composites "
        f"({comp['residual_composites']} residual), "
        f"meters difference {comp['meters_difference']:.6f} m, "
        f"{comp['findings']} finding(s)"
    )

    _, blocks = run_m01b_block_model(output_path=topo_path)
    counts = blocks["counts"]
    print(
        f"M01B block model: {blocks['n_blocks']} blocks "
        f"(ROCK {counts['ROCK']}, PARTIAL {counts['PARTIAL']}, AIR {counts['AIR']}, "
        f"OUTSIDE_TOPO_COVERAGE {counts['OUTSIDE_TOPO_COVERAGE']}), "
        f"{blocks['n_findings']} finding(s)"
    )

    _, domains = run_m01b_domain_assignment(composites_path, topo_path, domains_path)
    status = domains["status_counts"]
    print(
        f"M01B domains: {domains['n_rock_blocks']} rock blocks "
        f"(supported {status['ASSIGNED_SUPPORTED']}, "
        f"extrapolated {status['ASSIGNED_EXTRAPOLATED']}, "
        f"unknown {status['UNKNOWN_NO_SUPPORT']})"
    )

    report_kwargs = {} if report_path is None else {"report_path": report_path}
    validation = run_m01b_block_validation(
        topo_path, domains_path, composites_path, **report_kwargs
    )
    counts = validation.counts
    print(
        f"M01B validation: {validation.overall} "
        f"(PASS {counts['PASS']}, WARNING {counts['WARNING']}, FAIL {counts['FAIL']})"
    )

    figure_kwargs = {} if figure_path is None else {"output_path": figure_path}
    run_m01b_visualizer(
        domains_path=domains_path, composites_path=composites_path, **figure_kwargs
    )
    print("M01B viewer written.")
    return validation.overall


def run_m01_visualization(output_path: str | Path = M01_FIGURE_PATH) -> Path:
    """Run M01 once (load, validate, desurvey, positioning) and draw the results.

    Only orchestrates: the visualizer draws what desurvey and positioning
    already produced. The topography is optional and skipped if unavailable.
    """
    data = load_m01_data()
    report = validate_m01_data(data)
    desurvey = desurvey_m01_data(data, report)
    positioning = position_m01_intervals(data, desurvey.trajectories)

    topography = None
    if Path(DEFAULT_TOPOGRAPHY_PATH).is_file():
        points, _ = read_topography()
        xs = [float(c["x"]) for c in data.collar.records]
        ys = [float(c["y"]) for c in data.collar.records]
        pad = 150.0
        topography = sample_topography(
            TopographySurface(points),
            (min(xs) - pad, max(xs) + pad),
            (min(ys) - pad, max(ys) + pad),
        )
    figure = build_exploration_figure(data, desurvey, positioning, topography)
    written = write_exploration_html(figure, output_path)
    counts = summarize_figure_inputs(data, desurvey, positioning)
    print(
        f"M01 visualization: {counts['collars']} collars, {counts['trajectories']} trajectories, "
        f"intervals {counts['intervals']}, topography {'yes' if topography else 'no'} -> {written}"
    )
    return written


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PlanMinUPN pipeline")
    parser.add_argument("--stage", choices=STAGES, default="m01")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the selected stage; return 1 only if the M01B validation has a FAIL."""
    args = _parse_args(argv or [])
    if args.stage == "m01b":
        return 1 if run_m01b_stage() == FAIL else 0
    if args.stage == "m01viz":
        run_m01_visualization()
        return 0
    data = load_m01_data()
    report = validate_m01_data(data)
    print_validation_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
