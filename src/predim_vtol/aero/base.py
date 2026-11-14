"""Inputs and outputs shared by the aerodynamic backends (PredimRC units).

The geometry is described as in PredimRC (millimetres, up to 5 panels per surface, PredimRC
labels for the drop-down choices) so that a project gives the same inputs to both backends:
the PredimRC workbook (:mod:`predim_vtol.aero.predimrc`) and the simple model
(:mod:`predim_vtol.aero.simple`).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol

import numpy as np

G = 9.81
"""Gravity (m/s²), the value used by PredimRC."""

MAX_PANELS = 5
"""Panels per surface."""

WING_PANEL_FIELDS = ("tip_chord", "length", "le_offset", "twist", "dihedral")
STAB_PANEL_FIELDS = ("tip_chord", "length", "le_offset")


def _pad(values: list[float | None]) -> list[float | None]:
    """Pad a list of panel values to the 5 PredimRC panels with ``None``."""
    if len(values) > MAX_PANELS:
        msg = f"At most {MAX_PANELS} panels, got {len(values)}."
        raise ValueError(msg)
    return list(values) + [None] * (MAX_PANELS - len(values))


# ---------------------------------------------------------------------------
# Input dataclasses (PredimRC units)
# ---------------------------------------------------------------------------


@dataclass
class WingGeometry:
    """Wing geometry, up to 5 panels (PredimRC units)."""

    root_chord: float
    """Root chord (mm), cell C6."""

    tip_chord: list[float]
    """Tip chord of each panel (mm), C7:G7."""

    length: list[float]
    """Span length of each panel (mm), C8:G8."""

    le_offset: list[float]
    """Leading-edge offset of each panel tip, "Flèche /BA" (mm), C9:G9."""

    twist: list[float]
    """Twist of each panel (deg), C10:G10."""

    dihedral: list[float]
    """Dihedral of each panel (deg), C11:G11."""

    def __post_init__(self) -> None:
        for attr in WING_PANEL_FIELDS:
            setattr(self, attr, _pad(getattr(self, attr)))


@dataclass
class StabGeometry:
    """Horizontal stabiliser geometry (PredimRC units)."""

    root_chord: float
    """Root chord (mm), C15."""

    tip_chord: list[float]
    """Tip chord of each panel (mm), C16:G16."""

    length: list[float]
    """Length of each panel (mm), C17:G17."""

    le_offset: list[float]
    """Leading-edge offset of each panel tip (mm), C18:G18."""

    lever: float
    """Stabiliser lever (mm), C19."""

    stab_height: float
    """Stabiliser height (mm), E19."""

    profile: str
    """Stabiliser airfoil, PredimRC label (drop-down G19)."""

    opening: str
    """V-tail opening, PredimRC label such as "120" or "--- / 180" (drop-down C20)."""

    lateral_gap: float
    """Lateral gap (mm), E20."""

    def __post_init__(self) -> None:
        for attr in STAB_PANEL_FIELDS:
            setattr(self, attr, _pad(getattr(self, attr)))


@dataclass
class FuselageGeometry:
    """Fuselage geometry (PredimRC units)."""

    length: float
    """Length (mm), C24."""

    width: float
    """Width (mm), E24."""

    height: float
    """Height (mm), E25."""

    nose_lever: float
    """Nose lever (mm), C25."""

    shape: str
    """Shape, PredimRC label (drop-down G24)."""

    beam: str
    """Tail beam, PredimRC label (drop-down G25)."""

    wing_pos: str
    """Wing position, PredimRC label (drop-down C26)."""

    incidence: str
    """Linked incidence, PredimRC label (drop-down E26)."""

    accessory_surface: float
    """Accessory frontal area (dm²), F26."""

    accessory_shape: str
    """Accessory shape, PredimRC label (drop-down G26)."""


@dataclass
class Settings:
    """Global settings."""

    mass: float
    """Total mass (g), C33."""

    static_margin: float
    """Static margin (% of MAC), spinner N31."""

    cz_reg: float
    """Trim lift coefficient, multiple of 0.05 (spinner N32 = cz_reg · 20)."""

    altitude_m: float | None = None
    """Flight altitude (m), T29; not written when None."""

    temperature_c: float | None = None
    """Air temperature (°C), T30; not written when None."""

    vx1_kmh: float | None = None
    """Imposed speed Vx 1 (km/h), AB29; not written when None."""

    vx2_kmh: float | None = None
    """Imposed speed Vx 2 (km/h), AB30; not written when None."""


@dataclass
class ImposedSpeed:
    """PredimRC "Performances à vitesse imposée" block at one speed, versus the wing Cz."""

    vx_m_s: float
    cz_wing: np.ndarray
    drag_n: np.ndarray
    power_w: np.ndarray

    def at_cz(self, cz: float, cz_max: float | None = None) -> tuple[float, float]:
        """Drag (N) and power (W) at a wing Cz, NaN outside the usable nodes (no extrapolation).

        Parabola through the three nearest nodes (the induced drag varies as Cz²). The nodes
        above ``cz_max`` (the last Cz of the trimmed polar) are dropped: the block grid
        (0.15 in airfoil Cz) can keep one node in the stall drag rise, where the polar has
        already stopped, and interpolating towards it overestimates the power.
        """
        keep = np.ones(len(self.cz_wing), dtype=bool)
        if cz_max is not None:
            keep = self.cz_wing <= cz_max * (1.0 + 1e-9)
        order = np.argsort(self.cz_wing[keep])
        x = self.cz_wing[keep][order]
        drag, power = self.drag_n[keep][order], self.power_w[keep][order]
        if not len(x) or not x[0] <= cz <= x[-1]:
            return float("nan"), float("nan")
        if len(x) < 3:
            return float(np.interp(cz, x, drag)), float(np.interp(cz, x, power))
        i = min(max(int(np.argmin(np.abs(x - cz))) - 1, 0), len(x) - 3)
        w = _lagrange_weights(x[i : i + 3], cz)
        return float(w @ drag[i : i + 3]), float(w @ power[i : i + 3])


def _lagrange_weights(x: np.ndarray, x0: float) -> np.ndarray:
    """Weights of the quadratic through three nodes at x0."""
    return np.array([
        np.prod([(x0 - x[j]) / (x[i] - x[j]) for j in range(3) if j != i])
        for i in range(3)
    ])


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass
class AeroResults:
    """Aerodynamic results of a backend (PredimRC: mass 1, airfoil 1 block of Calculs1)."""

    cz: np.ndarray
    """Wing lift coefficient of each valid polar point."""

    cx: np.ndarray
    """Total drag coefficient."""

    vx: np.ndarray
    """Horizontal speed (m/s)."""

    sink_rate: np.ndarray
    """Vertical speed (m/s, negative when sinking)."""

    finesse_vx: np.ndarray
    """Lift-to-drag ratio."""

    drag_n: np.ndarray
    """Drag (N)."""

    power_required_w: np.ndarray
    """Power required for level flight (W)."""

    v_min: float
    """Lowest valid polar speed (m/s), stall side."""

    v_min_power: float
    """Speed of minimum required power (m/s)."""

    v_max_finesse: float
    """Speed of maximum lift-to-drag ratio (m/s)."""

    mass_kg: float
    """Mass used for the polar (kg)."""

    cg: float
    """Centre of gravity (% of MAC)."""

    foyer: float
    """Neutral point (% of MAC)."""

    total_surface: float
    """Wing area (dm²)."""

    mean_chord: float
    """Mean chord (mm)."""

    span_aero: float
    """Aerodynamic span (mm)."""

    span_total: float
    """Total span (mm)."""

    aspect_ratio: float
    """Aspect ratio."""

    aspect_ratio_el: float
    """Elliptic-equivalent aspect ratio."""

    wing_loading: float = field(default=float("nan"))
    """Wing loading (g/dm²)."""

    rho: float = field(default=float("nan"))
    """Air density used by PredimRC (kg/m³), Calculs1!B1."""

    power_predimrc_w: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """PredimRC's own level-flight power column P (W), Calculs1!AQ (same points as ``vx``)."""

    imposed: dict[int, ImposedSpeed] = field(default_factory=dict)
    """Imposed-speed blocks V1 and V2, when Vx 1 / Vx 2 were written."""

    altitude_m: float = field(default=float("nan"))
    """Altitude read back from PredimRC (m)."""

    temperature_c: float = field(default=float("nan"))
    """Temperature read back from PredimRC (°C)."""

    cg_mm: float = field(default=float("nan"))
    """CG giving the static margin entered (mm from the wing root leading edge), 3-Geometrie!D30."""

    neutral_point_mm: float = field(default=float("nan"))
    """Neutral point (mm from the wing root leading edge), 3-Geometrie!D31."""

    static_margin: float = field(default=float("nan"))
    """Static margin used by PredimRC (% of MAC), 3-Geometrie!D29."""

    tail_volume: float = field(default=float("nan"))
    """Tail volume coefficient, 3-Geometrie!L21 (NaN without a stabiliser)."""

    stab_incidence_deg: float = field(default=float("nan"))
    """Stabiliser incidence at the trim Cz, airfoil 1 (°), 3-Geometrie!J31."""

    longitudinal_dihedral_deg: float = field(default=float("nan"))
    """Longitudinal dihedral (angle between wing and stabiliser) at the trim Cz, airfoil 1 (°),
    3-Geometrie!J32."""

    @property
    def mac_mm(self) -> float:
        """Mean aerodynamic chord (mm), from the CG and neutral point in % of MAC and in mm."""
        d_pct = self.foyer - self.cg
        return (
            100.0 * (self.neutral_point_mm - self.cg_mm) / d_pct
            if d_pct
            else float("nan")
        )


def derive_drag(
    vx_kmh: np.ndarray, sink_rate: np.ndarray, mass_kg: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert the PredimRC speed polar into SI speed, drag and required power.

    Args:
        vx_kmh: The horizontal speeds (km/h).
        sink_rate: The vertical speeds (m/s).
        mass_kg: The mass (kg).

    Returns:
        The speeds (m/s), the drag (N) and the required power (W):
        ``D = m·g·|Vz| / V`` and ``P = D·V``.
    """
    vx = np.asarray(vx_kmh, dtype=float) / 3.6
    power = mass_kg * G * np.abs(np.asarray(sink_rate, dtype=float))
    return vx, power / vx, power


class AeroBackend(Protocol):
    """An aerodynamic backend for the wing-borne aircraft."""

    name: str
    """``simple`` or ``predimrc``."""

    def evaluate(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        """Evaluate the aerodynamics of a geometry."""

    def close(self) -> None:
        """Release the backend resources."""
