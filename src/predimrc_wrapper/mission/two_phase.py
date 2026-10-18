"""Two-phase flight time: hover, then cruise at a target speed until the reserve (MIC-MIS-TWO).

The designer's process (INC2-007):

1. Hover: thrust of each lift motor from the mass and the balance of moments about the CG;
   electric power at that thrust from the thrust–power surrogate (MIC-PROP-SUR); power
   chain (MIC-PROP-CHAIN) to the battery; power and thrust margins.
2. Cruise at V₁, V₂: aerodynamic power from PredimRC at the imposed speeds plus the drag
   sources (wing-borne, `aircraft/cruise.py`); thrust shared by the cruise and tilt motors
   by disc area; blade-element propeller (MIC-PROP-BEM) and motor constants for the motor
   power; power chain. Multicopter: forward-flight model of the MVP (MIC-MIS-SEG).
3. E_avail = (1 − r)·E_nom (80 % of the nominal energy by default);
   t_c = (E_avail − P_h·t_h) / P_c; flight time t_h + t_c; range V·t_c. Powers are the
   powers drawn from the cells (chemical power, battery losses included).
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
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
from predimrc_wrapper.core.units import INCH

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.model import AircraftModel
    from predimrc_wrapper.aircraft.project import MotorSlot
    from predimrc_wrapper.propulsion.chain import ChainResult

DEFAULT_PITCH_RATIO = 0.4
"""Pitch / diameter assumed when a propeller has no pitch (physics mean only, flagged)."""


@dataclass
class MotorHover:
    """Hover operating point of one lift motor."""

    index: int
    unit: str
    thrust_n: float
    fraction: float
    power_w: float
    """Electric power at the data measurement point (W)."""
    power_sd_w: float
    motor_input_w: float
    motor_current_a: float
    rpm: float
    power_margin: float
    current_margin: float
    thrust_margin: float
    """1 − T / T_max of the tested pair (NaN without data)."""
    trusted: bool
    reason: str
    source: str
    """``tested_pair``, ``untested_pair`` or ``physics_only``."""
    pair: str
    measured_at: str
    motor_id: str = ""
    propeller_id: str | None = None
    diameter_in: float = float("nan")
    pitch_in: float = float("nan")
    voltage_v: float = float("nan")
    """Bus voltage at which the surrogate was evaluated (V)."""


@dataclass
class HoverResult:
    """Hover phase."""

    thrust_total_n: float
    front_rear_ratio: float
    """Σ thrust of the motors ahead of the CG / Σ behind (NaN when undefined)."""
    cg_x_mm: float
    motors: list[MotorHover]
    chain: ChainResult
    battery_power_w: float
    """Power drawn from the cells (W)."""
    battery_power_sd_w: float


@dataclass
class MotorCruise:
    """Cruise operating point of one cruise / tilt motor."""

    index: int
    unit: str
    thrust_n: float
    rpm: float
    shaft_power_w: float
    prop_efficiency: float
    motor_input_w: float
    motor_current_a: float
    power_margin: float
    current_margin: float
    model: str


@dataclass
class CruiseResult:
    """Cruise at one target speed."""

    index: int
    v_m_s: float
    aero_power_w: float
    drag_n: float
    motors: list[MotorCruise]
    chain: ChainResult | None
    battery_power_w: float
    """Power drawn from the cells (W)."""
    source: str
    time_s: float = float("nan")
    time_sd_s: float = float("nan")
    flight_time_s: float = float("nan")
    range_m: float = float("nan")
    shaft_power_w: float = float("nan")
    """Σ rotor shaft power, multicopter forward-flight model only (W)."""
    terminal_power_w: float = float("nan")
    """Power at the battery terminals, multicopter forward-flight model only (W)."""


@dataclass
class TwoPhaseResult:
    """Flight time of the designer's process, per target speed."""

    hover_time_s: float
    energy_nominal_j: float
    energy_available_j: float
    reserve_fraction: float
    hover: HoverResult
    cruise: list[CruiseResult]
    margins: dict[str, float]
    feasible: bool
    limiting: str
    warnings: list[str] = field(default_factory=list)
    iso_check: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    curve: Any = None
    """``CruiseCurve`` of a wing-borne aircraft (aerodynamic power versus speed)."""
    aero_results: Any = None
    """PredimRC ``AeroResults`` at the target speeds (geometry results, imposed-speed blocks)."""

    @property
    def hover_energy_j(self) -> float:
        return self.hover.battery_power_w * self.hover_time_s

    def hand_check(self, k: int) -> str:
        """The flight-time formula with the numbers of target speed k (1 or 2)."""
        c = self.cruise[k - 1]
        return (
            f"t = t_h + (E_avail − P_h·t_h) / P_c = {self.hover_time_s:.0f} s + "
            f"({self.energy_available_j / 3600:.2f} Wh − {self.hover.battery_power_w:.1f} W × "
            f"{self.hover_time_s:.0f} s) / {c.battery_power_w:.1f} W = {c.flight_time_s:.0f} s "
            f"({c.flight_time_s / 60:.1f} min); E_avail = (1 − {self.reserve_fraction:g}) × "
            f"{self.energy_nominal_j / 3600:.2f} Wh"
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("iso_check", "curve", "aero_results"):
            data.pop(key, None)
        return data


def _motor_current(power_w: float, rpm: float, kv: float, r_m: float) -> float:
    """Motor current from its input power and speed: R·I² + (ω/Kv)·I − P = 0."""
    emf = rpm / kv
    if r_m <= 0:
        return power_w / emf
    return (-emf + np.sqrt(emf**2 + 4.0 * r_m * power_w)) / (2.0 * r_m)


def _pair(
    aircraft: AircraftModel, motor: MotorSlot
) -> tuple[str, str | None, float, float, bool]:
    """(motor id, propeller id or None, diameter in, pitch in, pitch known) of a motor."""
    from predimrc_wrapper.data import default_propellers  # noqa: PLC0415

    spec = aircraft.project.propulsion_units[motor.unit]
    pitch_known = spec.prop_pitch_in is not None
    pitch = (
        spec.prop_pitch_in
        if pitch_known
        else DEFAULT_PITCH_RATIO * spec.prop_diameter_in
    )
    prop_id = spec.propeller_id
    if prop_id is None and pitch_known:
        db = default_propellers()
        same = [
            p
            for p in db.records.values()
            if abs(p.diameter_in - spec.prop_diameter_in) < 1e-9
            and abs(p.pitch_in - pitch) < 1e-9
        ]
        prop_id = same[0].id if same else None
    return spec.motor_id, prop_id, spec.prop_diameter_in, pitch, pitch_known


class TwoPhaseEvaluation(CompositeModel):
    """Two-phase flight time (see the module docstring)."""

    mic_id = "MIC-MIS-TWO"
    inputs = ports(
        Port("hover_time_s", "t_h", "s", "hover time", (0, None)),
        Port(
            "target_speeds_m_s",
            "V_k",
            "m/s",
            "cruise target speeds (None: minimum power, maximum L/D)",
        ),
    )
    outputs = ports(
        Port(
            "result",
            "—",
            "—",
            "TwoPhaseResult: hover, cruise per target speed, flight times, margins",
        ),
    )
    parameters = params(
        Param(
            "reserve_fraction",
            "r",
            "—",
            "energy reserve, fraction of the nominal energy",
            default=0.20,
            bounds=(0, 0.5),
            source="designer, 2026-10-14",
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
            "min_thrust_to_weight",
            "T/W_min",
            "—",
            "minimum lift thrust-to-weight",
            default=1.5,
            bounds=(1, None),
            source="control authority practice",
        ),
    )
    expected_forms: list = []  # set after the class

    def __init__(self, aircraft: AircraftModel | None = None, **values: Any) -> None:
        if aircraft is not None:
            m = aircraft.project.mission
            values = {
                "reserve_fraction": m.reserve_fraction,
                "avionics_power_w": m.avionics_power_w,
                "min_thrust_to_weight": m.min_thrust_to_weight,
                **values,
            }
        super().__init__({}, **values)
        self.aircraft = aircraft

    # --- hover -----------------------------------------------------------------

    def hover(self) -> HoverResult:
        from predimrc_wrapper.data import default_tests  # noqa: PLC0415
        from predimrc_wrapper.propulsion.chain import PowerChain  # noqa: PLC0415
        from predimrc_wrapper.propulsion.surrogate import ThrustPowerSurrogate  # noqa: PLC0415

        ac = self.aircraft
        weight = ac.download_factor * ac.total_mass_kg * GRAVITY
        tests = default_tests()
        u_bus = ac.battery.open_circuit_voltage
        chain = None
        for _ in range(2):  # surrogate at the bus voltage under load, updated once
            motors = []
            for (i, slot), f in zip(
                ((ac.project.motors.index(m), m) for m in ac.lift_motors),
                ac.hover_fractions,
                strict=False,
            ):
                motor_id, prop_id, d_in, p_in, pitch_known = _pair(ac, slot)
                model = ThrustPowerSurrogate(
                    motor_id=motor_id,
                    propeller_id=prop_id or f"{d_in:g}x{p_in:g}",
                    diameter_in=d_in,
                    pitch_in=p_in,
                )
                thrust = f * weight
                p = model.predict(thrust, u_bus, ac.rho)
                pair_tests = tests.tests(motor_id, prop_id) if prop_id else []
                measured_at = pair_tests[0].measured_at if pair_tests else "motor_input"
                record = ac.db.motor(motor_id)
                power = float(p.power_w[0])
                eta = ac.project.propulsion_units[slot.unit].esc_efficiency
                motor_in = power * eta if measured_at == "esc_input" else power
                current = _motor_current(
                    motor_in, float(p.rpm[0]), record.kv, record.r_m
                )
                t_max = max((t.max_thrust_n for t in pair_tests), default=float("nan"))
                reason = str(p.reason[0]) + (
                    "" if pitch_known else "; propeller pitch not given"
                )
                motors.append(
                    MotorHover(
                        i,
                        slot.unit,
                        thrust,
                        float(f),
                        power,
                        float(
                            p.power_sd[0]
                            if hasattr(p, "power_sd")
                            else p.power_w[0] * p.sd_rel[0]
                        ),
                        motor_in,
                        current,
                        float(p.rpm[0]),
                        1.0 - motor_in / record.p_max,
                        1.0 - current / record.i_max,
                        1.0 - thrust / t_max if np.isfinite(t_max) else float("nan"),
                        bool(p.trusted[0]) and pitch_known,
                        reason.strip("; "),
                        p.source,
                        f"{motor_id} + {prop_id or f'{d_in:g}x{p_in:g} (not in the database)'}",
                        measured_at,
                        motor_id,
                        prop_id,
                        d_in,
                        p_in,
                        u_bus,
                    )
                )
            chain = PowerChain.from_project(
                ac.project, ac.battery, self._branch_currents(motors)
            ).evaluate({
                "motor_power_w": self._branch_values(motors, "power_w"),
                "motor_current_a": self._branch_values(motors, "motor_current_a"),
                "esc_input": self._branch_values(
                    motors, "measured_at", lambda v: v == "esc_input", False
                ),
                "avionics_power_w": self.p.avionics_power_w,
            })["result"]
            u_bus = chain.bus_voltage_v
        ratio = chain.chemical_power_w / max(
            chain.motor_power_w + self.p.avionics_power_w, 1e-9
        )
        sd = sum(m.power_sd_w for m in motors) * ratio  # fully correlated errors
        cg_x = (
            ac.project.cg_x_mm
            if ac.project.cg_x_mm is not None
            else float(
                sum(m.thrust_n * ac.project.motors[m.index].x_mm for m in motors)
                / sum(m.thrust_n for m in motors)
            )
        )
        front = sum(
            m.thrust_n for m in motors if ac.project.motors[m.index].x_mm < cg_x - 1e-6
        )
        rear = sum(
            m.thrust_n for m in motors if ac.project.motors[m.index].x_mm > cg_x + 1e-6
        )
        return HoverResult(
            weight,
            front / rear if rear > 0 and front > 0 else float("nan"),
            cg_x,
            motors,
            chain,
            chain.chemical_power_w,
            sd,
        )

    def _branch_values(
        self, motors: list, attr: str, convert=float, default: Any = 0.0
    ) -> list:
        """Per motor of the project (the chain has one branch per motor), stopped motors at 0."""
        values = [default] * len(self.aircraft.project.motors)
        for m in motors:
            values[m.index] = convert(getattr(m, attr))
        return values

    def _branch_currents(self, motors: list) -> list[float]:
        values = self._branch_values(motors, "motor_current_a")
        return [v if v > 0 else 10.0 for v in values]

    # --- cruise ----------------------------------------------------------------

    def _cruise_motor(self, slot_index: int, thrust: float, v: float) -> MotorCruise:
        from predimrc_wrapper.propulsion.propeller import BladeElementPropeller  # noqa: PLC0415

        ac = self.aircraft
        slot = ac.project.motors[slot_index]
        spec = ac.project.propulsion_units[slot.unit]
        record = ac.db.motor(spec.motor_id)
        motor = ac.units[slot.unit].motor
        if spec.prop_pitch_in is not None:
            bem = BladeElementPropeller(
                diameter_m=spec.prop_diameter_in * INCH,
                pitch_m=spec.prop_pitch_in * INCH,
            )
            n = float(bem.n_for_thrust(thrust, v, ac.rho, n_max=1500.0))
            shaft = float(
                bem.evaluate({"n_rev_s": n, "v_m_s": v, "rho": ac.rho})["shaft_power_w"]
            )
            model = "blade-element propeller (MIC-PROP-BEM)"
        else:
            n = float(
                np.sqrt(
                    thrust
                    / (spec.static_ct * ac.rho * (spec.prop_diameter_in * INCH) ** 4)
                )
            )
            shaft = thrust * v / spec.cruise_efficiency
            model = f"constant propeller efficiency {spec.cruise_efficiency:g} (no pitch given)"
        omega = 2.0 * np.pi * n
        y = motor.evaluate({"torque_nm": shaft / omega, "omega_rad_s": omega})
        p_in, i_m = float(y["power_elec_w"]), float(y["current_a"])
        return MotorCruise(
            slot_index,
            slot.unit,
            thrust,
            60.0 * n,
            shaft,
            float(thrust * v / shaft) if shaft > 0 else 0.0,
            p_in,
            i_m,
            1.0 - p_in / record.p_max,
            1.0 - i_m / record.i_max,
            model,
        )

    def cruise(
        self, speeds_m_s: tuple[float, float] | None
    ) -> tuple[list[CruiseResult], Any]:
        from predimrc_wrapper.propulsion.chain import PowerChain  # noqa: PLC0415

        ac = self.aircraft
        if not ac.wing_borne:
            from predimrc_wrapper.mission.powers import SegmentPower  # noqa: PLC0415
            from predimrc_wrapper.mission.solver import MissionSolver  # noqa: PLC0415

            if speeds_m_s is None:
                sweep = MissionSolver(ac).cruise_sweep()
                speeds_m_s = (sweep.v_endurance, sweep.v_range)
                if not all(np.isfinite(speeds_m_s)):
                    # No speed within every limit: take the minima of the unconstrained curve; the
                    # violated limits appear in the margins.
                    v, p = np.asarray(sweep.v_m_s), np.asarray(sweep.battery_power_w)
                    ok = np.isfinite(p)
                    speeds_m_s = (
                        float(v[ok][np.argmin(p[ok])]),
                        float(v[ok][np.argmin(p[ok] / v[ok])]),
                    )
            seg = SegmentPower(ac)
            out = []
            for k, v in enumerate(speeds_m_s, start=1):
                y = seg.evaluate({"kind": "cruise", "v_m_s": v})
                drag = float(np.asarray(ac.drag(v)["drag_n"]))
                out.append(
                    CruiseResult(
                        k,
                        v,
                        drag * v,
                        drag,
                        [],
                        None,
                        float(y["chemical_power_w"]),
                        "multicopter forward-flight model of the MVP (MIC-MIS-SEG)",
                        shaft_power_w=float(y["shaft_power_w"]),
                        terminal_power_w=float(y["battery_power_w"]),
                    )
                )
            return out, None
        from predimrc_wrapper.aircraft.cruise import target_points  # noqa: PLC0415

        curve, points, iso = target_points(ac, speeds_m_s)
        self._curve = curve
        self._aero = ac.aero.results(
            ac.total_mass_kg,
            (round(3.6 * points[0].v_m_s, 2), round(3.6 * points[1].v_m_s, 2)),
        )
        areas = np.array([ac.disc_area_m2(m) for m in ac.cruise_motors])
        out = []
        for point in points:
            motors = [
                self._cruise_motor(
                    ac.project.motors.index(m),
                    point.drag_n * a / areas.sum(),
                    point.v_m_s,
                )
                for m, a in zip(ac.cruise_motors, areas, strict=False)
            ]
            powers = [0.0] * len(ac.project.motors)
            currents = [0.0] * len(ac.project.motors)
            for m in motors:
                powers[m.index], currents[m.index] = m.motor_input_w, m.motor_current_a
            chain = PowerChain.from_project(
                ac.project, ac.battery, [c if c > 0 else 10.0 for c in currents]
            ).evaluate({
                "motor_power_w": powers,
                "motor_current_a": currents,
                "avionics_power_w": self.p.avionics_power_w,
            })["result"]
            out.append(
                CruiseResult(
                    point.index,
                    point.v_m_s,
                    point.aero_power_w,
                    point.drag_n,
                    motors,
                    chain,
                    chain.chemical_power_w,
                    "PredimRC imposed speed + drag sources",
                )
            )
        return out, iso

    # --- flight time -----------------------------------------------------------------

    def solve(
        self, hover_time_s: float, speeds_m_s: tuple[float, float] | None = None
    ) -> TwoPhaseResult:
        ac = self.aircraft
        hover = self.hover()
        self._curve = self._aero = None
        cruise, iso = self.cruise(speeds_m_s)
        e_nom = ac.battery.energy_wh() * 3600.0
        e_avail = (1.0 - self.p.reserve_fraction) * e_nom
        e_left = e_avail - hover.battery_power_w * hover_time_s
        warnings, feasible, limiting = [], True, ""
        for c in cruise:
            c.time_s = (
                max(0.0, e_left / c.battery_power_w)
                if c.battery_power_w > 0
                else float("nan")
            )
            sd_rel = (
                np.hypot(hover_time_s * hover.battery_power_sd_w / e_left, 0.0)
                if e_left > 0
                else float("nan")
            )
            c.time_sd_s = c.time_s * sd_rel
            c.flight_time_s = hover_time_s + c.time_s
            c.range_m = c.v_m_s * c.time_s
        if e_left <= 0:
            feasible, limiting = False, "hover_too_long"
        margins: dict[str, float] = {
            "motor_power": min(
                [m.power_margin for m in hover.motors]
                + [m.power_margin for c in cruise for m in c.motors]
            ),
            "motor_current": min(
                [m.current_margin for m in hover.motors]
                + [m.current_margin for c in cruise for m in c.motors]
            ),
            "hover_thrust": float(np.nanmin([m.thrust_margin for m in hover.motors]))
            if any(np.isfinite(m.thrust_margin) for m in hover.motors)
            else float("nan"),
            "thrust_to_weight": ac.lift_thrust_to_weight() / self.p.min_thrust_to_weight
            - 1.0,
            "battery_c": 1.0
            - max(
                [hover.chain.battery_current_a]
                + [c.chain.battery_current_a for c in cruise if c.chain]
            )
            / ac.battery.max_current_a(),
            "mass": float(ac.mass["margin_mass"]),
        }
        margins = {k: float(v) for k, v in margins.items()}
        for name in (
            "motor_power",
            "motor_current",
            "battery_c",
            "thrust_to_weight",
            "hover_thrust",
            "mass",
        ):
            if feasible and np.isfinite(margins[name]) and margins[name] < 0:
                feasible, limiting = False, name
        if not hover.chain.feasible:
            feasible, limiting = False, limiting or "battery_power"
        untrusted = [
            f"motor {m.index + 1}: {m.reason}" for m in hover.motors if not m.trusted
        ]
        if untrusted:
            warnings.append("Untrusted hover power: " + "; ".join(untrusted))
        warnings += [
            f"Cruise V{c.index}: {m.model}"
            for c in cruise
            for m in c.motors
            if "constant" in m.model
        ]
        if iso is not None and iso.available and not iso.passed:
            warnings.append(
                f"Iso-model check with PredimRC failed: curve {iso.curve_max_rel_dev:.2e}, "
                f"imposed speeds {iso.imposed_max_rel_dev:.2e}"
            )
        elif iso is not None and not iso.available:
            warnings.append(
                "Iso-model check not available (the aero backend gives no PredimRC blocks)"
            )
        from predimrc_wrapper import __version__  # noqa: PLC0415
        from predimrc_wrapper.data import default_tests  # noqa: PLC0415

        return TwoPhaseResult(
            hover_time_s,
            e_nom,
            e_avail,
            self.p.reserve_fraction,
            hover,
            cruise,
            margins,
            feasible,
            limiting,
            warnings,
            iso,
            {
                "tool_version": __version__,
                "project": ac.project.name,
                "test_data_hash": default_tests().hash(),
                "mass_total_kg": ac.total_mass_kg,
                "mass_breakdown": dict(ac.mass["breakdown"]),
            },
            self._curve,
            self._aero,
        )

    def evaluate(self, x):
        speeds = x.get("target_speeds_m_s")
        return {
            "result": self.solve(
                float(x["hover_time_s"]), None if speeds is None else tuple(speeds)
            )
        }


def _formula(_: TwoPhaseEvaluation) -> bool:
    """Flight time equals the formula from the displayed powers."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.aircraft import Project  # noqa: PLC0415

    r = TwoPhaseEvaluation(AircraftModel(Project.template("tricopter"))).solve(
        90.0, (8.0, 12.0)
    )
    c = r.cruise[0]
    expected = (
        90.0
        + (r.energy_available_j - r.hover.battery_power_w * 90.0) / c.battery_power_w
    )
    return bool(np.isclose(c.flight_time_s, expected, rtol=1e-12))


TwoPhaseEvaluation.expected_forms = [
    Invariant("flight time = t_h + (E_avail − P_h·t_h) / P_c", _formula)
]
