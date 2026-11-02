"""Battery power per flight segment (MIC-MIS-SEG, MVP variant)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from predimrc_wrapper.core import CompositeModel
from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.core.units import GRAVITY

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.model import AircraftModel
    from predimrc_wrapper.propulsion import PropulsionUnit

VERTICAL = ("hover", "vertical_climb", "vertical_descent")

MULTICOPTER_V_MIN = 1.0
"""Lowest cruise speed swept for a multicopter (m/s)."""

MULTICOPTER_V_MAX = 40.0
"""Highest cruise speed swept for a multicopter (m/s)."""


@dataclass
class SpeedSweep:
    """Cruise battery power versus speed."""

    v_m_s: np.ndarray
    battery_power_w: np.ndarray
    feasible: np.ndarray
    v_endurance: float
    v_range: float
    drag_n: np.ndarray | None = None
    """Total drag (N)."""
    shaft_power_w: np.ndarray | None = None
    """Total shaft power of the running propellers (W)."""

    @property
    def aero_power_w(self) -> np.ndarray | None:
        """Aerodynamic power D·V (W)."""
        return (
            None
            if self.drag_n is None
            else np.asarray(self.drag_n) * np.asarray(self.v_m_s)
        )


def parabolic_min(v: np.ndarray, f: np.ndarray, i: int) -> float:
    """Refine a grid minimum with the parabola through its neighbours."""
    if 0 < i < len(v) - 1 and np.all(np.isfinite(f[i - 1 : i + 2])):
        x0, x1, x2 = v[i - 1 : i + 2]
        y0, y1, y2 = f[i - 1 : i + 2]
        denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
        a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
        b = (x2**2 * (y0 - y1) + x1**2 * (y2 - y0) + x0**2 * (y1 - y2)) / denom
        if a > 0:
            return float(np.clip(-b / (2 * a), x0, x2))
    return float(v[i])


def _multicopter_zero_speed_is_hover(_: SegmentPower) -> bool:
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.aircraft import Project  # noqa: PLC0415

    seg = SegmentPower(AircraftModel(Project.template("multicopter")))
    hover = float(seg.evaluate({"kind": "hover", "v_m_s": 0.0})["battery_power_w"])
    cruise = float(seg.evaluate({"kind": "cruise", "v_m_s": 0.0})["battery_power_w"])
    return abs(cruise - hover) <= 1e-9 * hover


def _worst(ys: list[dict]) -> dict:
    """Element-wise worst margins over several units."""
    return {
        k: np.minimum.reduce([np.asarray(y[k], dtype=float) for y in ys])
        for k in ("current_margin", "power_margin", "voltage_margin")
    }


class SegmentPower(CompositeModel):
    """Battery power of a segment.

    Hover / vertical: T_i = f_i·k_dl·m·g (f_i: hover split of the lift rotors);
    P_b = Σ UNIT_i(T_i, 0) + P_av. Transition: κ_tr·P_hover. Wing-borne cruise: T = D(V)
    shared by disc area among the cruise and tilt motors, lift-only rotors stopped.
    Multicopter cruise: tan α = D/(m·g), T_i = f_i·√((mg)² + D²), Glauert induced velocity
    v_i = v_h² / √((V·cos α)² + (V·sin α + v_i)²), P_i = T_i·(V·sin α + v_i)/FM_i.

    Args:
        aircraft: The aircraft model.
        **values: The parameters.
    """

    mic_id = "MIC-MIS-SEG"
    inputs = ports(
        Port(
            "kind",
            "—",
            "—",
            "hover, vertical_climb, vertical_descent, transition, cruise, loiter",
        ),
        Port("v_m_s", "V", "m/s", "airspeed (cruise, loiter)", (0, None)),
    )
    outputs = ports(
        Port("battery_power_w", "P_b", "W", "total battery power", (0, None)),
        Port("battery_current_a", "I", "A", "battery current", (0, None)),
        Port(
            "chemical_power_w",
            "P_c",
            "W",
            "power drawn from the cells (MIC-PROP-BAT)",
            (0, None),
        ),
        Port(
            "shaft_power_w",
            "P_s",
            "W",
            "total shaft power of the running propellers",
            (0, None),
        ),
        Port(
            "margins",
            "—",
            "—",
            "motor current, motor power, voltage, battery C-rate margins (worst motor)",
        ),
        Port("feasible", "—", "—", "all limits respected"),
        Port("limiting", "—", "—", "first violated limit, if any"),
    )
    parameters = params(
        Param(
            "transition_factor",
            "κ_tr",
            "—",
            "transition power / hover power",
            default=1.0,
            bounds=(0, None),
            source="conservative assumption",
        ),
        Param(
            "avionics_power_w",
            "P_av",
            "W",
            "avionics and payload power",
            default=5.0,
            bounds=(0, None),
            source="project",
        ),
        Param(
            "download_factor",
            "k_dl",
            "—",
            "hover thrust / weight (1.05 quadplane, 1.0 multicopter when None)",
            default=None,
            source="quadplane practice",
        ),
    )
    expected_forms = [
        Invariant("multicopter at V = 0 ≡ hover", _multicopter_zero_speed_is_hover)
    ]

    def __init__(self, aircraft: AircraftModel | None = None, **values: Any) -> None:
        if aircraft is not None:
            mission = aircraft.project.mission
            values = {
                "transition_factor": mission.transition_factor,
                "avionics_power_w": mission.avionics_power_w,
                "download_factor": aircraft.download_factor,
                **values,
            }
        super().__init__({}, **values)
        self.aircraft = aircraft

    # --- helpers -------------------------------------------------------------

    def _loads_power(self, loads: list[tuple[PropulsionUnit, np.ndarray]], v) -> dict:
        """Evaluate the running units sharing the battery; voltage under load updated once."""
        ac = self.aircraft
        battery = ac.battery
        v0 = battery.open_circuit_voltage

        def run(u_bat):
            ys = [
                unit.evaluate({
                    "thrust_n": t,
                    "v_axial_m_s": v,
                    "rho": ac.rho,
                    "battery_voltage_v": u_bat,
                })
                for unit, t in loads
            ]
            return ys, sum(y["battery_power_w"] for y in ys) + self.p.avionics_power_w

        ys, total = run(v0)
        bat = battery.evaluate({"power_w": total})
        ys, total = run(np.where(np.isfinite(bat["voltage_v"]), bat["voltage_v"], v0))
        shaft = sum(np.asarray(y.get("shaft_power_w", np.nan), dtype=float) for y in ys)
        return {
            "unit": _worst(ys),
            "total": total,
            "battery": battery.evaluate({"power_w": total}),
            "shaft": shaft,
        }

    def _hover(self) -> dict:
        ac = self.aircraft
        k = (
            self.p.download_factor
            if self.p.download_factor is not None
            else ac.download_factor
        )
        return self._loads_power(ac.hover_loads(k * ac.total_mass_kg * GRAVITY), 0.0)

    def _multicopter_cruise(self, v) -> dict:
        ac = self.aircraft
        v = np.asarray(v, dtype=float)
        weight = ac.total_mass_kg * GRAVITY * (self.p.download_factor or 1.0)
        drag = np.asarray(ac.drag(v)["drag_n"], dtype=float)
        alpha = np.arctan2(drag, weight)
        battery = ac.battery
        v0 = battery.open_circuit_voltage
        motors, shaft_total = [], 0.0
        for unit, thrust_r in ac.hover_loads(np.hypot(weight, drag)):
            prop = unit.propeller
            v_h = np.sqrt(thrust_r / (2.0 * ac.rho * prop.disc_area_m2))
            v_i = v_h.copy()
            for _ in range(100):
                new = v_h**2 / np.sqrt(
                    (v * np.cos(alpha)) ** 2 + (v * np.sin(alpha) + v_i) ** 2
                )
                if np.all(np.abs(new - v_i) < 1e-10 * v_h):
                    v_i = new
                    break
                v_i = 0.5 * (v_i + new)
            shaft = thrust_r * (v * np.sin(alpha) + v_i) / prop.p.figure_of_merit
            n = prop.evaluate({"thrust_n": thrust_r, "v_m_s": 0.0, "rho": ac.rho})[
                "n_rev_s"
            ]
            omega = 2.0 * np.pi * n
            motors.append((
                unit,
                unit.motor.evaluate({"torque_nm": shaft / omega, "omega_rad_s": omega}),
            ))
            shaft_total = shaft_total + shaft
        total = (
            sum(mot["power_elec_w"] / unit.p.esc_efficiency for unit, mot in motors)
            + self.p.avionics_power_w
        )
        bat = battery.evaluate({"power_w": total})
        u_bat = np.where(np.isfinite(bat["voltage_v"]), bat["voltage_v"], v0)
        ys = [
            {
                "current_margin": mot["current_margin"],
                "power_margin": mot["power_margin"],
                "voltage_margin": 1.0 - mot["voltage_v"] / (unit.p.max_duty * u_bat),
            }
            for unit, mot in motors
        ]
        return {
            "unit": _worst(ys),
            "total": total,
            "battery": bat,
            "shaft": shaft_total,
        }

    # --- model ---------------------------------------------------------------

    def evaluate(self, x):
        kind = x["kind"]
        v = np.asarray(x.get("v_m_s", 0.0), dtype=float)
        ac = self.aircraft
        if kind in VERTICAL:
            out = self._hover()
        elif kind == "transition":
            out = self._hover()
            out["total"] = self.p.transition_factor * out["total"]
            out["battery"] = ac.battery.evaluate({"power_w": out["total"]})
        elif kind in ("cruise", "loiter"):
            if ac.wing_borne:
                drag = np.asarray(ac.drag(v)["drag_n"], dtype=float)
                out = self._loads_power(
                    ac.cruise_loads(np.where(np.isfinite(drag), drag, 0.0)), v
                )
                out["polar_ok"] = np.isfinite(drag)
            else:
                out = self._multicopter_cruise(v)
        else:
            msg = f"Unknown segment kind '{kind}'."
            raise ValueError(msg)
        y, bat = out["unit"], out["battery"]
        margins = {
            "motor_current": np.asarray(y["current_margin"], dtype=float),
            "motor_power": np.asarray(y["power_margin"], dtype=float),
            "voltage": np.asarray(y["voltage_margin"], dtype=float),
            "battery_c": np.asarray(bat["c_rate_margin"], dtype=float),
        }
        names = list(margins)
        stacked = np.stack(np.broadcast_arrays(*margins.values()))
        violated = ~(stacked >= 0.0)  # NaN counts as violated
        polar_ok = np.asarray(out.get("polar_ok", True))
        battery_ok = np.asarray(bat["feasible"], dtype=bool)
        feasible = ~violated.any(axis=0) & polar_ok & battery_ok
        reason = np.where(
            ~polar_ok,
            "outside_polar",
            np.where(
                ~battery_ok,
                "battery_power",
                np.asarray(names)[np.argmax(violated, axis=0)],
            ),
        )
        return {
            "battery_power_w": out["total"],
            "battery_current_a": bat["current_a"],
            "chemical_power_w": bat["chemical_power_w"],
            "shaft_power_w": out["shaft"],
            "margins": margins,
            "feasible": feasible,
            "limiting": np.where(feasible, "", reason),
        }

    def lift_thrust_to_weight(self) -> float:
        """Largest lift thrust keeping the hover split / weight, at the nominal battery voltage."""
        return self.aircraft.lift_thrust_to_weight()

    def cruise_sweep(self) -> SpeedSweep:
        """Battery power versus cruise speed and the two optimal speeds.

        Sweep V ∈ [k_s·V_min; V_max] by ΔV (``mission.stall_margin``, ``mission.speed_step``):
        V_e = argmin P_b, V_r = argmin P_b/V over the feasible speeds, parabolic refinement.
        """
        ac = self.aircraft
        mission = ac.project.mission
        if ac.wing_borne:
            lo = mission.stall_margin * ac.drag(1.0)["v_min_m_s"]
            polar = ac.aero.polar(ac.total_mass_kg)
            hi = float(polar.v_m_s[-1] * np.sqrt(polar.rho / ac.rho))
        else:
            lo, hi = MULTICOPTER_V_MIN, MULTICOPTER_V_MAX
        v = np.arange(lo, hi + 1e-9, mission.speed_step)
        y = self.evaluate({"kind": "cruise", "v_m_s": v})
        p = np.asarray(y["battery_power_w"], dtype=float)
        ok = np.asarray(y["feasible"], dtype=bool) & np.isfinite(p)
        extra = {
            "drag_n": np.asarray(ac.drag(v)["drag_n"], dtype=float),
            "shaft_power_w": np.broadcast_to(
                np.asarray(y["shaft_power_w"], dtype=float), v.shape
            ).copy(),
        }
        if not ok.any():
            return SpeedSweep(v, p, ok, float("nan"), float("nan"), **extra)
        masked = np.where(ok, p, np.inf)
        per_m = np.where(ok, p / v, np.inf)
        i_e, i_r = int(np.argmin(masked)), int(np.argmin(per_m))
        return SpeedSweep(
            v,
            p,
            ok,
            parabolic_min(v, masked, i_e),
            parabolic_min(v, per_m, i_r),
            **extra,
        )
