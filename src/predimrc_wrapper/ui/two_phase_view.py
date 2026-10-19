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
            "thrust margin": None
            if not np.isfinite(m.thrust_margin)
            else round(m.thrust_margin, 2),
            "source": m.source,
            "trusted": m.trusted,
            "why not": m.reason,
        }
        for m in point.motors
    ]


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
