"""Adapter between the project and the PredimRC backend (external model, no MIC card)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from predimrc_wrapper.aircraft.drag import SpeedPolar
from predimrc_wrapper.predimrc_wrapper import FuselageGeometry
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import StabGeometry
from predimrc_wrapper.predimrc_wrapper import WingGeometry

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import AeroSpec
    from predimrc_wrapper.aircraft.project import EnvironmentSpec
    from predimrc_wrapper.predimrc_wrapper import AeroBackend
    from predimrc_wrapper.predimrc_wrapper import AeroResults


def to_predimrc(
    aero: AeroSpec,
    mass_kg: float,
    environment: EnvironmentSpec | None = None,
    vx_kmh: tuple[float, float] | None = None,
) -> dict:
    """Convert the project aero block into PredimRC inputs.

    The accessory surface is always 0 (the tool's drag sources hold the parasitic drag,
    REQ-AERO-006); the flight altitude and temperature (ISA + offset) and the imposed speeds
    Vx 1 / Vx 2 are written when given.
    """
    w, s, f = aero.wing, aero.stab, aero.fuselage
    altitude = temperature = None
    if environment is not None:
        altitude = environment.altitude_m
        temperature = 15.0 - 0.0065 * environment.altitude_m + environment.delta_isa_k
    return {
        "wing": WingGeometry(
            w.root_chord_mm,
            list(w.tip_chord_mm),
            list(w.length_mm),
            list(w.le_offset_mm),
            list(w.twist_deg),
            list(w.dihedral_deg),
        ),
        "stab": StabGeometry(
            s.root_chord_mm,
            list(s.tip_chord_mm),
            list(s.length_mm),
            list(s.le_offset_mm),
            s.lever_mm,
            s.height_mm,
            s.profile,
            s.opening,
            s.lateral_gap_mm,
        ),
        "fus": FuselageGeometry(
            f.length_mm,
            f.width_mm,
            f.height_mm,
            f.nose_lever_mm,
            f.shape,
            f.beam,
            f.wing_pos,
            f.incidence,
            0.0,
            "Non profilé",
        ),
        "settings": Settings(
            mass=1000.0 * mass_kg,
            static_margin=aero.static_margin_pct,
            cz_reg=aero.cz_reg,
            altitude_m=altitude,
            temperature_c=temperature,
            vx1_kmh=None if vx_kmh is None else vx_kmh[0],
            vx2_kmh=None if vx_kmh is None else vx_kmh[1],
        ),
    }


class AeroModel:
    """Memoised PredimRC evaluations of one project geometry.

    Args:
        aero: The project aero block.
        backend: The PredimRC backend (injected).
    """

    def __init__(
        self,
        aero: AeroSpec,
        backend: AeroBackend,
        environment: EnvironmentSpec | None = None,
    ) -> None:
        self.aero = aero
        self.backend = backend
        self.environment = environment
        self._cache: dict[tuple, AeroResults] = {}

    def results(
        self, mass_kg: float, vx_kmh: tuple[float, float] | None = None
    ) -> AeroResults:
        """PredimRC results at a mass (and imposed speeds), memoised on geometry, environment,
        mass rounded to 1 g and imposed speeds rounded to 0.01 km/h."""
        vx = None if vx_kmh is None else (round(vx_kmh[0], 2), round(vx_kmh[1], 2))
        env = None if self.environment is None else self.environment.model_dump_json()
        key = (self.aero.model_dump_json(), env, round(1000.0 * mass_kg), vx)
        if key not in self._cache:
            self._cache[key] = self.backend.evaluate(
                **to_predimrc(self.aero, mass_kg, self.environment, vx)
            )
        return self._cache[key]

    def polar(self, mass_kg: float) -> SpeedPolar:
        """Clean-airframe speed polar at a mass."""
        r = self.results(mass_kg)
        return SpeedPolar(v_m_s=r.vx, drag_n=r.drag_n, rho=r.rho)
