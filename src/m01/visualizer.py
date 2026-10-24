"""Interactive 3D HTML view of M01 exploration data (topography, collars,
drillhole trajectories and positioned intervals) built with Plotly.

This module only draws results that the pipeline already computed
(``DesurveyResult`` and ``PositioningResult``); it does not recompute
desurvey or positioning. Plotly is imported lazily so the rest of the
project keeps working without it.

Coordinates are in the dataset's local Cartesian system (metres). The
CRS/EPSG is not documented; per the teacher's DECISION-06 this is an
accepted non-blocking limitation and no global location is implied.
"""

from collections import Counter
from math import isfinite
from pathlib import Path

from src.m01.desurvey import DesurveyResult
from src.m01.loader import M01Data, TableRecord
from src.m01.positioning import PositionedInterval, PositioningResult

DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[2] / "outputs" / "figures" / "m01_exploration_3d.html"
)

LITHOLOGY_COLORS = {
    "DIO": "#4c78a8",
    "POR": "#e45756",
    "BRX": "#f58518",
    "REG": "#b8a07e",
    "AIR": "#9aa5ad",
}
OTHER_COLOR = "#54a24b"

_TABLES = {"lithology": "lithology", "assay": "assay", "density": "density", "alteration": "alteration"}


def _require_plotly():
    try:
        import plotly.graph_objects as go
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "Plotly is required for the M01 visualization. Install it in the "
            "project environment with: pip install plotly"
        ) from error
    return go


