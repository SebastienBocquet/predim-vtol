"""Parasitic drag sources and total drag polar (MIC-CFG-DRAG, MVP variant)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports


@dataclass(frozen=True)
class SpeedPolar:
    """Drag of the clean airframe versus speed, at one mass and one density."""

    v_m_s: np.ndarray
    """Speeds (m/s), increasing."""
    drag_n: np.ndarray
    """Drag (N)."""
    rho: float
    """Density at which the polar was computed (kg/m³)."""


def _sum_of_sources(model: DragModel) -> bool:
    sources = [{"kind": "cds", "cds_m2": 0.01, "count": 2}, {"kind": "cds", "cds_m2": 0.005, "count": 1}]
    y = model.evaluate({"sources": sources, "v_m_s": 10.0, "rho": 1.2, "body_cds_m2": 0.0})
    return abs(y["cds_dedicated_m2"] - 0.025) < 1e-15 and abs(float(y["drag_n"]) - 0.5 * 1.2 * 100 * 0.025) < 1e-12


class DragModel(Model):
    """Total drag D(V).

    Boom: CdS = C_f·π·d·L + C_d,end·π·d²/4. Stopped rotor: CdS = n_b·c̄·R·C_d,b.
    Quadplane: D = D_PredimRC(V·√(ρ/ρ_p)) + ½·ρ·V²·ΣCdS (equal dynamic pressure, Reynolds
    neglected). Multicopter: D = ½·ρ·V²·(CdS_body + ΣCdS).
    """

    mic_id = "MIC-CFG-DRAG"
    inputs = ports(
        Port("sources", "—", "—", "list of {kind: boom | stopped_rotor | cds, count, ...}"),
        Port("v_m_s", "V", "m/s", "true airspeed", (0, None)),
        Port("rho", "ρ", "kg/m³", "air density", (0, None)),
        Port("polar", "—", "—", "PredimRC speed polar at the total mass (quadplane)"),
        Port("body_cds_m2", "CdS_b", "m²", "body drag area (multicopter)", (0, None)),
    )
    outputs = ports(
        Port("cds_dedicated_m2", "ΣCdS", "m²", "sum of dedicated drag areas", (0, None)),
        Port("drag_n", "D", "N", "total drag at V (NaN outside the polar)", (0, None)),
        Port("v_min_m_s", "V_min", "m/s", "lowest valid polar speed at ρ (quadplane)", (0, None)),
    )
    parameters = params(
        Param("boom_cf", "C_f", "—", "boom skin friction coefficient", default=0.005, bounds=(0, None), source="generic turbulent flat plate"),
        Param("boom_cd_end", "C_d,end", "—", "boom base drag coefficient", default=0.15, bounds=(0, None), source="generic"),
        Param("blade_cd", "C_d,b", "—", "stopped blade drag (blade planform)", default=0.05, bounds=(0, None), source="generic, blades aligned"),
    )
    expected_forms = [
        ScalingLaw("drag_n", "v_m_s", 2.0, fixed={"sources": [], "rho": 1.2, "body_cds_m2": 0.03}, lower=2.0, upper=30.0),
        Invariant("ΣCdS is the sum of the sources", _sum_of_sources),
    ]

    def cds(self, source: dict) -> float:
        """Drag area of one source, multiplied by its count (m²)."""
        kind, count = source["kind"], source.get("count", 1)
        if kind == "boom":
            d, length = source["diameter_m"], source["length_m"]
            one = self.p.boom_cf * np.pi * d * length + self.p.boom_cd_end * np.pi * d**2 / 4.0
        elif kind == "stopped_rotor":
            one = source.get("n_blades", 2) * source["blade_chord_m"] * source["radius_m"] * self.p.blade_cd
        elif kind == "cds":
            one = source["cds_m2"]
        else:
            msg = f"Unknown drag source kind '{kind}'."
            raise ValueError(msg)
        return count * one

    def evaluate(self, x):
        v = np.asarray(x["v_m_s"], dtype=float)
        rho = float(x["rho"])
        cds = sum(self.cds(s) for s in x.get("sources", []))
        body = x.get("body_cds_m2") or 0.0
        parasitic = 0.5 * rho * v**2 * (cds + body)
        polar: SpeedPolar | None = x.get("polar")
        if polar is None:
            return {"cds_dedicated_m2": cds, "drag_n": parasitic, "v_min_m_s": 0.0}
        v_eq = v * np.sqrt(rho / polar.rho)
        airframe = np.interp(v_eq, polar.v_m_s, polar.drag_n, left=np.nan, right=np.nan)
        return {
            "cds_dedicated_m2": cds,
            "drag_n": airframe + parasitic,
            "v_min_m_s": float(polar.v_m_s[0] * np.sqrt(polar.rho / rho)),
        }
