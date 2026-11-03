"""Two-phase flight time: hover, then cruise at a target speed until the reserve (MIC-MIS-TWO).

The designer's process (INC2-007):

1. Hover: thrust of each lift motor from the mass and the balance of moments about the CG;
   electric power at that thrust from the thrust–power surrogate (MIC-PROP-SUR); power
   chain (MIC-PROP-CHAIN) to the battery; power and thrust margins.
2. Cruise at V₁, V₂: aerodynamic power from PredimRC at the imposed speeds plus the drag
   sources (wing-borne, `aircraft/cruise.py`); thrust shared by the cruise and tilt motors
   by disc area; blade-element propeller (MIC-PROP-BEM) and motor constants for the motor
   power; power chain. Multicopter: forward-flight model of the MVP (MIC-MIS-SEG).
3. Vertical phases (INC3-006): climb to the transition altitude h at v_c, hover t_h,
   transition t_tr (winged aircraft), descent from h at v_d. Climb: each rotor at its hover
   thrust with the momentum-theory factor k_c = v_c/(2v_h) + √((v_c/(2v_h))² + 1),
   v_h = √(T/(2ρA)), on its power. Transition: the tilting motors at the tilt angle θ give
   T·sin θ vertically, so T_i = F_i / sin θ (F_i their hover share), no wing lift
   (start of the transition, conservative; default θ = 60°); a winged aircraft without tilting motors
   transitions at hover power. Descent at the landing hover power (conservative).
4. E_avail = (1 − r)·E_nom (80 % of the nominal energy by default);
   t_c = (E_avail − Σ P_k·t_k) / P_c over the vertical phases k; flight time Σ t_k + t_c;
   range V·t_c. Powers are the powers drawn from the cells (chemical power, battery losses
   included).
5. End of the flight (battery discharge): the cruise runs until the reserve, so the descent
   and the landing are at the state of charge s = r. The landing hover is evaluated at the
   open-circuit voltage and resistance of the pack at s (MIC-PROP-BAT); the other points at
   the nominal voltage. Every margin is the worst over the points, landing included; the
   landing fails below the cut-off voltage. The discharge profile along the flight (cruise at
   V₁) is integrated from the terminal powers (stateless, MIC-PROP-BAT).
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
    from predimrc_wrapper.propulsion.battery import DischargeProfile
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
    safety_thrust_n: float = float("nan")
    """Thrust with the safety factor: T/W_min · share · m·g (/ sin θ for a tilted motor) (N)."""
    max_thrust_n: float = float("nan")
    """Full-throttle thrust of the motor model at the open-circuit voltage of the point (N)."""
    test_max_thrust_n: float = float("nan")
    """Largest thrust of the tested pair (N), NaN without data."""
    safety_current_a: float = float("nan")
    """Motor current at the thrust with the safety factor (A)."""
    safety_current_margin: float = float("nan")
    """1 − I_safety / I_max of the motor."""

    @property
    def safety_margin(self) -> float:
        """T_full-throttle / T_safety − 1: power, current and voltage limits at T/W_min."""
        return self.max_thrust_n / self.safety_thrust_n - 1.0

    @property
    def safety_test_margin(self) -> float:
        """1 − T_safety / T_max of the tested pair (NaN without data)."""
        return 1.0 - self.safety_thrust_n / self.test_max_thrust_n


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
class PhaseResult:
    """One vertical phase of the flight."""

    name: str
    """climb, hover, transition or descent."""
    duration_s: float
    battery_power_w: float
    battery_power_sd_w: float = 0.0

    @property
    def energy_j(self) -> float:
        return self.battery_power_w * self.duration_s


@dataclass
class YawCase:
    """One yaw worst case: the yaw-tilting motors at full yaw tilt."""

    vertical: dict[int, float]
    """Vertical component k of a unit thrust of each yaw-tilting motor (index in
    ``project.motors``)."""
    tilt_deg: dict[int, float]
    """Tilt from the horizontal of each front yaw-tilting motor (θ ∓ δ; empty for the rear
    rotor, tilted laterally)."""
    point: HoverResult


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
    phases: list[PhaseResult] = field(default_factory=list)
    """Vertical phases: climb, hover, transition, descent (zero-duration ones left out)."""
    climb: HoverResult | None = None
    """Operating point of the climb (rotors at the climb power), when there is a climb."""
    transition: HoverResult | None = None
    """Operating point of the transition (tilting motors at the tilt angle)."""
    yaw_cases: list[YawCase] = field(default_factory=list)
    """Yaw worst cases, transition tilt included when there is one: front differential tilt
    (each side tilted forward in turn), or the rear rotor tilted laterally; empty without
    yaw tilt."""
    landing: HoverResult | None = None
    """Hover at the end of the flight, battery at the reserve state of charge (descent and
    landing; worst case of the margins)."""
    discharge: DischargeProfile | None = None
    """Battery state of charge and voltages along the flight, cruise at V1."""

    @property
    def hover_energy_j(self) -> float:
        return self.hover.battery_power_w * self.hover_time_s

    @property
    def vertical_time_s(self) -> float:
        return sum(p.duration_s for p in self.phases)

    @property
    def vertical_energy_j(self) -> float:
        return sum(p.energy_j for p in self.phases)

    def hand_check(self, k: int) -> str:
        """The flight-time formula with the numbers of target speed k (1 or 2)."""
        c = self.cruise[k - 1]
        terms = " + ".join(
            f"{p.battery_power_w:.1f} W × {p.duration_s:.0f} s ({p.name})"
            for p in self.phases
        )
        return (
            f"t = Σt_k + (E_avail − Σ P_k·t_k) / P_c = {self.vertical_time_s:.0f} s + "
            f"({self.energy_available_j / 3600:.2f} Wh − ({terms or '0'})) / "
            f"{c.battery_power_w:.1f} W = {c.flight_time_s:.0f} s "
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

    def hover(
        self,
        climb_speed_m_s: float = 0.0,
        tilt_deg: float | None = None,
        vertical: dict[int, float] | None = None,
        soc: float | None = None,
    ) -> HoverResult:
        """Operating point of the lift motors carrying the weight.

        A tilted motor keeps its hover share F_i of the vertical force (same weight and
        moment balances) and gives T_i = F_i / k_i, k_i the vertical component of a unit thrust.

        Args:
            climb_speed_m_s: Vertical climb speed (momentum-theory power factor per rotor).
            tilt_deg: Tilt angle of the tilting motors from the horizontal (transition):
                k = sin θ.
            vertical: Vertical component k_i of a unit thrust per motor index in
                ``project.motors`` (yaw worst case); it overrides ``tilt_deg``.
            soc: Battery state of charge (open-circuit voltage and resistance of the pack
                at that state); nominal voltage when None.
        """
        from predimrc_wrapper.data import default_tests  # noqa: PLC0415
        from predimrc_wrapper.propulsion.chain import PowerChain  # noqa: PLC0415
        from predimrc_wrapper.propulsion.surrogate import ThrustPowerSurrogate  # noqa: PLC0415

        ac = self.aircraft
        weight = ac.download_factor * ac.total_mass_kg * GRAVITY
        tests = default_tests()
        u_bus = u_open = ac.battery.ocv_v(soc)
        chain = None
        full_throttle: dict[str, float] = {}
        factors = [
            (vertical or {}).get(
                ac.project.motors.index(m),
                float(np.sin(np.radians(tilt_deg)))
                if tilt_deg is not None and m.role == "tilt"
                else 1.0,
            )
            for m in ac.lift_motors
        ]
        k_h = ac.project.mission.hover_power_factor  # calibration, 1 by default
        # What does not depend on the bus voltage, per lift motor; the motors of one
        # surrogate pair share a model, predicted once per pass on all their thrusts.
        lift = []
        models = {}
        for (i, slot), f, k in zip(
            ((ac.project.motors.index(m), m) for m in ac.lift_motors),
            ac.hover_fractions,
            factors,
            strict=False,
        ):
            motor_id, prop_id, d_in, p_in, pitch_known = _pair(ac, slot)
            key = (motor_id, prop_id or f"{d_in:g}x{p_in:g}", d_in, p_in)
            if key not in models:
                models[key] = ThrustPowerSurrogate(
                    motor_id=motor_id,
                    propeller_id=key[1],
                    diameter_in=d_in,
                    pitch_in=p_in,
                )
            thrust = f * weight / k
            k_c = 1.0
            if climb_speed_m_s > 0:
                v_h = np.sqrt(thrust / (2.0 * ac.rho * ac.disc_area_m2(slot)))
                ratio = climb_speed_m_s / (2.0 * v_h)
                k_c = float(ratio + np.sqrt(ratio**2 + 1.0))
            if slot.unit not in full_throttle:
                full_throttle[slot.unit] = ac.unit_of(slot).max_thrust(ac.rho, u_open)
            pair_tests = tests.tests(motor_id, prop_id) if prop_id else []
            lift.append({
                "i": i,
                "slot": slot,
                "f": f,
                "key": key,
                "prop_id": prop_id,
                "thrust": thrust,
                "safety": self.p.min_thrust_to_weight
                * f
                * ac.total_mass_kg
                * GRAVITY
                / k,
                "k_c": k_c,
                "pair_tests": pair_tests,
                "measured_at": pair_tests[0].measured_at
                if pair_tests
                else "motor_input",
                "pitch_known": pitch_known,
                "record": ac.db.motor(motor_id),
            })
        groups = {key: [m for m in lift if m["key"] == key] for key in models}
        for group in groups.values():
            for j, m in enumerate(group):
                m["j"], m["j_safety"] = j, len(group) + j
        for _ in range(2):  # surrogate at the bus voltage under load, updated once
            # Nominal thrusts then thrusts with the safety factor (static, no climb factor).
            predictions = {
                key: models[key].predict(
                    np.array(
                        [m["thrust"] for m in group] + [m["safety"] for m in group]
                    ),
                    u_bus,
                    ac.rho,
                )
                for key, group in groups.items()
            }
            motors = []
            for m in lift:
                p = predictions[m["key"]]
                j, j_s = m["j"], m["j_safety"]
                motor_id, prop_label, d_in, p_in = m["key"]
                prop_id = m["prop_id"]
                record, thrust, k_c = m["record"], m["thrust"], m["k_c"]
                power = k_h * k_c * float(p.power_w[j])
                eta = ac.project.esc_efficiency(m["slot"])
                esc_input = m["measured_at"] == "esc_input"
                motor_in = power * eta if esc_input else power
                current = _motor_current(
                    motor_in, float(p.rpm[j]), record.kv, record.r_m
                )
                safety_in = k_h * float(p.power_w[j_s]) * (eta if esc_input else 1.0)
                safety_current = _motor_current(
                    safety_in, float(p.rpm[j_s]), record.kv, record.r_m
                )
                t_max = max(
                    (t.max_thrust_n for t in m["pair_tests"]), default=float("nan")
                )
                reason = str(p.reason[j]) + (
                    "" if m["pitch_known"] else "; propeller pitch not given"
                )
                motors.append(
                    MotorHover(
                        m["i"],
                        m["slot"].unit,
                        thrust,
                        float(m["f"]),
                        power,
                        k_h
                        * k_c
                        * float(
                            p.power_sd[j]
                            if hasattr(p, "power_sd")
                            else p.power_w[j] * p.sd_rel[j]
                        ),
                        motor_in,
                        current,
                        float(p.rpm[j]),
                        1.0 - motor_in / record.p_max,
                        1.0 - current / record.i_max,
                        1.0 - thrust / t_max if np.isfinite(t_max) else float("nan"),
                        bool(p.trusted[j]) and m["pitch_known"],
                        reason.strip("; "),
                        p.source,
                        f"{motor_id} + {prop_id or f'{prop_label} (not in the database)'}",
                        m["measured_at"],
                        motor_id,
                        prop_id,
                        d_in,
                        p_in,
                        u_bus,
                        m["safety"],
                        full_throttle[m["slot"].unit],
                        t_max,
                        safety_current,
                        1.0 - safety_current / record.i_max,
                    )
                )
            chain = PowerChain.from_project(ac.project, ac.battery).evaluate({
                "motor_power_w": self._branch_values(motors, "power_w"),
                "motor_current_a": self._branch_values(motors, "motor_current_a"),
                "esc_input": self._branch_values(
                    motors, "measured_at", lambda v: v == "esc_input", False
                ),
                "avionics_power_w": self.p.avionics_power_w,
                "soc": soc,
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

            seg = SegmentPower(ac)
            if speeds_m_s is None:
                sweep = seg.cruise_sweep()
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
            chain = PowerChain.from_project(ac.project, ac.battery).evaluate({
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
                    "PredimRC imposed speed + drag sources"
                    if point.source == "block"
                    else "PredimRC polar (stall edge) + drag sources",
                )
            )
        return out, iso

    def yaw_cases(
        self, cg_x_mm: float, transition: bool
    ) -> list[tuple[dict[int, float], dict[int, float]]]:
        """Vertical components and tilts of the yaw-tilting motors in each worst case.

        θ: transition tilt from the horizontal on a tilting motor when there is a transition,
        else 90°; δ: maximum yaw tilt. Front motors, differential tilt about the same axis as
        the transition: one side at θ − δ (k = sin(θ − δ)), the other at θ + δ, then the
        reverse (two cases); a front motor on the centreline at θ − δ in both. Rear rotor
        (tricopter, lateral tilt about the boom, orthogonal to the transition tilt):
        k = sin θ · cos δ, one case. Empty without yaw tilt.

        Returns:
            (vertical components, tilts from the horizontal) per case, by motor index.
        """
        mission = self.aircraft.project.mission
        if mission.yaw_tilt == "none" or mission.yaw_tilt_max_deg <= 0:
            return []
        delta = mission.yaw_tilt_max_deg
        front = mission.yaw_tilt == "front"
        side = -1.0 if front else 1.0  # x aft-positive
        motors = {
            i: m
            for i, m in enumerate(self.aircraft.project.motors)
            if m.role in ("lift", "tilt") and side * (m.x_mm - cg_x_mm) > 1e-6
        }
        if not motors:
            return []
        theta = {
            i: mission.transition_tilt_deg if transition and m.role == "tilt" else 90.0
            for i, m in motors.items()
        }
        if not front:
            cos_delta = np.cos(np.radians(delta))
            return [
                (
                    {
                        i: float(np.sin(np.radians(t)) * cos_delta)
                        for i, t in theta.items()
                    },
                    {},
                )
            ]
        cases = []
        for forward in (1.0, -1.0):  # the side y > 0, then y < 0, tilted forward
            tilts = {
                i: theta[i] - delta if forward * m.y_mm >= -1e-6 else theta[i] + delta
                for i, m in motors.items()
            }
            cases.append((
                {i: float(np.sin(np.radians(a))) for i, a in tilts.items()},
                tilts,
            ))
        return cases

    # --- flight time -----------------------------------------------------------------

    def solve(
        self, hover_time_s: float, speeds_m_s: tuple[float, float] | None = None
    ) -> TwoPhaseResult:
        ac = self.aircraft
        mission = ac.project.mission
        hover = self.hover()
        h = mission.transition_altitude_m
        climb = (
            self.hover(climb_speed_m_s=mission.vertical_climb_speed_m_s)
            if h > 0
            else None
        )
        tilting = any(m.role == "tilt" for m in ac.project.motors)
        t_tr = mission.transition_time_s if ac.wing_borne else 0.0
        transition = (
            self.hover(tilt_deg=mission.transition_tilt_deg)
            if t_tr > 0 and tilting
            else None
        )
        yaw_cases = [
            YawCase(
                vertical,
                tilts,
                self.hover(
                    tilt_deg=mission.transition_tilt_deg
                    if transition is not None
                    else None,
                    vertical=vertical,
                ),
            )
            for vertical, tilts in self.yaw_cases(hover.cg_x_mm, transition is not None)
        ]
        # The cruise runs until the reserve: the landing is at the reserve state of charge.
        soc_land = self.p.reserve_fraction
        landing = self.hover(soc=soc_land)
        vertical_points = [
            (name, duration, point)
            for name, duration, point in (
                ("climb", h / mission.vertical_climb_speed_m_s, climb),
                ("hover", hover_time_s, hover),
                ("transition", t_tr, transition or hover),
                ("descent", h / mission.vertical_descent_speed_m_s, landing),
            )
            if duration > 0 and point is not None
        ]
        phases = [
            PhaseResult(
                name,
                duration,
                point.battery_power_w,
                point.battery_power_sd_w,
            )
            for name, duration, point in vertical_points
        ]
        self._curve = self._aero = None
        cruise, iso = self.cruise(speeds_m_s)
        e_nom = ac.battery.energy_wh() * 3600.0
        e_avail = (1.0 - self.p.reserve_fraction) * e_nom
        e_left = e_avail - sum(ph.energy_j for ph in phases)
        t_vertical = sum(ph.duration_s for ph in phases)
        e_vertical_sd = sum(ph.battery_power_sd_w * ph.duration_s for ph in phases)
        warnings, feasible, limiting = [], True, ""
        for c in cruise:
            c.time_s = (
                max(0.0, e_left / c.battery_power_w)
                if c.battery_power_w > 0
                else float("nan")
            )
            sd_rel = e_vertical_sd / e_left if e_left > 0 else float("nan")
            c.time_sd_s = c.time_s * sd_rel
            c.flight_time_s = t_vertical + c.time_s
            c.range_m = c.v_m_s * c.time_s
        if e_left <= 0:
            feasible, limiting = False, "hover_too_long"
        discharge = self._discharge(vertical_points, cruise[0])
        vertical = [p for p in (hover, climb, transition, landing) if p is not None]
        steady = [p for p in (hover, climb, landing) if p is not None]
        thrust_margins = [m.thrust_margin for p in vertical for m in p.motors]
        margins: dict[str, float] = {
            "motor_power": min(
                [m.power_margin for p in steady for m in p.motors]
                + [m.power_margin for c in cruise for m in c.motors]
            ),
            "motor_current": min(
                [m.current_margin for p in steady for m in p.motors]
                + [m.current_margin for c in cruise for m in c.motors]
            ),
            "transition": min(
                min(m.power_margin, m.current_margin) for m in transition.motors
            )
            if transition is not None
            else float("nan"),
            "yaw_tilt": min(
                min(m.power_margin, m.current_margin)
                for case in yaw_cases
                for m in case.point.motors
            )
            if yaw_cases
            else float("nan"),
            "hover_thrust": float(np.nanmin(thrust_margins))
            if any(np.isfinite(t) for t in thrust_margins)
            else float("nan"),
            "thrust_to_weight": min(
                ac.lift_thrust_to_weight(), ac.lift_thrust_to_weight(soc_land)
            )
            / self.p.min_thrust_to_weight
            - 1.0,
            "battery_c": 1.0
            - max(
                [p.chain.battery_current_a for p in vertical]
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
            "transition",
            "yaw_tilt",
            "hover_thrust",
            "mass",
        ):
            if feasible and np.isfinite(margins[name]) and margins[name] < 0:
                feasible, limiting = False, name
        if not all(p.chain.feasible for p in vertical):
            feasible, limiting = False, limiting or "battery_power"
        if not landing.chain.cutoff_ok:
            feasible, limiting = False, limiting or "battery_cutoff"
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
        if iso is not None:
            warnings += [f"Cruise {w}" for w in iso.warnings]
        if iso is not None and not iso.available:
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
                "hover_power_factor": mission.hover_power_factor,
                "mass_breakdown": dict(ac.mass["breakdown"]),
            },
            self._curve,
            self._aero,
            phases,
            climb,
            transition,
            yaw_cases,
            landing,
            discharge,
        )

    def _discharge(
        self,
        vertical_points: list[tuple[str, float, HoverResult]],
        cruise: CruiseResult,
    ) -> DischargeProfile:
        """Battery discharge along the flight with the cruise at the first target speed."""
        sequence = [(n, t, p.chain.battery_power_w) for n, t, p in vertical_points]
        p_cruise = (
            cruise.chain.battery_power_w
            if cruise.chain is not None
            else cruise.terminal_power_w
        )
        if np.isfinite(cruise.time_s) and cruise.time_s > 0:
            descent_last = bool(sequence) and sequence[-1][0] == "descent"
            at = len(sequence) - 1 if descent_last else len(sequence)
            sequence.insert(at, (f"cruise V{cruise.index}", cruise.time_s, p_cruise))
        return self.aircraft.battery.discharge(
            [t for _, t, _ in sequence],
            [p for _, _, p in sequence],
            [n for n, _, _ in sequence],
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
        r.vertical_time_s
        + (r.energy_available_j - r.vertical_energy_j) / c.battery_power_w
    )
    return bool(np.isclose(c.flight_time_s, expected, rtol=1e-12))


TwoPhaseEvaluation.expected_forms = [
    Invariant("flight time = Σt_k + (E_avail − Σ P_k·t_k) / P_c", _formula)
]