def sample_topography(surface, x_range, y_range, step_m=25.0):
    """Evaluate a TopographySurface on a regular grid; None where uncovered."""
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    x0, x1 = x_range
    y0, y1 = y_range
    nx = int((x1 - x0) // step_m) + 1
    ny = int((y1 - y0) // step_m) + 1
    xs = [x0 + i * step_m for i in range(nx)]
    ys = [y0 + j * step_m for j in range(ny)]
    zs = [[surface.elevation(x, y) for x in xs] for y in ys]
    return {"x": xs, "y": ys, "z": zs}


def source_record(data: M01Data, interval: PositionedInterval) -> TableRecord | None:
    """Source row of a positioned interval (row numbers start at 2, after the header)."""
    table = getattr(data, _TABLES.get(interval.table, ""), None)
    if table is None:
        return None
    index = interval.row_number - 2
    if 0 <= index < len(table.records):
        return table.records[index]
    return None


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _segments(intervals, hover):
    """x, y, z, text lists with None separators, one segment per interval."""
    xs, ys, zs, text = [], [], [], []
    for interval in intervals:
        for point in (interval.from_xyz, interval.to_xyz):
            xs.append(point[0])
            ys.append(point[1])
            zs.append(point[2])
            text.append(hover(interval))
        xs.append(None)
        ys.append(None)
        zs.append(None)
        text.append(None)
    return xs, ys, zs, text


def summarize_figure_inputs(data: M01Data, desurvey: DesurveyResult, positioning: PositioningResult):
    """Counts of what will be drawn, for reporting and tests."""
    by_table = Counter(item.table for item in positioning.intervals)
    return {
        "collars": len(data.collar.records),
        "trajectories": len(desurvey.trajectories),
        "intervals": dict(sorted(by_table.items())),
    }


def build_exploration_figure(
    data: M01Data,
    desurvey: DesurveyResult,
    positioning: PositioningResult,
    topography: dict | None = None,
):
    """Build the Plotly figure from precomputed pipeline results."""
    go = _require_plotly()
    fig = go.Figure()

    if topography is not None:
        fig.add_trace(
            go.Surface(
                x=topography["x"],
                y=topography["y"],
                z=topography["z"],
                name="Topografía",
                showscale=False,
                showlegend=True,
                opacity=0.55,
                colorscale=[[0, "#d9d2c3"], [1, "#8c8573"]],
                hovertemplate="X %{x:.0f} m<br>Y %{y:.0f} m<br>Z %{z:.1f} m<extra>Topografía</extra>",
            )
        )

    collars = data.collar.records
    fig.add_trace(
        go.Scatter3d(
            x=[c["x"] for c in collars],
            y=[c["y"] for c in collars],
            z=[c["z"] for c in collars],
            mode="markers+text",
            text=[c["hole_id"].split("-", 1)[-1] for c in collars],
            textposition="top center",
            textfont={"size": 9},
            marker={"size": 4, "color": "#111111", "symbol": "diamond"},
            name="Collares",
            hovertext=[
                f"{c['hole_id']}<br>az {c['azimuth_deg']:.1f}°, dip {c['dip_deg']:.1f}°"
                f"<br>prof. final {c['final_depth_m']:.1f} m"
                for c in collars
            ],
            hoverinfo="text",
        )
    )

    tx, ty, tz, tt = [], [], [], []
    for trajectory in desurvey.trajectories:
        for point in trajectory.points:
            tx.append(point.x)
            ty.append(point.y)
            tz.append(point.z)
            tt.append(f"{trajectory.hole_id}<br>MD {point.depth_m:.1f} m")
        tx.append(None)
        ty.append(None)
        tz.append(None)
        tt.append(None)
    fig.add_trace(
        go.Scatter3d(
            x=tx, y=ty, z=tz, mode="lines",
            line={"color": "#6b7780", "width": 2},
            name="Trayectorias", hovertext=tt, hoverinfo="text",
        )
    )

    lithology = [i for i in positioning.intervals if i.table == "lithology"]
    codes = []
    for interval in lithology:
        record = source_record(data, interval)
        code = str(record.get("lith_code", "")).strip() if record else ""
        codes.append(code or "SIN CÓDIGO")
    for code in sorted(set(codes)):
        subset = [i for i, c in zip(lithology, codes) if c == code]
        xs, ys, zs, text = _segments(
            subset,
            lambda i, code=code: f"{i.hole_id}<br>{code}<br>{i.from_m:.1f}–{i.to_m:.1f} m",
        )
        fig.add_trace(
            go.Scatter3d(
                x=xs, y=ys, z=zs, mode="lines",
                line={"color": LITHOLOGY_COLORS.get(code, OTHER_COLOR), "width": 7},
                name=f"Litología {code}", hovertext=text, hoverinfo="text",
            )
        )

    assay = []
    for interval in positioning.intervals:
        if interval.table != "assay":
            continue
        record = source_record(data, interval)
        cu = _finite(record.get("cu_pct")) if record else None
        if cu is not None:
            assay.append((interval, cu))
    if assay:
        xs, ys, zs, colors, text = [], [], [], [], []
        for interval, cu in assay:
            label = f"{interval.hole_id}<br>{interval.sample_id or ''}<br>Cu {cu:.3f} %<br>{interval.from_m:.1f}–{interval.to_m:.1f} m"
            for point in (interval.from_xyz, interval.to_xyz):
                xs.append(point[0]); ys.append(point[1]); zs.append(point[2])
                colors.append(cu); text.append(label)
            xs.append(None); ys.append(None); zs.append(None)
            colors.append(float("nan")); text.append(None)
        fig.add_trace(
            go.Scatter3d(
                x=xs, y=ys, z=zs, mode="lines",
                line={
                    "color": colors, "width": 7, "colorscale": "YlOrRd",
                    "cmin": 0, "cmax": max(cu for _, cu in assay) or 1,
                    "colorbar": {"title": "Cu (%)", "len": 0.5},
                },
                name="Assay Cu (%)", hovertext=text, hoverinfo="text",
                visible="legendonly",
            )
        )

    counts = summarize_figure_inputs(data, desurvey, positioning)
    fig.update_layout(
        title={
            "text": "M01 — Exploración 3D: topografía, collares, trayectorias e intervalos",
            "font": {"size": 15},
        },
        scene={
            "xaxis": {"title": "X local (m)"},
            "yaxis": {"title": "Y local (m)"},
            "zaxis": {"title": "Z (m)"},
            "aspectmode": "data",
        },
        legend={"itemsizing": "constant"},
        margin={"l": 0, "r": 0, "t": 50, "b": 40},
        annotations=[
            {
                "text": (
                    f"{counts['collars']} collares, {counts['trajectories']} trayectorias, "
                    f"intervalos posicionados {counts['intervals']}. Sistema cartesiano local en metros; "
                    "CRS/EPSG no consta (limitación no bloqueante, DECISION-06 del docente). "
                    "Assay Cu: activar en la leyenda."
                ),
                "xref": "paper", "yref": "paper", "x": 0, "y": -0.02,
                "showarrow": False, "font": {"size": 10}, "xanchor": "left",
            }
        ],
    )
    return fig


def write_exploration_html(fig, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Write a self-contained interactive HTML file (Plotly JS embedded)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(path), include_plotlyjs=True, full_html=True)
    return path
