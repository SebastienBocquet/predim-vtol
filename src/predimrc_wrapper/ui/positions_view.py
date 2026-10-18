"""Motor positions with their dimensions, drawn from the raw motor table (REQ-UI-002, REQ-CFG-002).

Drawn even when the project is invalid (e.g. overlapping propellers), so the designer sees
what to fix. Top view like the geometry: y horizontal (right-positive), x downward (aft).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import plotly.graph_objects as go

INCH_MM = 25.4
ROLE_COLORS = {"lift": "#1f77b4", "cruise": "#ff7f0e", "tilt": "#9467bd"}


def _diameter_mm(units: dict[str, Any], unit: str | None) -> float | None:
    spec = units.get(unit) if unit else None
    d = (spec or {}).get("prop_diameter_in")
    return None if d is None else float(d) * INCH_MM


def overlapping(motors: list[dict], units: dict[str, Any]) -> set[int]:
    """Indexes of the lift / tilt motors whose propeller discs overlap another one."""
    out = set()
    lift = [
        (i, m)
        for i, m in enumerate(motors)
        if m.get("role", "lift") in ("lift", "tilt")
        and _diameter_mm(units, m.get("unit")) is not None
    ]
    for k, (i, a) in enumerate(lift):
        for j, b in lift[k + 1 :]:
            gap = np.hypot(a["x_mm"] - b["x_mm"], a["y_mm"] - b["y_mm"])
            radii = (
                _diameter_mm(units, a["unit"]) + _diameter_mm(units, b["unit"])
            ) / 2
            if gap < radii - 1e-6:
                out |= {i, j}
    return out


def _dimension(
    fig: go.Figure,
    start: tuple[float, float],
    end: tuple[float, float],
    text: str,
    vertical: bool,
) -> None:
    """A dotted dimension line (plot coordinates: y horizontal, x vertical) with its value."""
    fig.add_trace(
        go.Scatter(
            x=[start[0], end[0]],
            y=[start[1], end[1]],
            mode="lines",
            line={"color": "grey", "width": 1, "dash": "dot"},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        x=(start[0] + end[0]) / 2,
        y=(start[1] + end[1]) / 2,
        text=text,
        showarrow=False,
        textangle=-90 if vertical else 0,
        xshift=(9 if end[0] >= 0 else -9) if vertical else 0,
        yshift=0 if vertical else 9,
        font={"size": 10, "color": "dimgrey"},
    )


def positions_figure(
    motors: list[dict],
    units: dict[str, Any],
    winged: bool,
    cg_x_mm: float | None = None,
) -> go.Figure:
    """Motors, propeller discs, the reference point and the x / y dimensions of each motor."""
    fig = go.Figure()
    origin = "wing root leading edge" if winged else "frame centre"
    clash = overlapping(motors, units)
    valid = [
        (i, m)
        for i, m in enumerate(motors)
        if m.get("x_mm") is not None and m.get("y_mm") is not None
    ]
    span = max([abs(m["y_mm"]) for _, m in valid] + [100.0])
    for i, m in valid:
        x, y = float(m["x_mm"]), float(m["y_mm"])
        role = m.get("role") or "lift"
        color = ROLE_COLORS.get(role, "grey")
        d = _diameter_mm(units, m.get("unit"))
        if d is not None and role == "cruise":  # pusher / tractor disc seen edge-on
            fig.add_trace(
                go.Scatter(
                    x=[y - d / 2, y + d / 2],
                    y=[x, x],
                    mode="lines",
                    line={"color": color, "width": 3},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        elif d is not None:
            t = np.linspace(0, 2 * np.pi, 60)
            fig.add_trace(
                go.Scatter(
                    x=y + d / 2 * np.cos(t),
                    y=x + d / 2 * np.sin(t),
                    mode="lines",
                    line={
                        "color": "red" if i in clash else color,
                        "width": 2 if i in clash else 1,
                    },
                    fill="toself",
                    fillcolor="rgba(255,0,0,0.15)" if i in clash else "rgba(0,0,0,0)",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        # Dimension lines: y along the station of the motor, x along its lateral position.
        dims = []
        if abs(y) > 0.5:
            dims.append("y")
        if abs(x) > 0.5:
            dims.append("x")
        if "y" in dims:
            _dimension(fig, (0.0, x), (y, x), f"y = {y:g}", vertical=False)
        if "x" in dims:
            _dimension(fig, (y, 0.0), (y, x), f"x = {x:g}", vertical=True)
        fig.add_trace(
            go.Scatter(
                x=[y],
                y=[x],
                mode="markers+text",
                text=[str(i + 1)],
                textposition="middle right" if y >= 0 else "middle left",
                textfont={"size": 14, "color": "red" if i in clash else color},
                marker={"size": 10, "color": color},
                name=f"{role} motor",
                legendgroup=role,
                showlegend=not any(t.name == f"{role} motor" for t in fig.data),
                hovertext=f"motor {i + 1} ({m.get('unit')}, {role}): x = {x:g} mm, y = {y:g} mm"
                + (f", propeller {d / INCH_MM:g} in" if d is not None else ""),
                hoverinfo="text",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[0.0],
            y=[0.0],
            mode="markers+text",
            text=[f"origin: {origin}"],
            textposition="top center",
            marker={
                "symbol": "cross-thin",
                "size": 18,
                "line": {"width": 2, "color": "black"},
            },
            name=f"reference: {origin} (0, 0)",
        )
    )
    if cg_x_mm is not None:
        fig.add_trace(
            go.Scatter(
                x=[0.0],
                y=[cg_x_mm],
                mode="markers",
                marker={"symbol": "circle-x", "size": 12, "color": "black"},
                name=f"CG (x = {cg_x_mm:g} mm)",
            )
        )
    fig.add_shape(
        type="line",
        x0=-1.1 * span,
        x1=1.1 * span,
        y0=0,
        y1=0,
        line={"color": "black", "width": 1},
    )
    fig.update_layout(
        title=(
            "Motor positions (mm): x aft-positive, y right-positive, from the "
            + origin
            + (" — overlapping propellers in red" if clash else "")
        ),
        xaxis_title="y (mm), right →",
        yaxis_title="x (mm), aft ↓",
        height=480,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h"},
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1, autorange="reversed")
    return fig
