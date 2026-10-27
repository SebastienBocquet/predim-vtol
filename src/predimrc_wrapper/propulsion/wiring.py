"""Cables: resistance, AWG table and default lengths from the geometry (INC2-004).

Positions follow the designer's rules (2026-10-14): the main cable starts downstream of
the battery (its rear end); lift ESCs are one 4-in-1 board or separate ESCs, the cruise
motors on the 4-in-1 board or on separate ESCs (``cruise_on_four_in_one``); ESC
positions in % of the fuselage length (cruise ESC, 4-in-1 board, every ESC of a
quadplane) or in % of the arm length (separate lift ESCs of a multicopter / tricopter).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import Project

COPPER_RHO_20C = 1.72e-8
"""Copper resistivity at 20 °C (Ω·m)."""

COPPER_ALPHA = 0.00393
"""Temperature coefficient of copper (1/K)."""

AMPACITY_A = {10: 55.0, 12: 41.0, 14: 32.0, 16: 22.0, 18: 16.0, 20: 11.0, 22: 7.0}
"""Continuous current of a single conductor in free air (chassis wiring practice, A)."""

COPPER_DENSITY_G_CM3 = 8.96
SILICONE_DENSITY_G_CM3 = 1.2


def silicone_wall_mm(awg: int) -> float:
    """Insulation wall of RC silicone wire (mm).

    Linear in the gauge through two published wires (Pimoroni dual silicone wire, 1 m red +
    1 m black: 20 AWG 1.8 mm OD 14.2 g, 14 AWG 3.5 mm OD 56.3 g,
    https://shop.pimoroni.com/en-eu/products/dual-silicone-wire-per-metre, 2026-10-19):
    walls 0.49 mm (20 AWG) and 0.94 mm (14 AWG).
    """
    return 0.94 - 0.075 * (awg - 14)


def conductor_mass_g_per_m(awg: int) -> float:
    """Mass of one silicone-insulated conductor (g/m): copper plus silicone wall.

    Reproduces the two published wires to 2 % (7.0 and 27.9 g/m per conductor against 7.1 and
    28.2).
    """
    area_cu = awg_area_mm2(awg)
    d = np.sqrt(4.0 * area_cu / np.pi)
    od = d + 2.0 * silicone_wall_mm(awg)
    area_si = np.pi / 4.0 * (od**2 - d**2)
    return float(area_cu * COPPER_DENSITY_G_CM3 + area_si * SILICONE_DENSITY_G_CM3)


def awg_area_mm2(awg: int) -> float:
    """Cross-section of an AWG wire: d = 0.127 mm · 92^((36 − n) / 39)."""
    d = 0.127 * 92.0 ** ((36 - awg) / 39.0)
    return np.pi * d**2 / 4.0


def resistance_ohm(length_mm: float, awg: int, temperature_c: float = 40.0) -> float:
    """Resistance of one conductor (Ω)."""
    rho = COPPER_RHO_20C * (1.0 + COPPER_ALPHA * (temperature_c - 20.0))
    return rho * (length_mm / 1000.0) / (awg_area_mm2(awg) * 1e-6)


def default_gauges(project: Project) -> tuple[int, list[tuple[int, int]]]:
    """(main AWG, [(DC AWG, phase AWG) per motor]): entered, else sized for the maximum current.

    The cables are installed for the full-throttle current, so each branch is sized for the
    maximum current I_max of its motor (data sheet) and the main cable for the largest of
    Σ I_max of the lift motors and Σ I_max of the cruise motors; the same cables at every
    operating point (losses, mass, cost).
    """
    from predimrc_wrapper.aircraft.project import WiringSpec  # noqa: PLC0415
    from predimrc_wrapper.data import default_database  # noqa: PLC0415

    spec = project.wiring or WiringSpec()
    db = default_database()
    i_max = [
        db.motor(project.propulsion_units[m.unit].motor_id).i_max
        for m in project.motors
    ]
    lift = sum(
        i for i, m in zip(i_max, project.motors, strict=True) if m.role != "cruise"
    )
    cruise = sum(
        i for i, m in zip(i_max, project.motors, strict=True) if m.role != "lift"
    )
    main = spec.main_awg or awg_for_current(max(lift, cruise))
    branches = [
        (spec.dc_awg or awg_for_current(i), spec.phase_awg or awg_for_current(i))
        for i in i_max
    ]
    return main, branches


def cable_rows_mass(project: Project) -> list[dict]:
    """Every cable with its length, conductors, gauge and mass (main, DC, phase)."""
    from predimrc_wrapper.aircraft.project import WiringSpec  # noqa: PLC0415

    spec = project.wiring or WiringSpec()
    layout = default_layout(project)
    overrides = {o.motor_index: o for o in spec.overrides}
    main_awg, gauges = default_gauges(project)
    rows = [
        ("main", "battery → distribution point", layout.main_length_mm, 2, main_awg)
    ]
    for b, (dc_awg, phase_awg), m in zip(
        layout.branches, gauges, project.motors, strict=True
    ):
        o = overrides.get(b.motor_index)
        dc = o.dc_length_mm if (o and o.dc_length_mm is not None) else b.dc_length_mm
        phase = (
            o.phase_length_mm
            if (o and o.phase_length_mm is not None)
            else b.phase_length_mm
        )
        name = f"motor {b.motor_index + 1} ({m.unit})"
        if dc > 0:
            rows.append(("DC", f"distribution → ESC of {name}", dc, 2, dc_awg))
        rows.append(("phase", f"ESC → {name}", phase, 3, phase_awg))
    return [
        {
            "cable": kind,
            "from → to": path,
            "length (mm)": round(length),
            "conductors": n,
            "gauge (AWG)": awg,
            "mass (g)": round(n * length / 1000.0 * conductor_mass_g_per_m(awg), 1),
        }
        for kind, path, length, n, awg in rows
    ]


def wiring_mass_kg(project: Project) -> float:
    """Mass of all the cables (kg)."""
    return sum(r["mass (g)"] for r in cable_rows_mass(project)) / 1000.0


def awg_for_current(current_a: float, margin: float = 1.25) -> int:
    """Smallest wire (highest AWG) whose ampacity exceeds margin × current."""
    for awg in sorted(AMPACITY_A, reverse=True):
        if AMPACITY_A[awg] >= margin * current_a:
            return awg
    return min(AMPACITY_A)


@dataclass
class BranchLengths:
    """Default lengths of the cables of one motor (mm) and how they were obtained."""

    motor_index: int
    dc_length_mm: float
    """Distribution point → ESC (2 conductors); 0 for a 4-in-1 board."""
    phase_length_mm: float
    """ESC → motor (3 conductors)."""
    esc_x_mm: float
    esc_y_mm: float
    origin: str


@dataclass
class WiringLayout:
    """Default cable layout of a project."""

    battery_rear_x_mm: float
    distribution_x_mm: float
    main_length_mm: float
    branches: list[BranchLengths]


def _fuselage(project: Project) -> tuple[float, float]:
    """(x of the nose, length) of the fuselage; a rotary frame is a virtual body of 0 length at the centre."""
    if project.aero is not None:
        fus = project.aero.fuselage
        return -fus.nose_lever_mm, fus.length_mm
    return 0.0, 0.0


def phase_path(
    project: Project, index: int, esc_x_mm: float, esc_y_mm: float
) -> list[tuple[float, float, float]]:
    """Path of the phase cables ESC → motor (x, y, z in mm), following the structure.

    - diagonal booms: along the fuselage to the boom anchor, across to the anchor of the
      motor's side, then along the boom;
    - winged aircraft, off-centreline motor: along the fuselage to the wing spar, along the
      spar to the boom, along the boom;
    - otherwise straight (arm of a frame, centreline motor).
    """
    from predimrc_wrapper.aircraft.booms import anchor  # noqa: PLC0415

    m = project.motors[index]
    spec = project.booms
    start = (esc_x_mm, esc_y_mm, 0.0)
    if (
        spec is not None
        and spec.layout == "diagonal"
        and m.role in ("lift", "tilt")
        and project.aero is not None
    ):
        x_a, half, z_a = anchor(project, spec)
        y_a = float(np.sign(m.y_mm)) * half
        return [
            start,
            (x_a, esc_y_mm, 0.0),
            (x_a, y_a, z_a),
            (m.x_mm, m.y_mm, spec.motor_z_mm),
        ]
    if project.aero is not None and abs(m.y_mm) > 1.0:
        spar = 0.25 * project.aero.wing.root_chord_mm
        return [
            start,
            (spar, esc_y_mm, 0.0),
            (spar, m.y_mm, 0.0),
            (m.x_mm, m.y_mm, 0.0),
        ]
    return [start, (m.x_mm, m.y_mm, 0.0)]


def path_length_mm(path: list[tuple[float, float, float]]) -> float:
    """Length of a polyline (mm)."""
    return float(
        sum(np.linalg.norm(np.subtract(b, a)) for a, b in itertools.pairwise(path))
    )


def default_layout(project: Project) -> WiringLayout:
    """Cable lengths from the geometry and the wiring choices of the project."""
    from predimrc_wrapper.aircraft.project import WiringSpec  # noqa: PLC0415

    spec = project.wiring or WiringSpec()
    x_nose, length = _fuselage(project)
    wing_borne = project.aero is not None
    if wing_borne:
        battery_rear = x_nose + spec.battery_length_mm
        spar = 0.25 * project.aero.wing.root_chord_mm
    else:  # battery centred on the frame
        battery_rear = spec.battery_length_mm / 2.0
        spar = 0.0

    def at_fuselage(pct: float) -> float:
        return x_nose + pct / 100.0 * length if wing_borne else 0.0

    four_in_one = spec.lift_esc == "four_in_one"
    distribution = (
        at_fuselage(spec.lift_esc_position_pct)
        if four_in_one
        else (spar if wing_borne else 0.0)
    )
    branches = []
    for i, m in enumerate(project.motors):
        on_board = project.on_four_in_one(m)
        if on_board:
            ex, ey, origin = distribution, 0.0, "4-in-1 ESC at % of the fuselage"
        elif m.role == "cruise":
            ex, ey, origin = (
                at_fuselage(spec.cruise_esc_position_pct),
                0.0,
                "cruise ESC at % of the fuselage",
            )
        elif wing_borne:
            ex, ey, origin = (
                at_fuselage(spec.lift_esc_position_pct),
                0.0,
                "separate ESC at % of the fuselage",
            )
        else:
            f = spec.lift_esc_position_pct / 100.0
            ex, ey, origin = f * m.x_mm, f * m.y_mm, "separate ESC at % of the arm"
        phase = path_length_mm(phase_path(project, i, ex, ey))
        if on_board:
            dc = 0.0
        elif wing_borne:
            dc = float(abs(ex - distribution) + abs(ey))  # along the fuselage
        else:
            dc = float(np.hypot(ex - distribution, ey))  # along the arm from the centre
        branches.append(BranchLengths(i, dc, phase, ex, ey, origin))
    return WiringLayout(
        battery_rear, distribution, abs(distribution - battery_rear), branches
    )
