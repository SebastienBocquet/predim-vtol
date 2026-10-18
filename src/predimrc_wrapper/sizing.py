"""Motor pre-selection: range of motor power per propulsion unit from a target mass range.

Hover battery power law, fitted on a reference aircraft (default: tricopter of 1.87 kg,
280 W measured in hover):

    P_h(m) = P_ref·(m / m_ref)^k

k = 1 when the propellers grow with the aircraft (constant disc loading per kg), k = 1.5
with the same propellers (momentum theory, P ∝ T^1.5). P_h is shared between the lift
rotors as the momentum power T_i^1.5/√A_i of their hover thrusts (CG balance, see
``hover_thrust_split``). A lift motor must deliver its share at the minimum
thrust-to-weight: P_i = s_i·P_h(m)·(T/W)^1.5. A cruise motor of a wing-borne aircraft
must deliver P_c = m·g·V_max / ((L/D)·η) shared by disc area; a tilting motor the larger
of both. The accepted range of a unit type is [min P_i(m_min); headroom·max P_i(m_max)].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.aircraft.model import hover_thrust_split
from predimrc_wrapper.aircraft.project import CRUISE_ROLES
from predimrc_wrapper.aircraft.project import ProjectError
from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.core.units import INCH
from predimrc_wrapper.core.units import MM
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import default_database

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import Project
    from predimrc_wrapper.aircraft.project import SizingSpec


@dataclass
class PowerRange:
    """Motor power range of one propulsion unit type."""

    unit: str
    roles: list[str]
    n_motors: int
    need_low_w: float
    """Power needed at the minimum target mass (W)."""
    need_high_w: float
    """Power needed at the maximum target mass (W)."""
    accepted_high_w: float
    """Largest accepted motor power: headroom × need_high_w (W)."""
    candidates: list[str]
    """Database motors whose maximum power is within [need_low_w, accepted_high_w]."""
    current_motor: str
    current_p_max_w: float

    @property
    def current_in_range(self) -> bool:
        return self.need_low_w <= self.current_p_max_w <= self.accepted_high_w


def _reference_point(model: MotorPowerLaw) -> bool:
    y = model.evaluate({
        "mass_kg": model.p.reference_mass_kg,
        "power_share": 1.0,
        "thrust_to_weight": 1.0,
    })
    return bool(
        np.isclose(y["hover_power_w"], model.p.reference_hover_power_w, rtol=1e-12)
        and np.isclose(y["motor_power_w"], model.p.reference_hover_power_w, rtol=1e-12)
    )


class MotorPowerLaw(Model):
    """Hover power law and power needed by one lift motor.

    P_h = P_ref·(m / m_ref)^k; P_i = s_i·P_h·(T/W)^1.5.
    """

    mic_id = "MIC-CFG-SIZ"
    inputs = ports(
        Port("mass_kg", "m", "kg", "take-off mass", (0, None)),
        Port(
            "power_share",
            "s_i",
            "—",
            "share of the hover power taken by the motor",
            (0, 1),
        ),
        Port("thrust_to_weight", "T/W", "—", "thrust-to-weight to deliver", (1, None)),
    )
    outputs = ports(
        Port(
            "hover_power_w",
            "P_h",
            "W",
            "hover battery power of the aircraft",
            (0, None),
        ),
        Port("motor_power_w", "P_i", "W", "power the motor must deliver", (0, None)),
    )
    parameters = params(
        Param(
            "reference_mass_kg",
            "m_ref",
            "kg",
            "mass of the reference aircraft",
            default=1.87,
            bounds=(0, None),
            source="user tricopter, 2026-10-13",
        ),
        Param(
            "reference_hover_power_w",
            "P_ref",
            "W",
            "measured hover battery power of the reference",
            default=280.0,
            bounds=(0, None),
            source="user tricopter, 2026-10-13",
        ),
        Param(
            "mass_exponent",
            "k",
            "—",
            "1: propellers grow with the aircraft; 1.5: same propellers",
            default=1.0,
            bounds=(0, 2),
            source="momentum theory",
        ),
    )
    expected_forms = [
        ScalingLaw(
            "hover_power_w",
            "mass_kg",
            1.0,
            fixed={"power_share": 1.0, "thrust_to_weight": 1.0},
            lower=0.5,
            upper=5.0,
        ),
        ScalingLaw(
            "motor_power_w",
            "thrust_to_weight",
            1.5,
            fixed={"mass_kg": 2.0, "power_share": 0.25},
            lower=1.0,
            upper=3.0,
        ),
        Invariant("reference point reproduced", _reference_point),
    ]

    @classmethod
    def from_spec(cls, spec: SizingSpec) -> MotorPowerLaw:
        return cls(
            reference_mass_kg=spec.reference_mass_kg,
            reference_hover_power_w=spec.reference_hover_power_w,
            mass_exponent=spec.mass_exponent,
        )

    def evaluate(self, x):
        m = np.asarray(x["mass_kg"], dtype=float)
        hover = (
            self.p.reference_hover_power_w
            * (m / self.p.reference_mass_kg) ** self.p.mass_exponent
        )
        share = np.asarray(x.get("power_share", 1.0), dtype=float)
        tw = np.asarray(x.get("thrust_to_weight", 1.0), dtype=float)
        return {"hover_power_w": hover, "motor_power_w": share * hover * tw**1.5}


def hover_power_w(spec: SizingSpec, mass_kg: float | np.ndarray) -> float | np.ndarray:
    """Hover battery power of the law P_ref·(m / m_ref)^k (W)."""
    return MotorPowerLaw.from_spec(spec).evaluate({"mass_kg": mass_kg})["hover_power_w"]


def _per_motor_need(project: Project, spec: SizingSpec, mass_kg: float) -> list[float]:
    """Power needed by each motor of the project at a mass (W), in the order of ``motors``."""
    units = project.propulsion_units
    lift = project.lift_motors()
    area = np.array([
        np.pi * (units[m.unit].prop_diameter_in * INCH) ** 2 / 4.0 for m in lift
    ])
    try:
        fractions = hover_thrust_split(
            np.array([m.x_mm * MM for m in lift]),
            np.array([m.y_mm * MM for m in lift]),
            area,
            None
            if project.cg_x_mm is None
            else (project.cg_x_mm * MM, project.cg_y_mm * MM),
        )
    except ProjectError:
        fractions = area / area.sum()
    momentum = fractions**1.5 / np.sqrt(area)
    lift_need = MotorPowerLaw.from_spec(spec).evaluate({
        "mass_kg": mass_kg,
        "power_share": momentum / momentum.sum(),
        "thrust_to_weight": project.mission.min_thrust_to_weight,
    })["motor_power_w"]
    lift_need_by_id = {id(m): float(p) for m, p in zip(lift, lift_need, strict=False)}
    cruise = (
        [m for m in project.motors if m.role in CRUISE_ROLES]
        if project.architecture == "quadplane"
        else []
    )
    cruise_need_by_id = {}
    if cruise:
        c_area = np.array([
            np.pi * (units[m.unit].prop_diameter_in * INCH) ** 2 / 4.0 for m in cruise
        ])
        total = (
            mass_kg
            * GRAVITY
            * spec.cruise_max_speed_m_s
            / (spec.cruise_lift_to_drag * spec.cruise_overall_efficiency)
        )
        cruise_need_by_id = {
            id(m): float(total * a / c_area.sum())
            for m, a in zip(cruise, c_area, strict=False)
        }
    return [
        max(lift_need_by_id.get(id(m), 0.0), cruise_need_by_id.get(id(m), 0.0))
        for m in project.motors
    ]


def motor_power_ranges(
    project: Project, db: MotorDatabase | None = None
) -> list[PowerRange]:
    """Power range and candidate motors of each propulsion unit type of a project with a ``sizing`` block.

    Raises:
        ValueError: When the project has no ``sizing`` block.
    """
    spec = project.sizing
    if spec is None:
        msg = "The project has no 'sizing' block (target mass range)."
        raise ValueError(msg)
    db = db or default_database()
    low_mass, high_mass = spec.target_mass_kg
    low, high = (
        _per_motor_need(project, spec, low_mass),
        _per_motor_need(project, spec, high_mass),
    )
    out = []
    for name, unit in project.propulsion_units.items():
        idx = [i for i, m in enumerate(project.motors) if m.unit == name]
        if not idx:
            continue
        need_low, need_high = min(low[i] for i in idx), max(high[i] for i in idx)
        accepted = spec.headroom * need_high
        candidates = sorted(
            (m for m in db.records.values() if need_low <= m.p_max <= accepted),
            key=lambda m: m.p_max,
        )
        out.append(
            PowerRange(
                unit=name,
                roles=sorted({project.motors[i].role for i in idx}),
                n_motors=len(idx),
                need_low_w=need_low,
                need_high_w=need_high,
                accepted_high_w=accepted,
                candidates=[m.id for m in candidates],
                current_motor=unit.motor_id,
                current_p_max_w=db.motor(unit.motor_id).p_max,
            )
        )
    return out


__all__ = ["MotorPowerLaw", "PowerRange", "hover_power_w", "motor_power_ranges"]
