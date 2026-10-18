"""Cables: resistance, AWG table and default lengths from the geometry (INC2-004).

Positions follow the designer's rules (2026-10-14): the main cable starts downstream of
the battery (its rear end); lift ESCs are one 4-in-1 board or separate ESCs; ESC
positions in % of the fuselage length (cruise ESC, 4-in-1 board, every ESC of a
quadplane) or in % of the arm length (separate lift ESCs of a multicopter / tricopter).
"""

from __future__ import annotations

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


def awg_area_mm2(awg: int) -> float:
    """Cross-section of an AWG wire: d = 0.127 mm · 92^((36 − n) / 39)."""
    d = 0.127 * 92.0 ** ((36 - awg) / 39.0)
    return np.pi * d**2 / 4.0


def resistance_ohm(length_mm: float, awg: int, temperature_c: float = 40.0) -> float:
    """Resistance of one conductor (Ω)."""
    rho = COPPER_RHO_20C * (1.0 + COPPER_ALPHA * (temperature_c - 20.0))
    return rho * (length_mm / 1000.0) / (awg_area_mm2(awg) * 1e-6)


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
    distribution = at_fuselage(spec.lift_esc_position_pct) if four_in_one else (spar if wing_borne else 0.0)
    branches = []
    for i, m in enumerate(project.motors):
        if m.role == "cruise":
            ex, ey, origin = at_fuselage(spec.cruise_esc_position_pct), 0.0, "cruise ESC at % of the fuselage"
        elif four_in_one:
            ex, ey, origin = distribution, 0.0, "4-in-1 ESC at % of the fuselage"
        elif wing_borne:
            ex, ey, origin = at_fuselage(spec.lift_esc_position_pct), 0.0, "separate ESC at % of the fuselage"
        else:
            f = spec.lift_esc_position_pct / 100.0
            ex, ey, origin = f * m.x_mm, f * m.y_mm, "separate ESC at % of the arm"
        if wing_borne and abs(m.y_mm) > 1.0:
            # Along the fuselage to the wing spar, laterally to the boom, along the boom.
            phase = abs(ex - spar) + abs(m.y_mm - ey) + abs(m.x_mm - spar)
        else:
            phase = float(np.hypot(m.x_mm - ex, m.y_mm - ey))
        if four_in_one and m.role != "cruise":
            dc = 0.0
        elif wing_borne:
            dc = float(abs(ex - distribution) + abs(ey))  # along the fuselage
        else:
            dc = float(np.hypot(ex - distribution, ey))  # along the arm from the centre
        branches.append(BranchLengths(i, dc, phase, ex, ey, origin))
    return WiringLayout(battery_rear, distribution, abs(distribution - battery_rear), branches)
