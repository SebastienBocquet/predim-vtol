"""Cruise aerodynamics of a wing-borne aircraft, iso-model with PredimRC (INC2-005).

The curve is the PredimRC level-flight polar (power column of Calculs1) plus the tool's
drag sources at the PredimRC density (the flight altitude and temperature are written into
PredimRC). The power at the target speeds V₁ (minimum power) and V₂ (maximum L/D) is read
in the PredimRC "Performances à vitesse imposée" blocks at the trimmed C_z = 2mg/(ρSV²),
so that it is PredimRC's own value at that speed; the gap to the interpolated curve is
reported (coarse polar grid).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.mission.solver import _parabolic_min

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.model import AircraftModel

ISO_TOLERANCE = 1e-6
"""Relative tolerance of the iso-model checks."""


@dataclass
class CruiseCurve:
    """Aerodynamic power versus speed at the PredimRC density."""

    v_m_s: np.ndarray
    drag_predimrc_n: np.ndarray
    power_predimrc_w: np.ndarray
    """PredimRC power column (W)."""
    drag_sources_n: np.ndarray
    """Tool drag sources ½ρV²ΣCdS (N)."""
    drag_factor: float
    rho: float
    mass_kg: float
    cds_sources_m2: float
    wing_area_m2: float

    @property
    def drag_total_n(self) -> np.ndarray:
        return self.drag_factor * (self.drag_predimrc_n + self.drag_sources_n)

    @property
    def power_total_w(self) -> np.ndarray:
        return self.drag_total_n * self.v_m_s

    def speeds(self) -> tuple[float, float]:
        """(V minimum power, V maximum L/D) of the total curve, parabolic refinement (m/s)."""
        v = self.v_m_s
        i_p, i_d = int(np.argmin(self.power_total_w)), int(np.argmin(self.drag_total_n))
        return _parabolic_min(v, self.power_total_w, i_p), _parabolic_min(
            v, self.drag_total_n, i_d
        )


@dataclass
class TargetPoint:
    """Aerodynamics at one target speed, from the PredimRC imposed-speed block."""

    index: int
    v_m_s: float
    cz_trim: float
    drag_predimrc_n: float
    power_predimrc_w: float
    drag_sources_n: float
    drag_factor: float
    curve_power_w: float
    """Total power interpolated on the curve at the same speed (W), for information."""

    @property
    def drag_n(self) -> float:
        return self.drag_factor * (self.drag_predimrc_n + self.drag_sources_n)

    @property
    def aero_power_w(self) -> float:
        return self.drag_n * self.v_m_s

    @property
    def curve_gap(self) -> float:
        """Relative gap of the interpolated curve to the PredimRC block value."""
        return self.curve_power_w / self.aero_power_w - 1.0


@dataclass
class IsoCheck:
    """Iso-model checks against the PredimRC sheet."""

    curve_max_rel_dev: float
    """Tool level-flight power (m·g·|Vz|) versus the PredimRC power column."""
    imposed_max_rel_dev: float
    """Power used at the target speeds versus the PredimRC block at the trimmed C_z."""
    curve_gaps: list[float] = field(default_factory=list)
    """Interpolated curve versus block at each target speed (information)."""
    imposed_speeds_kmh: list[float] = field(default_factory=list)
    """Vx 1, Vx 2 read back from the PredimRC blocks (km/h)."""

    @property
    def available(self) -> bool:
        """Both checks could be made (PredimRC blocks read)."""
        return bool(
            np.isfinite(self.curve_max_rel_dev)
            and np.isfinite(self.imposed_max_rel_dev)
        )

    @property
    def passed(self) -> bool:
        return (
            self.curve_max_rel_dev <= ISO_TOLERANCE
            and self.imposed_max_rel_dev <= ISO_TOLERANCE
        )


def cruise_curve(
    aircraft: AircraftModel, vx_kmh: tuple[float, float] | None = None
) -> CruiseCurve:
    """The cruise curve of a wing-borne aircraft at its total mass."""
    r = aircraft.aero.results(aircraft.total_mass_kg, vx_kmh)
    cds = sum(aircraft.drag_model.cds(s) for s in aircraft.drag_sources())
    v = np.asarray(r.vx, dtype=float)
    return CruiseCurve(
        v_m_s=v,
        drag_predimrc_n=np.asarray(r.drag_n, dtype=float),
        power_predimrc_w=np.asarray(
            r.power_predimrc_w if len(r.power_predimrc_w) else r.power_required_w,
            dtype=float,
        ),
        drag_sources_n=0.5 * r.rho * v**2 * cds,
        drag_factor=aircraft.project.mission.drag_factor,
        rho=r.rho,
        mass_kg=aircraft.total_mass_kg,
        cds_sources_m2=cds,
        wing_area_m2=r.total_surface / 100.0,
    )


def target_points(
    aircraft: AircraftModel, speeds_m_s: tuple[float, float] | None = None
) -> tuple[CruiseCurve, list[TargetPoint], IsoCheck]:
    """Curve, target points and iso checks; default speeds: minimum power and maximum L/D.

    Two PredimRC evaluations when the speeds are not given (the second writes Vx 1, Vx 2).
    """
    if speeds_m_s is None:
        speeds_m_s = cruise_curve(aircraft).speeds()
    # The speeds written into PredimRC are rounded to 0.01 km/h: compute at those exact speeds.
    vx_kmh = (round(3.6 * speeds_m_s[0], 2), round(3.6 * speeds_m_s[1], 2))
    speeds_m_s = (vx_kmh[0] / 3.6, vx_kmh[1] / 3.6)
    results = aircraft.aero.results(aircraft.total_mass_kg, vx_kmh)
    curve = cruise_curve(aircraft, vx_kmh)
    points, devs, gaps, read_back = [], [], [], []
    for k, v in ((1, speeds_m_s[0]), (2, speeds_m_s[1])):
        block = results.imposed.get(k)
        cz = 2.0 * curve.mass_kg * GRAVITY / (curve.rho * curve.wing_area_m2 * v**2)
        if block is None:
            drag_p = float(np.interp(v, curve.v_m_s, curve.drag_predimrc_n))
            power_p, read_back_v = drag_p * v, float("nan")
        else:
            drag_p, power_p = block.at_cz(cz)
            read_back_v = 3.6 * block.vx_m_s
        point = TargetPoint(
            k,
            v,
            cz,
            drag_p,
            power_p,
            0.5 * curve.rho * v**2 * curve.cds_sources_m2,
            curve.drag_factor,
            float(np.interp(v, curve.v_m_s, curve.power_total_w)),
        )
        points.append(point)
        if block is not None:
            devs.extend((
                abs(point.drag_predimrc_n * v / power_p - 1.0)
                if power_p > 0
                else np.inf,
                abs(read_back_v / (3.6 * v) - 1.0),
            ))
        gaps.append(point.curve_gap)
        read_back.append(read_back_v)
    m_g_vz = np.asarray(results.power_required_w, dtype=float)
    col = np.asarray(results.power_predimrc_w, dtype=float)
    curve_dev = (
        float(np.nanmax(np.abs(m_g_vz / col - 1.0))) if len(col) else float("nan")
    )
    iso = IsoCheck(
        curve_dev, float(max(devs)) if devs else float("nan"), gaps, read_back
    )
    return curve, points, iso
