"""Hover tab: data behind each hover power (REQ-PROP-012), surrogate validation (REQ-NFR-005)."""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go

from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.ui import units

if TYPE_CHECKING:
    from predimrc_wrapper.mission.two_phase import MotorHover
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult

COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b")


def pairs(r: TwoPhaseResult) -> dict[str, list[MotorHover]]:
    """Hover motors grouped by motor + propeller pair."""
    out: dict[str, list[MotorHover]] = {}
    for m in r.hover.motors:
        out.setdefault(m.pair, []).append(m)
    return out


def _model(m: MotorHover):
    from predimrc_wrapper.propulsion.surrogate import ThrustPowerSurrogate  # noqa: PLC0415

    return ThrustPowerSurrogate(
        motor_id=m.motor_id,
        propeller_id=m.propeller_id or f"{m.diameter_in:g}x{m.pitch_in:g}",
        diameter_in=m.diameter_in,
        pitch_in=m.pitch_in,
    )


def pair_figure(r: TwoPhaseResult, pair: str) -> go.Figure:
    """Electric power versus thrust: test points, surrogate mean and 95 % band, physics, operating points."""
    from predimrc_wrapper.data import default_tests  # noqa: PLC0415

    motors = pairs(r)[pair]
    m0 = motors[0]
    tests = (
        default_tests().tests(m0.motor_id, m0.propeller_id) if m0.propeller_id else []
    )
    t_max = max(
        [t.max_thrust_n for t in tests] + [1.4 * max(m.thrust_n for m in motors)]
    )
    thrust = np.linspace(0.15 * t_max, 1.1 * t_max, 50)
    p = _model(m0).predict(thrust, m0.voltage_v)
    low, high = p.interval95()
    g = thrust / GRAVITY * 1000.0
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=np.r_[g, g[::-1]],
            y=np.r_[high, low[::-1]],
            fill="toself",
            name="surrogate 95 %",
            line={"width": 0},
            fillcolor="rgba(31,119,180,0.2)",
        )
    )
    fig.add_trace(
        go.Scatter(x=g, y=p.power_w, name="surrogate mean", line={"color": COLORS[0]})
    )
    fig.add_trace(
        go.Scatter(
            x=g,
            y=p.physics_power_w,
            name="physics model",
            line={"color": "grey", "dash": "dot"},
        )
    )
    for i, t in enumerate(tests):
        fig.add_trace(
            go.Scatter(
                x=t.thrust_n,
                y=t.power_w,
                mode="markers",
                name=f"test data {t.voltage_v:g} V",
                marker={
                    "color": COLORS[(i + 1) % len(COLORS)],
                    "size": 8,
                    "symbol": "circle-open",
                },
                hovertext=[
                    f"throttle {100 * th:.0f} %, {units.thrust_text(tn)}"
                    for th, tn in zip(t.throttle, t.thrust_n, strict=False)
                ],
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[m.thrust_n for m in motors],
            y=[m.power_w for m in motors],
            error_y={"type": "data", "array": [1.96 * m.power_sd_w for m in motors]},
            mode="markers",
            name="hover operating point",
            marker={"color": "black", "size": 11, "symbol": "diamond"},
            hovertext=[
                f"motor {m.index + 1}: {units.thrust_text(m.thrust_n)}" for m in motors
            ],
        )
    )
    fig.update_layout(
        title=f"{pair} — power at {m0.voltage_v:.1f} V ({m0.measured_at.replace('_', ' ')})",
        xaxis_title="thrust (N)",
        yaxis_title="electric power (W)",
        height=400,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def points_near_rows(m: MotorHover, k: int = 6) -> list[dict]:
    """Test points of the pair closest to the operating thrust."""
    from predimrc_wrapper.data import default_tests  # noqa: PLC0415

    rows = []
    for t in (
        default_tests().tests(m.motor_id, m.propeller_id) if m.propeller_id else []
    ):
        rows.extend(
            {
                "test": t.id,
                "throttle (%)": round(100 * t.throttle[i]),
                "voltage (V)": t.voltage[i],
                "thrust": units.thrust_text(float(t.thrust_n[i])),
                "power (W)": t.power_w[i],
                "current (A)": t.current_a[i],
                "rpm": None if not np.isfinite(t.rpm[i]) else int(t.rpm[i]),
                "source": t.source,
                "_d": abs(t.thrust_n[i] - m.thrust_n),
            }
            for i in range(len(t.thrust_n))
        )
    rows.sort(key=operator.itemgetter("_d"))
    return [{k_: v for k_, v in r.items() if k_ != "_d"} for r in rows[:k]]


def validation_rows() -> tuple[dict, list[dict]]:
    """Global error guarantee and per-pair errors of the surrogate on the stored data."""
    from predimrc_wrapper.propulsion.surrogate import default_fit  # noqa: PLC0415

    r = default_fit().validate()
    summary = {
        "points": r.n_points,
        "pairs": r.n_pairs,
        "LOO mean error (%)": round(100 * r.loo_mean_rel_err, 2),
        "LOO max error (%)": round(100 * r.loo_max_rel_err, 2),
        "LOO coverage 95 % (%)": round(100 * r.loo_coverage_95, 1),
        "leave-one-pair-out mean error (%)": round(100 * r.lopo_mean_rel_err, 2),
        "leave-one-pair-out coverage 95 % (%)": round(100 * r.lopo_coverage_95, 1),
        "physics mean error (%)": round(100 * r.physics_mean_rel_err, 2),
        "guarantee met": r.passed(),
        "data hash": r.data_hash,
    }
    rows = [
        {
            "pair": g.replace("|", " + "),
            "points": v["n"],
            "LOO mean error (%)": round(100 * v["loo_mean_rel_err"], 2),
            "leave-one-pair-out mean error (%)": round(100 * v["lopo_mean_rel_err"], 2),
            "physics mean error (%)": round(100 * v["physics_mean_rel_err"], 2),
        }
        for g, v in r.per_pair.items()
    ]
    return summary, rows
