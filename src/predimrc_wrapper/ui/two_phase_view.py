"""Tables and KPI tiles of the two-phase flight time (no Streamlit import)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

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
                fmt(c.v_m_s, ".1f", "m/s") + f" ({c.v_m_s * 3.6:.0f} km/h)",
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
            f"Margin {k.replace('_', ' ')}",
            fmt(v, "+.2f"),
            bool(np.isfinite(v) and v < 0),
        )
        for k, v in r.margins.items()
    ])
    return rows


def hover_rows(r: TwoPhaseResult) -> list[dict]:
    return [
        {
            "motor": m.index + 1,
            "unit": m.unit,
            "pair (data)": m.pair,
            "thrust (g)": round(m.thrust_n / 9.81 * 1000),
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
        for m in r.hover.motors
    ]


def cruise_rows(r: TwoPhaseResult) -> list[dict]:
    rows = []
    for c in r.cruise:
        if not c.motors:
            rows.append({
                "V": c.index,
                "speed (m/s)": round(c.v_m_s, 2),
                "aero power (W)": round(c.aero_power_w, 1),
                "battery power (W)": round(c.battery_power_w, 1),
                "model": c.source,
            })
        rows.extend(
            {
                "V": c.index,
                "speed (m/s)": round(c.v_m_s, 2),
                "motor": m.index + 1,
                "thrust (N)": round(m.thrust_n, 2),
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
