"""Drag tab: the booms with their model (REQ-CFG-004, REQ-CFG-014)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult

BOOM_DRAG_LATEX = (
    r"D_i = \tfrac12\rho V^2\Big(C_{d,section}\,\sin^2\theta_i\;A_i + C_f\,p\,L_i\Big),"
    r"\qquad A_i = t\,L_i\,\sin\theta_i"
)
"""Drag of a diagonal boom (cross-flow principle on the frontal area, plus skin friction)."""


def boom_rows(project: Project, two: TwoPhaseResult | None = None) -> list[dict]:
    """One row per boom: geometry, frontal area, effective C_d, CdS and drag power at V1."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.aircraft.booms import boom_drag  # noqa: PLC0415

    aircraft = AircraftModel(project)
    model = aircraft.drag_model
    v1 = two.cruise[0].v_m_s if two is not None and two.cruise else None
    rows = []
    for k, b in enumerate(boom_drag(project, model.p.boom_cf, model.p.boom_cd_end), 1):
        row = {
            "boom": k,
            "motors": ", ".join(str(i + 1) for i in b.boom.motors),
            "layout": b.layout,
            "section": b.section,
            "length (mm)": round(b.boom.length_mm),
            "angle to the flow θ (°)": round(b.boom.angle_to_flow_deg, 1),
            "frontal area (dm²)": round(100 * b.frontal_area_m2, 3),
            "C_d effective": None
            if not np.isfinite(b.cd_effective)
            else round(b.cd_effective, 3),
            "CdS (dm²)": round(100 * b.cds_m2, 4),
            "formula": b.formula,
            "coefficient source": b.coefficient_source,
        }
        if v1 is not None:
            row["drag power at V1 (W)"] = round(
                0.5 * aircraft.rho * v1**3 * b.cds_m2, 2
            )
        rows.append(row)
    return rows
