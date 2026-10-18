"""Mass budget (MIC-CFG-MASS, MVP variant)."""

from __future__ import annotations

from collections import defaultdict

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ports

_EXAMPLE_INPUT = {
    "mass_items": [("airframe", 0.9), ("payload", 0.15), ("avionics", 0.12)],
    "propulsion_items": [("lift propulsion", 0.15)] * 4 + [("cruise propulsion", 0.15)],
    "battery_mass_kg": 0.6, "max_takeoff_mass_kg": 3.0,
}


def _exact_sum(model: MassBudget) -> bool:
    y = model.evaluate(_EXAMPLE_INPUT)
    expected = 0.9 + 0.15 + 0.12 + 4 * 0.15 + 0.15 + 0.6
    return abs(y["total_kg"] - expected) < 1e-12 and abs(sum(y["breakdown"].values()) - expected) < 1e-12


class MassBudget(Model):
    """Total mass m = Σ m_i + Σ m_unit,j + m_b, one propulsion unit per motor (a tilting motor counts once).

    margin_mass = 1 − m / m_max when a maximum take-off mass is given.
    """

    mic_id = "MIC-CFG-MASS"
    inputs = ports(
        Port("mass_items", "m_i", "kg", "user items as (category, mass) pairs"),
        Port("propulsion_items", "m_u,j", "kg", "motor + propeller + ESC mass of each motor, as (category, mass) pairs"),
        Port("battery_mass_kg", "m_b", "kg", "battery mass (MIC-PROP-BAT)", (0, None)),
        Port("max_takeoff_mass_kg", "m_max", "kg", "optional maximum take-off mass", (0, None)),
    )
    outputs = ports(
        Port("total_kg", "m", "kg", "total mass", (0, None)),
        Port("breakdown", "—", "kg", "mass per category"),
        Port("margin_mass", "—", "—", "1 − m / m_max (NaN without m_max)"),
    )
    expected_forms = [Invariant("total and breakdown are exact sums", _exact_sum)]

    def evaluate(self, x):
        breakdown: dict[str, float] = defaultdict(float)
        for category, mass in x.get("mass_items", []):
            breakdown[category] += mass
        for category, mass in x.get("propulsion_items", []):
            breakdown[category] += mass
        breakdown["battery"] += x.get("battery_mass_kg", 0.0)
        total = sum(breakdown.values())
        m_max = x.get("max_takeoff_mass_kg")
        return {
            "total_kg": total,
            "breakdown": dict(breakdown),
            "margin_mass": float("nan") if m_max is None else 1.0 - total / m_max,
        }
