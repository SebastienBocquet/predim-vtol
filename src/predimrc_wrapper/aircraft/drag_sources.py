"""Drag of each parasitic source with its model shown (INC2-006, MIC-CFG-DRAG).

V-arms: one straight arm per motor from its root under the fuselage to the motor; frontal
area A = Σ t·L_i·√(1 − u_x,i²) (beam of thickness t seen by the flow along x), CdS =
C_d(shape)·A, C_d from the PredimRC accessory shapes. Body part: CdS = C_d(shape)·A.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.aircraft.drag import DragModel
from predimrc_wrapper.core.units import MM
from predimrc_wrapper.data.drag_shapes import shape_cd

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import DragSource
    from predimrc_wrapper.aircraft.project import Project


@dataclass
class ArmSegment:
    """One V-arm, mm."""

    motor_index: int
    root: tuple[float, float, float]
    tip: tuple[float, float, float]

    @property
    def length_mm(self) -> float:
        return float(np.linalg.norm(np.subtract(self.tip, self.root)))

    @property
    def sin_to_flow(self) -> float:
        dx = self.tip[0] - self.root[0]
        return float(np.sqrt(max(0.0, 1.0 - (dx / self.length_mm) ** 2))) if self.length_mm > 0 else 0.0


@dataclass
class CdsResult:
    """Drag area of one source and how it was obtained."""

    name: str
    kind: str
    cds_m2: float
    model: str
    formula: str
    coefficient_source: str
    frontal_area_m2: float = float("nan")
    cd: float = float("nan")
    area_from: str = ""
    arms: list[ArmSegment] | None = None


def v_arm_segments(source: DragSource, project: Project) -> list[ArmSegment]:
    """Arms from their roots under the fuselage to the motors (defaults from the geometry)."""
    if project.aero is not None:
        fus = project.aero.fuselage
        x_a = source.attach_x_mm if source.attach_x_mm is not None else 0.25 * project.aero.wing.root_chord_mm
        z_a = source.attach_z_mm if source.attach_z_mm is not None else -fus.height_mm / 2
        half = source.attach_half_width_mm if source.attach_half_width_mm is not None else fus.width_mm / 2
    else:
        x_a = source.attach_x_mm if source.attach_x_mm is not None else 0.0
        z_a = source.attach_z_mm if source.attach_z_mm is not None else -40.0
        half = source.attach_half_width_mm if source.attach_half_width_mm is not None else 0.0
    indexes = source.motors if source.motors is not None else [
        i for i, m in enumerate(project.motors) if m.role in ("lift", "tilt")]
    arms = []
    for i in indexes:
        m = project.motors[i]
        y_root = float(np.sign(m.y_mm)) * half
        arms.append(ArmSegment(i, (x_a, y_root, z_a), (m.x_mm, m.y_mm, source.motor_z_mm)))
    return arms


def source_cds(source: DragSource, project: Project, model: DragModel | None = None) -> CdsResult:
    """Drag area of a project drag source, with its model and coefficient source."""
    model = model or DragModel()
    n = source.count
    if source.kind == "boom":
        d, length = source.diameter_mm * MM, source.length_mm * MM
        cds = model.cds({"kind": "boom", "count": n, "diameter_m": d, "length_m": length})
        return CdsResult(source.name, "boom", cds, "boom: skin friction + base drag",
                         f"n·(C_f·π·d·L + C_d,end·π·d²/4), C_f = {model.p.boom_cf}, C_d,end = {model.p.boom_cd_end}",
                         "generic turbulent flat plate; generic base drag", np.pi * d**2 / 4 * n, area_from="user")
    if source.kind == "stopped_rotor":
        cds = model.cds({"kind": "stopped_rotor", "count": n, "n_blades": source.n_blades,
                         "blade_chord_m": source.blade_chord_mm * MM, "radius_m": source.radius_mm * MM})
        return CdsResult(source.name, "stopped_rotor", cds, "stopped rotor: blade planform drag",
                         f"n·B·c̄·R·C_d,b, C_d,b = {model.p.blade_cd}", "generic, blades aligned with the flow",
                         area_from="user")
    if source.kind == "cds":
        return CdsResult(source.name, "cds", n * source.cds_m2, "free drag area", "n·CdS", "user", area_from="user")
    shape = shape_cd(source.shape)
    if source.kind == "body_part":
        area = n * source.frontal_area_dm2 / 100.0
        return CdsResult(source.name, "body_part", shape.cd * area, f"body part, shape {shape.label}",
                         f"C_d·A, C_d = {shape.cd:g}", shape.source, area, shape.cd, "user")
    arms = v_arm_segments(source, project)
    if source.frontal_area_dm2 is not None:
        area, origin = n * source.frontal_area_dm2 / 100.0, "user"
    else:
        area = n * sum(source.thickness_mm * a.length_mm * a.sin_to_flow for a in arms) * MM**2
        origin = "geometry"
    return CdsResult(source.name, "v_arms", shape.cd * area, f"V-arms, shape {shape.label}",
                     f"C_d·Σ t·L_i·√(1 − u_x,i²), C_d = {shape.cd:g}, t = {source.thickness_mm:g} mm, "
                     f"{len(arms)} arms", shape.source, area, shape.cd, origin, arms)


def drag_report(project: Project) -> list[CdsResult]:
    """Every drag source of the project with its CdS and model."""
    model = DragModel()
    return [source_cds(s, project, model) for s in project.drag_sources]
