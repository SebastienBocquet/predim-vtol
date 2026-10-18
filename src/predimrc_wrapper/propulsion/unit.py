"""Propulsion unit: ESC (constant efficiency) + motor + propeller (MIC-PROP-UNIT)."""

from __future__ import annotations

import numpy as np

from predimrc_wrapper.core import CompositeModel
from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.propulsion.motor import MotorModel
from predimrc_wrapper.propulsion.propeller import MomentumPropeller

LIMITS = ("motor_current", "motor_power", "voltage")
"""Limits checked, in the order used to report the first violated one."""


def _example_unit() -> PropulsionUnit:
    return PropulsionUnit(
        MotorModel(kv=330.0, r_m=0.085, i0=1.1, i_max=25.0, p_max=750.0, mass_kg=0.171),
        MomentumPropeller(diameter_m=0.381, mass_kg=0.025),
    )


def _energy_chain(_: PropulsionUnit) -> bool:
    unit = _example_unit()
    for v in (0.0, 15.0):
        y = unit.evaluate({
            "thrust_n": 6.0,
            "v_axial_m_s": v,
            "rho": 1.225,
            "battery_voltage_v": 22.2,
        })
        if (
            not float(y["battery_power_w"])
            >= float(y["power_elec_w"])
            >= float(y["shaft_power_w"])
            >= 6.0 * v
        ):
            return False
    return True


def _undersized(_: PropulsionUnit) -> bool:
    unit = PropulsionUnit(
        MotorModel(kv=330.0, r_m=0.085, i0=1.1, i_max=5.0, p_max=750.0, mass_kg=0.171),
        MomentumPropeller(diameter_m=0.381, mass_kg=0.025),
    )
    y = unit.evaluate({
        "thrust_n": 20.0,
        "v_axial_m_s": 0.0,
        "rho": 1.225,
        "battery_voltage_v": 22.2,
    })
    return not bool(y["feasible"]) and str(y["limiting"]) == "motor_current"


class PropulsionUnit(CompositeModel):
    """ESC → motor → propeller chain.

    (n, P) = propeller(T, V, ρ); ω = 2πn; Q = P/ω; (I, U, P_el) = motor(Q, ω);
    P_b = P_el / η_esc. Feasible if I ≤ I_max, P_el ≤ P_max and U ≤ d_max·U_bat.

    Args:
        motor: The motor model.
        propeller: The propeller model.
        **values: The parameters of the unit.
    """

    mic_id = "MIC-PROP-UNIT"
    inputs = ports(
        Port("thrust_n", "T", "N", "thrust of one unit", (0, None)),
        Port("v_axial_m_s", "V", "m/s", "axial inflow speed", (0, None)),
        Port("rho", "ρ", "kg/m³", "air density", (0, None)),
        Port(
            "battery_voltage_v", "U_bat", "V", "battery voltage under load", (0, None)
        ),
    )
    outputs = ports(
        Port("rpm", "N", "rpm", "rotation speed", (0, None)),
        Port("shaft_power_w", "P", "W", "shaft power", (0, None)),
        Port("power_elec_w", "P_el", "W", "motor electric power", (0, None)),
        Port(
            "battery_power_w",
            "P_b",
            "W",
            "power drawn from the battery by the unit",
            (0, None),
        ),
        Port("motor_current_a", "I_m", "A", "motor current", (0, None)),
        Port("current_margin", "—", "—", "1 − I_m / I_max"),
        Port("power_margin", "—", "—", "1 − P_el / P_max"),
        Port("voltage_margin", "—", "—", "1 − U_m / (d_max·U_bat)"),
        Port("feasible", "—", "—", "all limits respected"),
        Port(
            "limiting",
            "—",
            "—",
            "first violated limit: motor_current, motor_power, voltage",
        ),
    )
    parameters = params(
        Param(
            "esc_efficiency",
            "η_esc",
            "—",
            "ESC efficiency (constant in the MVP)",
            default=0.95,
            bounds=(0, 1),
            source="generic",
        ),
        Param(
            "esc_mass_kg",
            "m_esc",
            "kg",
            "ESC mass",
            default=0.03,
            bounds=(0, None),
            source="project",
        ),
        Param(
            "max_duty",
            "d_max",
            "—",
            "maximum duty cycle",
            default=0.95,
            bounds=(0, 1),
            source="generic",
        ),
    )
    expected_forms = [
        Invariant("P_b ≥ P_el ≥ P ≥ T·V", _energy_chain),
        Invariant("undersized motor ⇒ limiting = motor_current", _undersized),
    ]

    def __init__(
        self,
        motor: MotorModel | None = None,
        propeller: MomentumPropeller | None = None,
        **values,
    ) -> None:
        if motor is None or propeller is None:
            example = (
                _example_unit()
                if (motor is None and propeller is None and not values)
                else None
            )
            if example is None:
                msg = "PropulsionUnit needs a motor and a propeller."
                raise ValueError(msg)
            motor, propeller = example.motor, example.propeller
        super().__init__({"motor": motor, "propeller": propeller}, **values)

    @property
    def motor(self) -> MotorModel:
        return self.submodels["motor"]

    @property
    def propeller(self) -> MomentumPropeller:
        return self.submodels["propeller"]

    @property
    def mass_kg(self) -> float:
        """Motor + propeller + ESC mass (kg)."""
        return self.motor.p.mass_kg + self.propeller.p.mass_kg + self.p.esc_mass_kg

    def evaluate(self, x):
        prop = self.propeller.evaluate({
            "thrust_n": x["thrust_n"],
            "v_m_s": x.get("v_axial_m_s", 0.0),
            "rho": x["rho"],
        })
        omega = 2.0 * np.pi * prop["n_rev_s"]
        mot = self.motor.evaluate({
            "torque_nm": prop["torque_nm"],
            "omega_rad_s": omega,
        })
        battery_power = mot["power_elec_w"] / self.p.esc_efficiency
        u_bat = np.asarray(x["battery_voltage_v"], dtype=float)
        voltage_margin = 1.0 - mot["voltage_v"] / (self.p.max_duty * u_bat)
        margins = np.stack(
            np.broadcast_arrays(
                mot["current_margin"], mot["power_margin"], voltage_margin
            )
        )
        violated = margins < 0.0
        feasible = ~violated.any(axis=0)
        first = np.argmax(violated, axis=0)
        limiting = np.where(feasible, "", np.asarray(LIMITS)[first])
        return {
            "rpm": 60.0 * prop["n_rev_s"],
            "shaft_power_w": prop["shaft_power_w"],
            "power_elec_w": mot["power_elec_w"],
            "battery_power_w": battery_power,
            "motor_current_a": mot["current_a"],
            "current_margin": mot["current_margin"],
            "power_margin": mot["power_margin"],
            "voltage_margin": voltage_margin,
            "feasible": feasible,
            "limiting": limiting,
        }

    def max_thrust(
        self, rho: float, battery_voltage_v: float, v_axial_m_s: float = 0.0
    ) -> float:
        """Return the largest feasible thrust (N), by bisection."""

        def ok(t: float) -> bool:
            return bool(
                self.evaluate({
                    "thrust_n": t,
                    "v_axial_m_s": v_axial_m_s,
                    "rho": rho,
                    "battery_voltage_v": battery_voltage_v,
                })["feasible"]
            )

        low, high = 0.0, 1.0
        if not ok(1e-6):
            return 0.0
        while ok(high) and high < 1e5:
            low, high = high, 2.0 * high
        for _ in range(60):
            mid = 0.5 * (low + high)
            low, high = (mid, high) if ok(mid) else (low, mid)
        return low
