"""Tables and KPI tiles of the two-phase flight time (no Streamlit import)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.ui import units

if TYPE_CHECKING:
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult


def fmt(value: float, spec: str = ".1f", unit: str = "") -> str:
    """A number, or "—" when not finite."""
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:{spec}}{(' ' + unit) if unit else ''}"


def kpi_rows(r: TwoPhaseResult) -> list[list[tuple[str, str, bool]]]:
    """Rows of (label, text, negative) tiles: one row per target speed, then the margins."""
    rows = [
        [
            (
                f"V{c.index}",
                units.speed_text(c.v_m_s, 1),
                False,
            ),
            (
                "Flight time",
                fmt(c.flight_time_s / 60, ".1f", "min") + f" ± {c.time_sd_s / 60:.1f}",
                False,
            ),
            ("Range", fmt(c.range_m / 1000, ".1f", "km"), False),
            (
                "Hover power (battery)",
                fmt(r.hover.battery_power_w, ".0f", "W")
                + f" ± {r.hover.battery_power_sd_w:.0f}",
                False,
            ),
            ("Cruise power (battery)", fmt(c.battery_power_w, ".0f", "W"), False),
            ("Aerodynamic power", fmt(c.aero_power_w, ".1f", "W"), False),
        ]
        for c in r.cruise
    ]
    rows.append([
        (
            margin_label(k),
            fmt(v, "+.2f"),
            bool(np.isfinite(v) and v < 0),
        )
        for k, v in r.margins.items()
    ])
    return rows


MARGIN_LABELS = {
    "hover_thrust": "Margin hover thrust within test data",
    "thrust_to_weight": "Margin thrust-to-weight (control)",
    "transition": "Margin transition (tilting motors)",
    "yaw_tilt": "Margin yaw tilt (worst case)",
}


def margin_label(key: str) -> str:
    return MARGIN_LABELS.get(key, f"Margin {key.replace('_', ' ')}")


def phase_rows(r: TwoPhaseResult) -> list[dict]:
    """Vertical phases then the cruise to the reserve at V1: duration, power, energy."""
    rows = [
        {
            "phase": p.name,
            "duration (s)": round(p.duration_s, 1),
            "battery power (W)": round(p.battery_power_w, 1),
            "energy (Wh)": round(p.energy_j / 3600.0, 2),
        }
        for p in r.phases
    ]
    rows.extend(
        {
            "phase": f"cruise at V{c.index} (until the reserve)",
            "duration (s)": round(c.time_s, 1),
            "battery power (W)": round(c.battery_power_w, 1),
            "energy (Wh)": round(c.battery_power_w * c.time_s / 3600.0, 2),
        }
        for c in r.cruise
    )
    return rows


def discharge_figure(r: TwoPhaseResult):
    """Pack voltage (open-circuit and under load) and state of charge along the flight."""
    import plotly.graph_objects as go  # noqa: PLC0415

    d = r.discharge
    t = np.asarray(d.time_s) / 60.0
    fig = go.Figure([
        go.Scatter(x=t, y=d.voltage_v, name="under load", mode="lines"),
        go.Scatter(x=t, y=d.ocv_v, name="open circuit", mode="lines"),
        go.Scatter(
            x=t,
            y=100.0 * np.asarray(d.soc),
            name="state of charge (%)",
            mode="lines",
            yaxis="y2",
            line={"dash": "dot"},
        ),
    ])
    for name, end in zip(d.names, d.segment_end, strict=True):
        fig.add_vline(x=t[end], line={"width": 1, "dash": "dot"}, annotation_text=name)
    fig.update_layout(
        title="Battery discharge (cruise at V1)",
        xaxis_title="time (min)",
        yaxis_title="pack voltage (V)",
        yaxis2={
            "title": "state of charge (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
        },
        legend={"orientation": "h"},
        height=360,
    )
    return fig


def hover_rows(r: TwoPhaseResult, point=None) -> list[dict]:
    """One row per lift motor of an operating point (hover by default, or climb, transition)."""
    point = point or r.hover
    return [
        {
            "motor": m.index + 1,
            "unit": m.unit,
            "pair (data)": m.pair,
            "thrust": units.thrust_text(m.thrust_n),
            "share (%)": round(100 * m.fraction, 1),
            "power (W)": round(m.power_w, 1),
            "± σ (W)": round(m.power_sd_w, 1),
            "measured at": m.measured_at,
            "motor current (A)": round(m.motor_current_a, 2),
            "rpm": round(m.rpm),
            "power margin": round(m.power_margin, 2),
            "current margin": round(m.current_margin, 2),
            "thrust margin": None
            if not np.isfinite(m.thrust_margin)
            else round(m.thrust_margin, 2),
            "thrust with T/W min": units.thrust_text(m.safety_thrust_n),
            "margin with T/W min (motor limits)": round(m.safety_margin, 2),
            "margin with T/W min (test data)": None
            if not np.isfinite(m.safety_test_margin)
            else round(m.safety_test_margin, 2),
            "motor current with T/W min (A)": round(m.safety_current_a, 2),
            "current margin with T/W min": round(m.safety_current_margin, 2),
            "source": m.source,
            "trusted": m.trusted,
            "why not": m.reason,
        }
        for m in point.motors
    ]


def hover_tilt_rows(
    r: TwoPhaseResult,
    tilting: set[int],
    tilt_deg: float,
    yaw_tilt: str = "none",
    yaw_tilt_deg: float = 0.0,
) -> list[dict]:
    """Hover rows of every lift motor, the transition rows of the tilting ones, then the
    yaw worst-case rows of the yaw-tilting motors, each at its worst case (largest thrust).

    Args:
        tilting: Indices in ``project.motors`` of the tilting motors.
        tilt_deg: Transition tilt angle, shown in the phase column.
        yaw_tilt: Yaw-tilting motors (``mission.yaw_tilt``): none, front or rear.
        yaw_tilt_deg: Maximum yaw tilt (°).
    """
    rows = [{"phase": "hover", **row} for row in hover_rows(r)]
    if r.landing is not None:
        rows.extend(
            {"phase": f"landing, battery at {r.reserve_fraction:.0%}", **row}
            for row in hover_rows(r, r.landing)
        )
    if r.transition is not None:
        rows.extend(
            {"phase": f"transition, tilted {tilt_deg:g}°", **row}
            for m, row in zip(
                r.transition.motors, hover_rows(r, r.transition), strict=True
            )
            if m.index in tilting
        )
    if not r.yaw_cases:
        return rows
    transition = f"transition {tilt_deg:g}°, " if r.transition is not None else ""
    # Each motor at its worst case: the case of its largest thrust
    worst: dict[int, tuple] = {}
    for case in r.yaw_cases:
        for m, row in zip(case.point.motors, hover_rows(r, case.point), strict=True):
            if m.index not in case.vertical:
                continue
            if m.index not in worst or m.thrust_n > worst[m.index][0].thrust_n:
                worst[m.index] = (m, row, case)
    for index, (_, row, case) in sorted(worst.items()):
        prefix = transition if index in tilting else ""
        if yaw_tilt == "front":
            own = case.tilt_deg[index]
            others = sorted({f"{a:g}°" for a in case.tilt_deg.values() if a != own})
            label = f"{prefix}differential yaw ±{yaw_tilt_deg:g}°, tilted {own:g}°" + (
                f", other side {', '.join(others)}" if others else ""
            )
        else:
            label = (
                f"{prefix}yaw {yaw_tilt_deg:g}° lateral, k = {case.vertical[index]:.3f}"
            )
        rows.append({"phase": f"worst case yaw ({label})", **row})
    return rows


def cruise_rows(r: TwoPhaseResult) -> list[dict]:
    rows = []
    for c in r.cruise:
        if not c.motors:
            rows.append({
                "V": c.index,
                "speed (km/h)": round(units.kmh(c.v_m_s), 1),
                "aero power (W)": round(c.aero_power_w, 1),
                "battery power (W)": round(c.battery_power_w, 1),
                "model": c.source,
            })
        rows.extend(
            {
                "V": c.index,
                "speed (km/h)": round(units.kmh(c.v_m_s), 1),
                "motor": m.index + 1,
                "thrust": units.thrust_text(m.thrust_n),
                "rpm": round(m.rpm),
                "prop efficiency": round(m.prop_efficiency, 3),
                "motor input (W)": round(m.motor_input_w, 1),
                "motor current (A)": round(m.motor_current_a, 2),
                "power margin": round(m.power_margin, 2),
                "aero power (W)": round(c.aero_power_w, 1),
                "battery power (W)": round(c.battery_power_w, 1),
                "model": m.model,
            }
            for m in c.motors
        )
    return rows


def chain_rows(r: TwoPhaseResult) -> list[dict]:
    """One row per segment, one column of losses per operating point."""
    points = [("hover", r.hover.chain)] + [
        (f"V{c.index}", c.chain) for c in r.cruise if c.chain is not None
    ]
    names = [s.name for s in points[0][1].segments]
    rows = []
    for i, name in enumerate(names):
        row = {"segment": name, "model": points[0][1].segments[i].model}
        for label, chain in points:
            seg = chain.segments[i]
            row[f"{label} loss (W)"] = (
                round(seg.loss_w, 2) if seg.power_in_w > 0 else 0.0
            )
        row["in the data"] = points[0][1].segments[i].in_data
        rows.append(row)
    return [row for row in rows if any(v for k, v in row.items() if k.endswith("(W)"))]
