"""Optimisation tab helpers (no Streamlit): default design variables, tables and charts."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import numpy as np
import plotly.graph_objects as go

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.mdo.optimise import OptimisationSummary
    from predimrc_wrapper.mdo.parameters import Parameter

OBJECTIVE_LABELS = {"flight_time": "Maximise the flight time", "range": "Maximise the range",
                    "mass_total": "Minimise the total mass"}
UNITS = {"flight_time": ("min", 1 / 60), "range": ("km", 1e-3), "mass_total": ("kg", 1.0),
         "flight_time_v1": ("min", 1 / 60), "flight_time_v2": ("min", 1 / 60), "range_v1": ("km", 1e-3),
         "range_v2": ("km", 1e-3)}
MARGINS = ("margin_motor_current", "margin_motor_power", "margin_voltage", "margin_battery_c",
           "margin_thrust_to_weight", "margin_mass")


def default_variables(project: Project) -> list[dict[str, Any]]:
    """Continuous variables offered: battery, propeller diameters, wing panel spans (quadplane)."""
    rows = []
    if project.battery.mode == "mass":
        m = project.battery.mass_g
        rows.append({"use": True, "name": "battery_mass_g", "path": "battery.mass_g",
                     "lower": round(0.5 * m), "upper": round(1.8 * m)})
    else:
        c = project.battery.capacity_mah
        rows.append({"use": True, "name": "battery_capacity_mah", "path": "battery.capacity_mah",
                     "lower": round(0.5 * c), "upper": round(1.8 * c)})
    for name, unit in project.propulsion_units.items():
        d = unit.prop_diameter_in
        rows.append({"use": True, "name": f"{name}_prop_diameter_in", "path": f"propulsion_units.{name}.prop_diameter_in",
                     "lower": max(4.0, d - 2.0), "upper": d + 2.0})
    if project.aero is not None:
        for i, length in enumerate(project.aero.wing.length_mm):
            rows.append({"use": False, "name": f"wing_panel_{i + 1}_mm", "path": f"aero.wing.length_mm.{i}",
                         "lower": round(0.8 * length), "upper": round(1.2 * length)})
    return rows


def to_parameters(rows: list[dict[str, Any]]) -> list[Parameter]:
    """The selected rows as continuous design parameters.

    Raises:
        ValueError: For a row with lower ≥ upper.
    """
    from predimrc_wrapper.mdo import Parameter  # noqa: PLC0415

    out = []
    for r in rows:
        if not r.get("use"):
            continue
        lower, upper = float(r["lower"]), float(r["upper"])
        if not lower < upper:
            msg = f"{r['name']}: the lower bound must be below the upper bound."
            raise ValueError(msg)
        out.append(Parameter(str(r["name"]), str(r["path"]), "float", lower, upper))
    return out


def run_rows(summary: OptimisationSummary) -> list[dict[str, Any]]:
    """One row per discrete choice: choice, optimum, objective, feasibility, margins."""
    unit, scale = UNITS[summary.objective]
    best = summary.best
    rows = []
    for r in summary.runs:
        row = {"best": r is best, **{k.split(".")[-2] if k.count(".") >= 2 else k: v for k, v in r.choice.items()}}
        row.update({k: round(v, 2) for k, v in r.x.items()})
        value = r.outputs.get(summary.objective, np.nan)
        row[f"{summary.objective} ({unit})"] = round(value * scale, 3) if np.isfinite(value) else None
        row["feasible"] = r.feasible
        row.update({m[7:]: round(r.outputs[m], 3) for m in MARGINS if np.isfinite(r.outputs.get(m, np.nan))})
        row["evaluations"] = len(r.history)
        row["error"] = r.error
        rows.append(row)
    return rows


def history_figure(summary: OptimisationSummary) -> go.Figure:
    """Objective versus evaluation for each discrete choice."""
    unit, scale = UNITS[summary.objective]
    fig = go.Figure()
    for r in summary.runs:
        if r.history:
            label = ", ".join(str(v) for v in r.choice.values()) or "design"
            fig.add_trace(go.Scatter(y=np.asarray(r.history) * scale, mode="lines+markers", name=label,
                                     marker={"size": 4}, line={"width": 3 if r is summary.best else 1.5}))
    fig.update_layout(title="Convergence", xaxis_title="evaluation", yaxis_title=f"{summary.objective} ({unit})",
                      height=380, margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig
