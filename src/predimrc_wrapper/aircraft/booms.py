"""Booms carrying the lift motors: geometry and drag (REQ-CFG-014, REQ-CFG-004, MIC-CFG-DRAG).

Two layouts, set in the configuration tab (``Project.booms``):

- **parallel**: booms along the flow, one per lateral station of off-centreline lift motors,
  from the front motor to the rear one, at least to the wing spar (quadplane 4+1). Drag: skin friction on the wetted
  area plus base drag on the cross-section, CdS = C_f·p·L + C_d,base·A_section.
- **diagonal**: one straight boom per lift motor, from an anchor under the fuselage to the
  motor. Drag by the cross-flow principle (Hoerner, *Fluid-Dynamic Drag*, 1965): the flow
  component normal to the boom sets the force, D = ½ρV²·C_d,section·sin²θ·A_frontal with
  the frontal area A_frontal = t·L·sin θ (t: thickness seen by the flow, L: boom length,
  θ: angle between the boom and the flow), plus the skin friction C_f·p·L of the wetted
  surface (p: perimeter of the section), which remains when the boom is aligned with the
  flow. Hence CdS = C_d,section·t·L·sin³θ + C_f·p·L.

Section coefficients (``data/boom_sections.yaml``) are referred to the frontal area t·L of a
member normal to the flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.core.units import MM
from predimrc_wrapper.data.boom_sections import boom_section

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import BoomSpec
    from predimrc_wrapper.aircraft.project import Project


@dataclass
class Boom:
    """One straight boom, coordinates in mm (x aft, y right, z up)."""

    motors: list[int]
    """Motors carried (0-based)."""
    root: tuple[float, float, float]
    tip: tuple[float, float, float]

    @property
    def length_mm(self) -> float:
        return float(np.linalg.norm(np.subtract(self.tip, self.root)))

    @property
    def sin_to_flow(self) -> float:
        """sin θ, θ the angle between the boom and the flow (x axis)."""
        if self.length_mm <= 0:
            return 0.0
        ux = (self.tip[0] - self.root[0]) / self.length_mm
        return float(np.sqrt(max(0.0, 1.0 - ux**2)))

    @property
    def angle_to_flow_deg(self) -> float:
        return float(np.degrees(np.arcsin(min(1.0, self.sin_to_flow))))


@dataclass
class BoomDrag:
    """Drag area of one boom with its model."""

    boom: Boom
    layout: str
    section: str
    frontal_area_m2: float
    cd_effective: float
    """C_d referred to the frontal area (diagonal: C_d,section·sin²θ)."""
    cds_m2: float
    formula: str
    coefficient_source: str


def anchor(project: Project, spec: BoomSpec) -> tuple[float, float, float]:
    """(x, half width, z) of the diagonal-boom anchor, defaults from the fuselage."""
    if project.aero is not None:
        fus = project.aero.fuselage
        x = 0.25 * project.aero.wing.root_chord_mm
        half, z = fus.width_mm / 2.0, -fus.height_mm / 2.0
    else:  # arms of a frame, in the plane of the motors
        x, half, z = 0.0, 0.0, spec.motor_z_mm
    return (
        spec.anchor_x_mm if spec.anchor_x_mm is not None else x,
        spec.anchor_half_width_mm if spec.anchor_half_width_mm is not None else half,
        spec.anchor_z_mm if spec.anchor_z_mm is not None else z,
    )


def _spar_x(project: Project) -> float:
    """Station of the wing spar (quarter root chord), where parallel booms are attached."""
    return 0.25 * project.aero.wing.root_chord_mm if project.aero is not None else 0.0


def booms(project: Project) -> list[Boom]:
    """The booms of the project (none when ``project.booms`` is not set)."""
    spec = project.booms
    if spec is None:
        return []
    lift = [i for i, m in enumerate(project.motors) if m.role in ("lift", "tilt")]
    if spec.layout == "diagonal":
        x_a, half, z_a = anchor(project, spec)
        out = []
        for i in lift:
            m = project.motors[i]
            y_root = float(np.sign(m.y_mm)) * half
            out.append(Boom([i], (x_a, y_root, z_a), (m.x_mm, m.y_mm, spec.motor_z_mm)))
        return out
    by_y: dict[float, list[int]] = {}
    for i in lift:
        y = project.motors[i].y_mm
        if abs(y) > 1.0:
            by_y.setdefault(round(y, 1), []).append(i)
    out = []
    spar = _spar_x(project)
    for y, idx in by_y.items():
        xs = [project.motors[i].x_mm for i in idx]
        # From the front motor to the rear motor, at least to the wing spar.
        x0, x1 = min(*xs, spar), max(*xs, spar)
        out.append(Boom(idx, (x0, y, spec.motor_z_mm), (x1, y, spec.motor_z_mm)))
    return out


def boom_drag(project: Project, cf: float, cd_base: float) -> list[BoomDrag]:
    """Drag area of every boom (cross-flow for diagonal booms, friction + base for parallel ones)."""
    spec = project.booms
    if spec is None:
        return []
    section = boom_section(spec.section)
    t = spec.thickness_mm * MM
    chord = (spec.chord_mm or 4.0 * spec.thickness_mm) * MM
    perimeter, a_section = section.perimeter_and_area(t, chord)
    out = []
    for b in booms(project):
        length = b.length_mm * MM
        if spec.layout == "diagonal":
            s = b.sin_to_flow
            area = t * length * s
            cd = section.cd * s**2
            out.append(
                BoomDrag(
                    b,
                    "diagonal",
                    spec.section,
                    area,
                    cd,
                    cd * area + cf * perimeter * length,
                    f"cross-flow C_d·sin²θ·(t·L·sin θ) + friction C_f·p·L, C_d = {section.cd:g}, "
                    f"C_f = {cf:g}, t = {spec.thickness_mm:g} mm, L = {b.length_mm:.0f} mm, "
                    f"θ = {b.angle_to_flow_deg:.0f}°",
                    section.source + "; skin friction: generic turbulent flat plate",
                )
            )
            continue
        cds = cf * perimeter * length + cd_base * a_section
        out.append(
            BoomDrag(
                b,
                "parallel",
                spec.section,
                a_section,
                cds / a_section if a_section > 0 else float("nan"),
                cds,
                f"C_f·p·L + C_d,base·A, C_f = {cf:g}, C_d,base = {cd_base:g}, "
                f"p = {perimeter / MM:.0f} mm, L = {b.length_mm:.0f} mm",
                "generic turbulent flat plate; generic base drag",
            )
        )
    return out
