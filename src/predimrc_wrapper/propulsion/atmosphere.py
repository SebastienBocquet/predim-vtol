"""ISA atmosphere, troposphere (MIC-ATM-ISA)."""

from __future__ import annotations

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports


def _decreasing(model: AtmosphereISA) -> bool:
    h = model.evaluate({
        "altitude_m": np.array([0.0, 1000.0, 3000.0]),
        "delta_isa_k": 0.0,
    })
    dt = model.evaluate({
        "altitude_m": 500.0,
        "delta_isa_k": np.array([-20.0, 0.0, 20.0]),
    })
    return bool(
        np.all(np.diff(h["density"]) < 0) and np.all(np.diff(dt["density"]) < 0)
    )


def _sea_level(model: AtmosphereISA) -> bool:
    rho0 = float(model.evaluate({"altitude_m": 0.0, "delta_isa_k": 0.0})["density"])
    rho1 = float(model.evaluate({"altitude_m": 1000.0, "delta_isa_k": 0.0})["density"])
    return abs(rho0 - 1.2250) <= 5e-4 and abs(rho1 - 1.1117) <= 1e-3


class AtmosphereISA(Model):
    """Air density from pressure altitude and temperature offset.

    T = T₀ − L·h + ΔT; p = p₀·(1 − 2.25577·10⁻⁵·h)^5.25588; ρ = p / (R·T).
    """

    mic_id = "MIC-ATM-ISA"
    inputs = ports(
        Port("altitude_m", "h", "m", "pressure altitude", (0, 11000)),
        Port("delta_isa_k", "ΔT", "K", "temperature offset to ISA", (-40, 40)),
    )
    outputs = ports(Port("density", "ρ", "kg/m³", "air density", (0, None)))
    parameters = params(
        Param(
            "t0",
            "T₀",
            "K",
            "sea-level temperature",
            default=288.15,
            bounds=(0, None),
            source="ISO 2533",
        ),
        Param(
            "p0",
            "p₀",
            "Pa",
            "sea-level pressure",
            default=101325.0,
            bounds=(0, None),
            source="ISO 2533",
        ),
        Param(
            "lapse_rate",
            "L",
            "K/m",
            "temperature lapse rate",
            default=0.0065,
            bounds=(0, None),
            source="ISO 2533",
        ),
        Param(
            "r_air",
            "R",
            "J/(kg·K)",
            "gas constant of air",
            default=287.053,
            bounds=(0, None),
            source="ISO 2533",
        ),
    )
    expected_forms = [
        Invariant(
            "density decreases with altitude and temperature offset", _decreasing
        ),
        Invariant("sea-level and 1000 m ISA densities", _sea_level),
    ]

    def evaluate(self, x):
        h = np.asarray(x.get("altitude_m", 0.0), dtype=float)
        dt = np.asarray(x.get("delta_isa_k", 0.0), dtype=float)
        if np.any(h > 11000.0) or np.any(h < 0.0):
            msg = "ISA troposphere only: altitude must be within [0, 11000] m."
            raise ValueError(msg)
        t = self.p.t0 - self.p.lapse_rate * h + dt
        p = self.p.p0 * (1.0 - 2.25577e-5 * h) ** 5.25588
        return {"density": p / (self.p.r_air * t)}


def density(altitude_m: float = 0.0, delta_isa_k: float = 0.0) -> float:
    """Return the ISA air density (kg/m³)."""
    return float(
        AtmosphereISA().evaluate({
            "altitude_m": altitude_m,
            "delta_isa_k": delta_isa_k,
        })["density"]
    )
