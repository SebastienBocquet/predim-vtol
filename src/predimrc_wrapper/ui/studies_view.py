"""Exploration, optimisation and studies tabs: default variables, tables, charts (no Streamlit)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import numpy as np
import plotly.graph_objects as go

if TYPE_CHECKING:
    from predimrc_wrapper.mdo.studies import Study

OUTPUT_LABELS = {
    "flight_time_v1": ("Flight time V1", "min", 1 / 60), "flight_time_v2": ("Flight time V2", "min", 1 / 60),
    "range_v1": ("Range V1", "km", 1e-3), "range_v2": ("Range V2", "km", 1e-3), "mass_total": ("Total mass", "kg", 1.0),
    "hover_power": ("Hover power (battery)", "W", 1.0), "cruise_power_v1": ("Cruise power V1 (battery)", "W", 1.0),
    "cruise_power_v2": ("Cruise power V2 (battery)", "W", 1.0), "flight_time": ("Flight time (scenario)", "min", 1 / 60),
    "range": ("Range (scenario)", "km", 1e-3),
}


def numeric_columns(points: list[dict[str, Any]]) -> list[str]:
    cols = list(dict.fromkeys(k for p in points for k in p))
    return [c for c in cols if c not in ("error", "history", "constraints_applied")
            and all(isinstance(p.get(c), (int, float)) or p.get(c) is None for p in points)]


def label(column: str) -> str:
    name, unit, _ = OUTPUT_LABELS.get(column, (column, "", 1.0))
    return f"{name} ({unit})" if unit else name


def _scaled(points: list[dict], column: str) -> np.ndarray:
    scale = OUTPUT_LABELS.get(column, ("", "", 1.0))[2]
    return np.array([np.nan if p.get(column) is None else float(p[column]) * scale for p in points])


def choice_label(point: dict, choices: dict) -> str:
    return ", ".join(str(point.get(k)) for k in choices) or "design"


def scatter_figure(studies: list[Study], x: str, y: str, pareto: list[np.ndarray] | None = None) -> go.Figure:
    """Any output against any input, coloured by study and choice; infeasible points hollow; Pareto ringed."""
    fig = go.Figure()
    for s_i, study in enumerate(studies):
        groups: dict[str, list[int]] = {}
        for i, p in enumerate(study.points):
            groups.setdefault(choice_label(p, study.definition.choices), []).append(i)
        for name, idx in groups.items():
            pts = [study.points[i] for i in idx]
            ok = np.array([bool(p.get("feasible")) for p in pts])
            prefix = f"{study.name}: " if len(studies) > 1 else ""
            fig.add_trace(go.Scatter(x=_scaled(pts, x), y=_scaled(pts, y), mode="markers", name=prefix + name,
                                     marker={"symbol": np.where(ok, ["circle"] * len(ok), ["circle-open"] * len(ok)),
                                             "size": 9}))
        if pareto is not None and s_i < len(pareto) and pareto[s_i].any():
            front = [p for p, m in zip(study.points, pareto[s_i]) if m]
            order = np.argsort(_scaled(front, x))
            fig.add_trace(go.Scatter(x=_scaled(front, x)[order], y=_scaled(front, y)[order], mode="lines+markers",
                                     name="Pareto front" + (f" {study.name}" if len(studies) > 1 else ""),
                                     line={"color": "black", "dash": "dot"},
                                     marker={"size": 14, "symbol": "circle-open", "color": "black"}))
    fig.update_layout(xaxis_title=label(x), yaxis_title=label(y), height=460, margin={"l": 10, "r": 10, "t": 30, "b": 10},
                      title="Hollow markers: infeasible points")
    return fig


def point_rows(study: Study) -> list[dict]:
    """Points with readable output units."""
    rows = []
    for p in study.points:
        row = {}
        for k, v in p.items():
            if k in ("history", "constraints_applied"):
                continue
            if k in OUTPUT_LABELS and isinstance(v, (int, float)) and v is not None:
                row[label(k)] = round(v * OUTPUT_LABELS[k][2], 3)
            else:
                row[k] = round(v, 4) if isinstance(v, float) else v
        rows.append(row)
    return rows


def overrides_of(study: Study, index: int) -> dict[str, Any]:
    """Project overrides reproducing one point of a study (choices and variables)."""
    p = study.points[index]
    out = {k: p[k] for k in study.definition.choices}
    out.update({v["path"]: p[v["name"]] for v in study.definition.variables if p.get(v["name"]) is not None})
    return out
