"""Brushless DC motor, Kv–R_m–I₀ model (MIC-PROP-MOT)."""

from __future__ import annotations

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import default_database

_EXAMPLE = {
    "kv": 330.0,
    "r_m": 0.085,
    "i0": 1.1,
    "i_max": 25.0,
    "p_max": 750.0,
    "mass_kg": 0.171,
}


class MotorModel(Model):
    """Brushless motor.

    Kv_SI = Kv·π/30; I = Q·Kv_SI + I₀; U = ω/Kv_SI + R_m·I; P_el = U·I; η = Q·ω/P_el.
    """

    mic_id = "MIC-PROP-MOT"
    inputs = ports(
        Port("torque_nm", "Q", "N·m", "torque required by the propeller", (0, None)),
        Port("omega_rad_s", "ω", "rad/s", "rotation speed", (0, None)),
    )
    outputs = ports(
        Port("current_a", "I", "A", "motor current", (0, None)),
        Port("voltage_v", "U", "V", "equivalent DC motor voltage", (0, None)),
        Port("power_elec_w", "P_el", "W", "electric input power", (0, None)),
        Port("efficiency", "η_m", "—", "Q·ω / P_el", (0, 1)),
        Port("current_margin", "—", "—", "1 − I / I_max"),
        Port("power_margin", "—", "—", "1 − P_el / P_max"),
    )
    parameters = params(
        Param(
            "kv",
            "Kv",
            "rpm/V",
            "speed constant",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
        Param(
            "r_m",
            "R_m",
            "Ω",
            "phase-to-phase winding resistance",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
        Param(
            "i0",
            "I₀",
            "A",
            "no-load current",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
        Param(
            "i_max",
            "I_max",
            "A",
            "maximum current",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
        Param(
            "p_max",
            "P_max",
            "W",
            "maximum power",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
        Param(
            "mass_kg",
            "m_m",
            "kg",
            "motor mass with cables",
            origin="database",
            bounds=(0, None),
            source="manufacturer data sheet",
        ),
    )
    expected_forms = [
        Invariant(
            "Q = 0 ⇒ I = I₀",
            lambda m: np.isclose(
                float(
                    m.evaluate({"torque_nm": 0.0, "omega_rad_s": 500.0})["current_a"]
                ),
                m.p.i0,
            ),
            params=_EXAMPLE,
        ),
        Invariant(
            "efficiency below 1",
            lambda m: (
                float(
                    m.evaluate({"torque_nm": 0.3, "omega_rad_s": 500.0})["efficiency"]
                )
                < 1.0
            ),
            params=_EXAMPLE,
        ),
        ScalingLaw(
            "power_elec_w",
            "omega_rad_s",
            1.0,
            fixed={"torque_nm": 0.0},
            lower=100.0,
            upper=1000.0,
            tol=1e-2,
            params={**_EXAMPLE, "r_m": 0.0},
        ),
    ]

    @classmethod
    def from_database(
        cls, motor_id: str, db: MotorDatabase | None = None
    ) -> MotorModel:
        """Build the model of a database motor."""
        return cls(**(db or default_database()).motor(motor_id).model_parameters())

    def evaluate(self, x):
        q = np.asarray(x["torque_nm"], dtype=float)
        omega = np.asarray(x["omega_rad_s"], dtype=float)
        kv_si = self.p.kv * np.pi / 30.0
        current = q * kv_si + self.p.i0
        voltage = omega / kv_si + self.p.r_m * current
        power = voltage * current
        with np.errstate(divide="ignore", invalid="ignore"):
            efficiency = np.where(power > 0.0, q * omega / power, 0.0)
        return {
            "current_a": current,
            "voltage_v": voltage,
            "power_elec_w": power,
            "efficiency": efficiency,
            "current_margin": 1.0 - current / self.p.i_max,
            "power_margin": 1.0 - power / self.p.p_max,
        }
