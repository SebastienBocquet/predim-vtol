"""Propulsion views: reference data tables, thrust/power curves and propeller pitch study.

Pure functions on an ``AircraftModel`` (no Streamlit), tested without the GUI.

Choosing the pitch of a fixed-pitch propeller: its thrust vanishes near the pitch speed
V_p = n·P and its efficiency peaks around J = V/(nD) ≈ 0.7–0.8·P/D, i.e. at a flight
speed of about 70–80 % of the pitch speed at the cruise rpm. A low pitch turns fast and
works at low J: good static thrust (hover, take-off) but low efficiency and over-speed
at cruise speed. A high pitch suits the cruise speed but stalls in static conditions and
asks more torque (current) at low speed. The motor matters as much: its Kv sets the rpm
reachable at the battery voltage, and its efficiency drops at low rpm and high torque.
For a cruise motor, take the pitch maximising the propeller × motor efficiency T·V/P_el
at the best-range speed within the motor limits; for a lift motor, the pitch needing
the least electric power at the hover thrust; a tilting motor needs a compromise
(check both).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.core.units import INCH
from predimrc_wrapper.propulsion import BladeElementPropeller

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel
    from predimrc_wrapper.data import MotorDatabase
    from predimrc_wrapper.propulsion import PropulsionUnit
    from predimrc_wrapper.sizing import PowerRange

COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b")


# --- reference data ------------------------------------------------------------


def motor_rows(db: MotorDatabase, ranges: list[PowerRange] | None = None) -> list[dict]:
    """Motor database as table rows; with ranges, the unit types each motor fits."""
    rows = []
    for m in sorted(db.records.values(), key=lambda r: r.p_max):
        row = {"id": m.id, "role (data sheet)": m.role, "Kv (rpm/V)": m.kv, "Rm (mΩ)": round(1000 * m.r_m, 1),
               "I0 (A)": m.i0, "Imax (A)": m.i_max, "Pmax (W)": m.p_max, "mass (g)": round(1000 * m.mass_kg, 1),
               "source": m.source}
        if ranges is not None:
            row["fits unit types"] = ", ".join(r.unit for r in ranges if m.id in r.candidates)
        rows.append(row)
    return rows


def range_rows(ranges: list[PowerRange]) -> list[dict]:
    return [{
        "unit type": r.unit, "roles": ", ".join(r.roles), "motors": r.n_motors,
        "needed at min mass (W)": round(r.need_low_w), "needed at max mass (W)": round(r.need_high_w),
        "accepted up to (W)": round(r.accepted_high_w), "current motor": r.current_motor,
        "its Pmax (W)": r.current_p_max_w, "in range": r.current_in_range,
        "candidates": ", ".join(r.candidates) or "none in the database",
    } for r in ranges]


def propeller_rows(aircraft: AircraftModel) -> list[dict]:
    """Propeller data of each unit type; static C_T, C_P of the blade-element model when the pitch is known."""
    rows = []
    for name, spec in aircraft.project.propulsion_units.items():
        row = {"unit type": name, "motor": spec.motor_id, "diameter (in)": spec.prop_diameter_in,
               "pitch (in)": spec.prop_pitch_in, "mass (g)": spec.prop_mass_g, "FM (hover)": spec.figure_of_merit,
               "CT0 (speed estimate)": spec.static_ct, "η cruise": spec.cruise_efficiency}
        if spec.prop_pitch_in:
            bem = _bem(spec.prop_diameter_in, spec.prop_pitch_in)
            y = bem.evaluate({"n_rev_s": 100.0, "v_m_s": 0.0, "rho": aircraft.rho})
            ct, cp = float(y["ct"]), float(y["cp"])
            row.update({"BEM CT0": round(ct, 3), "BEM CP0": round(cp, 3),
                        "BEM FM": round(ct**1.5 / np.sqrt(2.0) / cp, 2)})
        rows.append(row)
    return rows


# --- thrust / power curves -------------------------------------------------------


def unit_curves(unit: PropulsionUnit, rho: float, battery_voltage_v: float, v_m_s: float = 0.0,
                n: int = 40) -> dict[str, np.ndarray]:
    """Static (or axial-flow) operating points from zero to the maximum feasible thrust."""
    t_max = unit.max_thrust(rho, battery_voltage_v, v_m_s)
    thrust = np.linspace(0.02 * t_max, t_max, n)
    y = unit.evaluate({"thrust_n": thrust, "v_axial_m_s": v_m_s, "rho": rho, "battery_voltage_v": battery_voltage_v})
    return {"thrust_n": thrust, "battery_power_w": y["battery_power_w"], "current_a": y["motor_current_a"],
            "rpm": y["rpm"], "g_per_w": thrust / GRAVITY * 1000.0 / y["battery_power_w"]}


def thrust_figure(aircraft: AircraftModel) -> go.Figure:
    """Per unit type: thrust vs battery power, current vs thrust (I_max dashed), with hover points."""
    v0 = aircraft.battery.open_circuit_voltage
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Thrust vs battery power", "Motor current vs thrust",
                                                        "Efficiency (g/W) vs thrust"))
    hover = {}
    weight = aircraft.download_factor * aircraft.total_mass_kg * GRAVITY
    for m, f in zip(aircraft.lift_motors, aircraft.hover_fractions):
        hover.setdefault(m.unit, []).append(f * weight)
    for i, (name, unit) in enumerate(aircraft.units.items()):
        color = COLORS[i % len(COLORS)]
        c = unit_curves(unit, aircraft.rho, v0)
        grams = c["thrust_n"] / GRAVITY * 1000.0
        fig.add_trace(go.Scatter(x=c["battery_power_w"], y=grams, name=name, legendgroup=name, line={"color": color}),
                      1, 1)
        fig.add_trace(go.Scatter(x=grams, y=c["current_a"], name=name, legendgroup=name, showlegend=False,
                                 line={"color": color}), 1, 2)
        fig.add_hline(y=unit.motor.p.i_max, line={"color": color, "dash": "dash"}, row=1, col=2)
        fig.add_trace(go.Scatter(x=grams, y=c["g_per_w"], name=name, legendgroup=name, showlegend=False,
                                 line={"color": color}), 1, 3)
        for t in sorted(set(np.round(hover.get(name, []), 6))):
            y = unit.evaluate({"thrust_n": t, "v_axial_m_s": 0.0, "rho": aircraft.rho, "battery_voltage_v": v0})
            fig.add_trace(go.Scatter(x=[float(y["battery_power_w"])], y=[t / GRAVITY * 1000.0], mode="markers",
                                     name=f"{name} hover", legendgroup=name, marker={"color": color, "size": 10,
                                                                                      "symbol": "diamond"}), 1, 1)
    fig.update_xaxes(title_text="battery power per motor (W)", row=1, col=1)
    fig.update_yaxes(title_text="thrust (g)", row=1, col=1)
    fig.update_xaxes(title_text="thrust (g)", row=1, col=2)
    fig.update_yaxes(title_text="current (A)", row=1, col=2)
    fig.update_xaxes(title_text="thrust (g)", row=1, col=3)
    fig.update_yaxes(title_text="g/W", row=1, col=3)
    fig.update_layout(height=400, margin={"l": 10, "r": 10, "t": 40, "b": 10},
                      title=f"Static operating range at {v0:.1f} V (nominal), limits: Imax, Pmax, voltage")
    return fig


# --- pitch study -----------------------------------------------------------------


def _bem(diameter_in: float, pitch_in: float) -> BladeElementPropeller:
    return BladeElementPropeller(diameter_m=diameter_in * INCH, pitch_m=pitch_in * INCH)


def default_pitches(diameter_in: float) -> list[float]:
    """Pitches from P/D = 0.3 to 1.0, rounded to 0.5 in."""
    return sorted({round(2 * diameter_in * r) / 2 for r in np.linspace(0.3, 1.0, 8)})


def pitch_study(unit: PropulsionUnit, diameter_in: float, pitches_in: list[float], v_m_s: np.ndarray,
                thrust_n: np.ndarray, rho: float, battery_voltage_v: float) -> dict[str, np.ndarray]:
    """Fixed-pitch propellers on the unit's motor delivering a thrust T(V).

    Returns arrays of shape (n_pitch, n_speed): ``efficiency`` (T·V / P_el, propeller ×
    motor), ``prop_efficiency``, ``rpm``, ``current_a``, ``power_elec_w`` and ``feasible``
    (motor current, power and voltage within limits), plus ``best_pitch_in`` per speed
    (highest feasible efficiency; lowest electric power at V = 0).
    """
    v = np.asarray(v_m_s, dtype=float)
    t = np.broadcast_to(np.asarray(thrust_n, dtype=float), v.shape)
    motor = unit.motor
    n_max = max_rpm(unit, battery_voltage_v) / 60.0 * 1.2
    out: dict[str, list] = {k: [] for k in ("efficiency", "prop_efficiency", "rpm", "current_a", "power_elec_w",
                                            "feasible")}
    for p in pitches_in:
        bem = _bem(diameter_in, p)
        n = bem.n_for_thrust(t, v, rho, n_max=n_max)
        ok = np.isfinite(n)
        n_safe = np.where(ok, n, 1.0)
        y = bem.evaluate({"n_rev_s": n_safe, "v_m_s": v, "rho": rho})
        omega = 2.0 * np.pi * n_safe
        mot = motor.evaluate({"torque_nm": np.maximum(y["shaft_power_w"], 0.0) / omega, "omega_rad_s": omega})
        within = (ok & (mot["current_margin"] >= 0) & (mot["power_margin"] >= 0)
                  & (mot["voltage_v"] <= unit.p.max_duty * battery_voltage_v))
        out["efficiency"].append(np.where(ok, t * v / mot["power_elec_w"], np.nan))
        out["prop_efficiency"].append(np.where(ok, y["efficiency"], np.nan))
        out["rpm"].append(np.where(ok, 60.0 * n, np.nan))
        out["current_a"].append(np.where(ok, mot["current_a"], np.nan))
        out["power_elec_w"].append(np.where(ok, mot["power_elec_w"], np.nan))
        out["feasible"].append(within)
    res = {k: np.array(val) for k, val in out.items()}
    score = np.where(v > 0, res["efficiency"], -res["power_elec_w"])
    masked = np.where(res["feasible"], score, -np.inf)
    res["best_pitch_in"] = np.where(res["feasible"].any(axis=0),
                                    np.asarray(pitches_in, dtype=float)[np.argmax(masked, axis=0)], np.nan)
    return res


def max_rpm(unit: PropulsionUnit, battery_voltage_v: float) -> float:
    """No-load speed bound Kv·U·d_max (rpm)."""
    return unit.motor.p.kv * battery_voltage_v * unit.p.max_duty


def pitch_figure(name: str, diameter_in: float, pitches_in: list[float], v_m_s: np.ndarray,
                 study: dict[str, np.ndarray], current_pitch_in: float | None = None,
                 v_mark: float | None = None) -> go.Figure:
    """Propeller × motor efficiency vs speed per pitch (dotted beyond the motor limits), best pitch vs speed."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Propeller × motor efficiency T·V / P_el",
                                                        "Best pitch within the motor limits"))
    for i, p in enumerate(pitches_in):
        ok = study["feasible"][i]
        eta = study["efficiency"][i]
        width = 4 if current_pitch_in is not None and abs(p - current_pitch_in) < 1e-9 else 2
        color = COLORS[i % len(COLORS)] if i < len(COLORS) else None
        fig.add_trace(go.Scatter(x=v_m_s, y=np.where(ok, eta, np.nan), name=f"{diameter_in:g}x{p:g}",
                                 legendgroup=str(p), line={"width": width, "color": color}), 1, 1)
        fig.add_trace(go.Scatter(x=v_m_s, y=np.where(~ok, eta, np.nan), name=f"{diameter_in:g}x{p:g} over limits",
                                 legendgroup=str(p), showlegend=False, line={"dash": "dot", "color": color}), 1, 1)
    fig.add_trace(go.Scatter(x=v_m_s, y=study["best_pitch_in"], name="best pitch", line={"color": "black"}), 1, 2)
    if v_mark is not None and np.isfinite(v_mark):
        for col in (1, 2):
            fig.add_vline(x=v_mark, line_dash="dash", row=1, col=col)
    fig.update_xaxes(title_text="speed (m/s)")
    fig.update_yaxes(title_text="η propeller × motor", row=1, col=1)
    fig.update_yaxes(title_text="pitch (in)", row=1, col=2)
    fig.update_layout(height=380, margin={"l": 10, "r": 10, "t": 40, "b": 10}, title=f"Pitch study — {name}")
    return fig


