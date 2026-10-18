"""Result views (REQ-UI-003): KPI tiles, mass breakdown, power curve, segment table."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go

if TYPE_CHECKING:
    from predimrc_wrapper.mission.solver import MissionResult


@dataclass
class Kpi:
    label: str
    value: float
    unit: str
    negative: bool = False

    def text(self) -> str:
        return (
            f"{self.value:+.2f}" if self.unit == "" else f"{self.value:.1f} {self.unit}"
        )


def kpis(result: MissionResult) -> list[Kpi]:
    """Main figures, then one tile per margin (negative margins flagged)."""
    tiles = [
        Kpi("Flight time", result.flight_time_min, "min"),
        Kpi("Range", result.range_km, "km"),
        Kpi("Best-endurance speed", 3.6 * result.v_endurance, "km/h"),
        Kpi("Best-range speed", 3.6 * result.v_range, "km/h"),
        Kpi("Total mass", result.mass_total_kg, "kg"),
    ]
    tiles += [
        Kpi(f"Margin {k.replace('_', ' ')}", v, "", bool(v < 0))
        for k, v in result.margins.items()
        if v is not None and np.isfinite(v)
    ]
    return tiles


def mass_figure(result: MissionResult) -> go.Figure:
    items = sorted(result.mass_breakdown.items(), key=operator.itemgetter(1))
    fig = go.Figure(
        go.Bar(x=[v * 1000 for _, v in items], y=[k for k, _ in items], orientation="h")
    )
    fig.update_layout(
        title=f"Mass breakdown — total {result.mass_total_kg:.2f} kg",
        xaxis_title="mass (g)",
        height=60 + 28 * len(items),
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def power_figure(result: MissionResult) -> go.Figure:
    """Battery, shaft and aerodynamic (D·V) power versus cruise speed; V_e and V_r marked."""
    s = result.cruise_sweep
    v, p, ok = (
        3.6 * np.asarray(s.v_m_s),
        np.asarray(s.battery_power_w),
        np.asarray(s.feasible, dtype=bool),
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=v[ok],
            y=p[ok],
            mode="lines+markers",
            name="battery (feasible)",
            marker={"size": 4},
        )
    )
    if (~ok).any():
        fig.add_trace(
            go.Scatter(
                x=v[~ok],
                y=p[~ok],
                mode="markers",
                name="battery (infeasible)",
                marker={"size": 4, "color": "lightgrey"},
            )
        )
    if s.shaft_power_w is not None:
        fig.add_trace(
            go.Scatter(
                x=v,
                y=np.asarray(s.shaft_power_w),
                mode="lines",
                name="shaft",
                line={"dash": "dash"},
            )
        )
    if s.aero_power_w is not None:
        fig.add_trace(
            go.Scatter(
                x=v,
                y=s.aero_power_w,
                mode="lines",
                name="aerodynamic D·V",
                line={"dash": "dot"},
            )
        )
    for speed, name, dash in (
        (s.v_endurance, "V endurance", "dash"),
        (s.v_range, "V range", "dot"),
    ):
        if speed is not None and np.isfinite(speed):
            fig.add_vline(
                x=3.6 * speed,
                line_dash=dash,
                annotation_text=f"{name} {3.6 * speed:.0f} km/h",
            )
    fig.update_layout(
        title="Power versus cruise speed",
        xaxis_title="speed (km/h)",
        yaxis_title="power (W)",
        height=380,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def segment_rows(result: MissionResult) -> list[dict]:
    return [
        {
            "segment": s.kind,
            "duration (s)": round(s.duration_s, 1),
            "distance (m)": round(s.distance_m),
            "speed (km/h)": round(3.6 * s.speed_m_s, 1),
            "battery power (W)": round(s.battery_power_w, 1),
            "current (A)": round(s.battery_current_a, 2),
            "energy (Wh)": round(s.energy_j / 3600, 2),
            "feasible": s.feasible,
            "limiting": s.limiting,
        }
        for s in result.segments
    ]
