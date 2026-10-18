"""Motor-out hover: does the aircraft still hover when one lift motor stops? (REQ-COST-003, MIC-REL).

For each lift (or tilting) motor k removed, the remaining lift motors must balance, within
their thrust limits T_max,i (maximum static thrust of the unit at the nominal voltage):

- vertical force  Σ T_i = k_dl·m·g,
- pitch moment    Σ T_i·(x_i − x_CG) = 0,
- roll moment     Σ T_i·(y_i − y_CG) = 0,
- yaw torque      Σ s_i·Q_i = 0, s_i = +1 (CCW) / −1 (CW) seen from above, Q_i = κ·D_i·T_i
  (the torque-to-thrust ratio of a propeller scales with its diameter; κ cancels).

The yaw equation is skipped when yaw is controlled by tilting a motor: a tricopter (3 lift
motors, its rear motor tilts for yaw) and any aircraft with tilting motors (vectored yaw).

Solved as a linear programme: minimise z = max_i T_i / T_max,i under the balances and
T_i ≥ 0. Hover survives when a solution exists with z ≤ 1; the remaining thrust-to-weight
is then 1 / z (all motors at full thrust in the same proportions). Single points of failure:
a 4-in-1 ESC (every lift motor), the battery (one pack), any motor whose loss is not
survivable.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import linprog

from predimrc_wrapper.core.units import GRAVITY

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel
    from predimrc_wrapper.aircraft.project import Project


@dataclass
class MotorOut:
    """Hover with one motor stopped."""

    motor: int
    """Stopped motor (0-based)."""
    survivable: bool
    thrust_to_weight: float
    """Remaining thrust-to-weight 1 / max(T_i / T_max,i); 0 when no balance exists."""
    thrusts_n: dict[int, float]
    """Thrust of each remaining motor (N), empty when no balance exists."""
    reason: str


@dataclass
class Reliability:
    """Motor-out hover of every lift motor and the single points of failure."""

    cases: list[MotorOut]
    yaw_by_tilt: bool
    single_points: list[str] = field(default_factory=list)

    @property
    def worst_thrust_to_weight(self) -> float:
        return min((c.thrust_to_weight for c in self.cases), default=float("nan"))

    @property
    def all_survivable(self) -> bool:
        return all(c.survivable for c in self.cases)


def default_spins(project: Project) -> list[int]:
    """+1 (CCW) / −1 (CW) per motor: alternate around the centre of the lift motors, as on
    ArduPilot frames; ``MotorSlot.spin`` replaces the default when given."""
    lift = [i for i, m in enumerate(project.motors) if m.role in ("lift", "tilt")]
    xs = np.array([project.motors[i].x_mm for i in lift])
    ys = np.array([project.motors[i].y_mm for i in lift])
    angles = np.arctan2(ys - ys.mean(), -(xs - xs.mean()))  # clockwise from the nose
    order = [lift[k] for k in np.argsort(angles)]
    spins = [0] * len(project.motors)
    for rank, i in enumerate(order):
        spins[i] = 1 if rank % 2 == 0 else -1
    for i, m in enumerate(project.motors):
        if m.spin is not None:
            spins[i] = 1 if m.spin == "ccw" else -1
    return spins


def yaw_by_tilt(project: Project) -> bool:
    """Yaw controlled by a tilting motor: tricopter, or tilting motors."""
    lift = [m for m in project.motors if m.role in ("lift", "tilt")]
    return any(m.role == "tilt" for m in project.motors) or (
        project.architecture == "multicopter" and len(lift) == 3
    )


def motor_out(aircraft: AircraftModel) -> Reliability:
    """Motor-out hover of each lift motor."""
    project = aircraft.project
    lift = [i for i, m in enumerate(project.motors) if m.role in ("lift", "tilt")]
    weight = aircraft.download_factor * aircraft.total_mass_kg * GRAVITY
    v0 = aircraft.battery.open_circuit_voltage
    t_max = {
        i: float(aircraft.unit_of(project.motors[i]).max_thrust(aircraft.rho, v0))
        for i in lift
    }
    if project.cg_x_mm is not None:
        cg = (project.cg_x_mm, project.cg_y_mm)
    else:  # thrust shared by disc area without CG: the CG is the area centroid
        areas = np.array([aircraft.disc_area_m2(project.motors[i]) for i in lift])
        cg = (
            float(np.average([project.motors[i].x_mm for i in lift], weights=areas)),
            float(np.average([project.motors[i].y_mm for i in lift], weights=areas)),
        )
    spins = default_spins(project)
    by_tilt = yaw_by_tilt(project)
    cases = []
    for k in lift:
        rest = [i for i in lift if i != k]
        rows = [
            [1.0] * len(rest),
            [(project.motors[i].x_mm - cg[0]) / 1000.0 for i in rest],
            [(project.motors[i].y_mm - cg[1]) / 1000.0 for i in rest],
        ]
        rhs = [weight, 0.0, 0.0]
        if not by_tilt:
            rows.append([
                spins[i]
                * project.propulsion_units[project.motors[i].unit].prop_diameter_in
                for i in rest
            ])
            rhs.append(0.0)
        n = len(rest)
        # Variables: T_1..T_n, z. Minimise z with T_i − z·T_max,i ≤ 0.
        c = np.r_[np.zeros(n), 1.0]
        a_ub = np.hstack([np.eye(n), -np.array([[t_max[i]] for i in rest])])
        a_eq = np.hstack([np.array(rows), np.zeros((len(rows), 1))])
        res = linprog(
            c,
            A_ub=a_ub,
            b_ub=np.zeros(n),
            A_eq=a_eq,
            b_eq=rhs,
            bounds=[(0, None)] * (n + 1),
            method="highs",
        )
        if not res.success:
            cases.append(
                MotorOut(
                    k,
                    False,
                    0.0,
                    {},
                    "no thrust split balances the forces and moments"
                    + ("" if by_tilt else " (yaw torque included)"),
                )
            )
            continue
        z = float(res.x[-1])
        thrusts = {i: float(t) for i, t in zip(rest, res.x[:-1], strict=True)}
        ok = z <= 1.0 + 1e-9
        cases.append(
            MotorOut(
                k,
                ok,
                1.0 / z if z > 0 else float("inf"),
                thrusts,
                "balanced within the thrust limits"
                if ok
                else f"needs {100 * z:.0f} % of the maximum thrust of a motor",
            )
        )
    single = ["battery (one pack)"]
    if project.wiring is not None and project.wiring.lift_esc == "four_in_one":
        single.append("4-in-1 ESC (every lift motor)")
    single += [
        f"motor {c.motor + 1} (its loss is not survivable)"
        for c in cases
        if not c.survivable
    ]
    return Reliability(cases, by_tilt, single)