def hover_pitch_rows(unit: PropulsionUnit, diameter_in: float, pitches_in: list[float], thrust_n: float, rho: float,
                     battery_voltage_v: float) -> list[dict]:
    """Static operating point of each pitch at the hover thrust: rpm, shaft and electric power, FM, current."""
    rows = []
    limit = max_rpm(unit, battery_voltage_v)
    for p in pitches_in:
        bem = _bem(diameter_in, p)
        n = float(bem.n_for_thrust(thrust_n, 0.0, rho, n_max=limit / 60.0 * 1.5))
        if not np.isfinite(n):
            rows.append({"pitch (in)": p, "rpm": None, "shaft power (W)": None, "FM": None, "motor current (A)": None,
                         "electric power (W)": None, "within motor limits": False})
            continue
        y = bem.evaluate({"n_rev_s": n, "v_m_s": 0.0, "rho": rho})
        power = float(y["shaft_power_w"])
        mot = unit.motor.evaluate({"torque_nm": power / (2 * np.pi * n), "omega_rad_s": 2 * np.pi * n})
        ideal = thrust_n**1.5 / np.sqrt(2.0 * rho * np.pi * (diameter_in * INCH) ** 2 / 4.0)
        within = (float(mot["current_margin"]) >= 0 and float(mot["power_margin"]) >= 0
                  and float(mot["voltage_v"]) <= unit.p.max_duty * battery_voltage_v)
        rows.append({"pitch (in)": p, "rpm": round(60 * n), "shaft power (W)": round(power, 1),
                     "FM": round(float(ideal / power), 3), "motor current (A)": round(float(mot["current_a"]), 2),
                     "electric power (W)": round(float(mot["power_elec_w"]), 1), "within motor limits": within})
    return rows
