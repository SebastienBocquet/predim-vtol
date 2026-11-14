"""Simple aerodynamic model of the wing-borne aircraft, without Excel (MIC-AERO-SIMPLE).

Textbook methods on the PredimRC geometry description (same inputs and outputs as the
PredimRC backend):

- planform: exact integrals over the trapezoidal panels (area, span, mean aerodynamic
  chord and its position);
- lift slopes: Helmbold / DATCOM; V-tail pitch effectiveness cos²Γ (Purser-Campbell);
- downwash at the tail: DATCOM (aspect ratio, taper and tail height factors);
- induced drag: Oswald factor of Nita & Scholz (taper, sweep, fuselage);
- profile drag: NeuralFoil section polars versus lift coefficient and Reynolds number
  (:mod:`predim_vtol.aero.airfoils`);
- fuselage: turbulent skin friction × Hoerner body form factor, tail boom, afterbody;
- neutral point: wing and tail aerodynamic centres, fuselage Munk moment with the wing
  upwash (Multhopp);
- polar: pitch equilibrium at every point (stabiliser lift from the moment balance about
  the centre of gravity placed at the requested static margin).

Lengths in mm, as the inputs; SI inside the drag computations.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from predim_vtol.aero.airfoils import Airfoil
from predim_vtol.aero.airfoils import airfoil
from predim_vtol.aero.base import AeroResults
from predim_vtol.aero.base import FuselageGeometry
from predim_vtol.aero.base import G
from predim_vtol.aero.base import ImposedSpeed
from predim_vtol.aero.base import Settings
from predim_vtol.aero.base import StabGeometry
from predim_vtol.aero.base import WingGeometry

if TYPE_CHECKING:
    from typing_extensions import Self

MM = 1e-3

DEFAULT_ALTITUDE_M = 0.0
DEFAULT_TEMPERATURE_C = 15.0

STAB_PROFILES = {
    "- no foil -": "NACA0006",
    "Planche": "NACA0006",
    "Biconvexe fin": "NACA0006",
    "Biconvexe épais": "NACA0010",
    "Asymétrique fin": "NACA2406",
    "Asymétrique épais": "NACA2410",
}
"""Stabiliser profile labels (as in PredimRC) -> stabiliser airfoil."""

FUSELAGE_SHAPES = {
    # label: (wetted area / (perimeter x length), form factor multiplier, box section)
    "Profilée": (0.75, 1.0, False),
    "Caisse arrondie": (0.85, 1.35, False),
    "Caisse": (0.9, 1.7, True),
}
"""Fuselage shape labels -> pod wetted area factor, form factor multiplier, box section."""

BEAMS = {
    # label: (boom diameter / pod equivalent diameter, afterbody Cd on the pod frontal area,
    #         total span width / fuselage width)
    "Fine": (0.12, 0.0, 1.0),
    "Normale": (0.2, 0.04, 1.0),
    "Epaisse": (0.3, 0.08, 1.0),
    "Jet (entrées air latérales)": (0.45, 0.12, 1.9),
}
"""Tail beam labels -> boom diameter ratio, afterbody drag coefficient, width of the
fuselage in the total span (lateral air intakes of a jet), as in PredimRC."""

WING_POSITIONS = ("parasol", "haute", "médiane", "basse")
"""Wing position labels: no effect in this model."""

INCIDENCES = ("aile", "stab")
"""Linked incidence labels: no effect in this model (fuselage aligned at the trim C_z)."""

ACCESSORY_CD = {"Profilé": 0.15, "Mixte": 0.5, "Non profilé": 1.1}
"""Accessory shape labels -> drag coefficient on the accessory frontal area."""

TAIL_DYNAMIC_PRESSURE_RATIO = 0.9
"""η: dynamic pressure at the tail over the free stream one."""

WING_CL_MAX_FACTOR = 0.9
"""Wing maximum lift coefficient over the section one (straight wing). The section profile
drag is read at ``C_L / WING_CL_MAX_FACTOR``, the lift coefficient of the most loaded
sections, so that the sections reach their maximum lift at the wing maximum lift."""

TAIL_EFFICIENCY = 0.85
"""Factor on the tail lift slope in the neutral point, calibrated on PredimRC (see the
MIC card): thin stabilisers at low Reynolds numbers, fuselage and boom interference."""

FUSELAGE_MOMENT_FACTOR = 6.0
"""Factor on the Munk-Multhopp fuselage moment, calibrated on PredimRC (see the MIC card).
With 1, the neutral point is about 10 % of the MAC further aft: the calibrated value keeps
the centre of gravity recommendation on the safe (forward) side."""

POLAR_POINTS = 60
POLAR_CL_MIN = 0.02
"""Lowest wing lift coefficient of the polar (highest speed)."""


class SimpleAeroError(ValueError):
    """Invalid inputs of the simple aerodynamic model."""


def _label(table: dict | tuple, value: str, what: str):
    if value not in table:
        msg = f"{what}: '{value}' is not a valid label. Allowed: {list(table)}"
        raise SimpleAeroError(msg)
    return table[value] if isinstance(table, dict) else value


def _opening_dihedral_rad(opening: str) -> float:
    """V-tail panel dihedral Γ from the opening label ('--- / 180' = flat, '120', '-120')."""
    text = str(opening).split("/")[-1].strip()
    try:
        angle = abs(float(text))
    except ValueError as error:
        msg = f"stab.opening: '{opening}' is not an angle label such as '120' or '--- / 180'."
        raise SimpleAeroError(msg) from error
    if not 0.0 < angle <= 180.0:
        msg = f"stab.opening: the opening must lie in ]0, 180] degrees, got {opening}."
        raise SimpleAeroError(msg)
    return math.radians((180.0 - angle) / 2.0)


# ---------------------------------------------------------------------------
# Planform
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Planform:
    """A symmetric surface made of trapezoidal panels (mm)."""

    area: float
    """Area of both halves (mm²)."""
    span: float
    """Span of the panels, both halves (mm)."""
    mac: float
    """Mean aerodynamic chord (mm)."""
    x_le_mac: float
    """Leading edge of the mean aerodynamic chord, from the root leading edge (mm)."""
    root_chord: float
    taper: float
    """Equivalent taper ratio (trapezoid of same area, span and root chord)."""
    tan_sweep_c4: float
    tan_sweep_c2: float

    @property
    def aspect_ratio(self) -> float:
        return self.span**2 / self.area

    @property
    def x_ac(self) -> float:
        """Aerodynamic centre: quarter of the mean aerodynamic chord (mm)."""
        return self.x_le_mac + 0.25 * self.mac


def planform(
    root_chord: float,
    tip_chord: list[float | None],
    length: list[float | None],
    le_offset: list[float | None],
) -> Planform:
    """Planform of panels given as in PredimRC (tip chords, lengths, absolute LE offsets)."""
    panels = [
        (c, span_l, x)
        for c, span_l, x in zip(tip_chord, length, le_offset, strict=False)
        if c is not None and span_l is not None
    ]
    if not panels:
        msg = "A surface needs at least one panel."
        raise SimpleAeroError(msg)
    half_area = int_c2 = int_cx = 0.0
    sweep = {0.25: 0.0, 0.5: 0.0}
    c_a, x_a = float(root_chord), 0.0
    for c_b, span_l, x_b in panels:
        c_b, span_l, x_b = float(c_b), float(span_l), float(x_b or 0.0)
        if span_l <= 0.0 or c_b < 0.0:
            msg = f"Invalid panel: length {span_l} mm, tip chord {c_b} mm."
            raise SimpleAeroError(msg)
        area = span_l * (c_a + c_b) / 2.0
        half_area += area
        int_c2 += span_l * (c_a**2 + c_a * c_b + c_b**2) / 3.0
        dc, dx = c_b - c_a, x_b - x_a
        int_cx += span_l * (c_a * x_a + (c_a * dx + x_a * dc) / 2.0 + dc * dx / 3.0)
        for f in sweep:
            sweep[f] += area * (dx + f * dc) / span_l
        c_a, x_a = c_b, x_b
    half_span = sum(float(span_l) for _, span_l, _ in panels)
    mean_chord = half_area / half_span
    taper = min(max((2.0 * mean_chord - root_chord) / root_chord, 0.0), 2.0)
    mac = int_c2 / half_area
    x_le_mac = int_cx / half_area
    return Planform(
        area=2.0 * half_area,
        span=2.0 * half_span,
        mac=mac,
        x_le_mac=x_le_mac,
        root_chord=float(root_chord),
        taper=taper,
        tan_sweep_c4=sweep[0.25] / half_area,
        tan_sweep_c2=sweep[0.5] / half_area,
    )


def lift_slope(aspect_ratio: float, tan_sweep_c2: float, section_slope: float) -> float:
    """Lift slope per rad (Helmbold / DATCOM, incompressible)."""
    kappa = section_slope / (2.0 * math.pi)
    return (
        2.0
        * math.pi
        * aspect_ratio
        / (2.0 + math.sqrt(aspect_ratio**2 / kappa**2 * (1.0 + tan_sweep_c2**2) + 4.0))
    )


def oswald(aspect_ratio: float, taper: float, sweep_c4_deg: float) -> float:
    """Theoretical span efficiency (Nita & Scholz 2012), without the fuselage factor."""
    d_taper = -0.357 + 0.45 * math.exp(0.0375 * sweep_c4_deg)
    lam = taper - d_taper
    f = 0.0524 * lam**4 - 0.15 * lam**3 + 0.1659 * lam**2 - 0.0706 * lam + 0.0119
    return 1.0 / (1.0 + max(f, 0.0) * aspect_ratio)


def downwash_gradient(wing: Planform, tail_arm: float, tail_height: float) -> float:
    """dε/dα at the tail (DATCOM, incompressible)."""
    ar = wing.aspect_ratio
    k_a = 1.0 / ar - 1.0 / (1.0 + ar**1.7)
    k_lambda = (10.0 - 3.0 * wing.taper) / 7.0
    k_h = (1.0 - abs(tail_height) / wing.span) / (2.0 * tail_arm / wing.span) ** (1 / 3)
    cos_sweep = 1.0 / math.sqrt(1.0 + wing.tan_sweep_c4**2)
    return 4.44 * (k_a * k_lambda * max(k_h, 0.0) * math.sqrt(cos_sweep)) ** 1.19


# ---------------------------------------------------------------------------
# Atmosphere and skin friction
# ---------------------------------------------------------------------------


def air(altitude_m: float, temperature_c: float) -> tuple[float, float]:
    """Density (kg/m³) and dynamic viscosity (Pa·s): ISA pressure, given temperature."""
    pressure = 101325.0 * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588
    t = temperature_c + 273.15
    return pressure / (287.05 * t), 1.458e-6 * t**1.5 / (t + 110.4)


def turbulent_cf(reynolds: np.ndarray) -> np.ndarray:
    """Turbulent flat-plate skin friction (Schlichting)."""
    return 0.455 / np.log10(np.maximum(reynolds, 1e4)) ** 2.58


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class _Aircraft:
    """The geometry derived once per evaluation (mm, rad)."""

    wing: Planform
    stab: Planform
    wing_airfoil: Airfoil
    stab_airfoil: Airfoil
    a_w: float
    e_w: float
    e_w_theoretical: float
    a_t: float
    """Stabiliser pitch lift slope per rad of its angle of attack, on its own area."""
    e_t: float
    cos_gamma: float
    stab_span: float
    x_ac_t: float
    deps: float
    m_alpha_fus: float
    """Fuselage pitching moment derivative over the dynamic pressure (mm³ per rad)."""
    x_np: float
    fus_cds_m2: object
    """Callable: fuselage drag area (m²) at a speed (m/s)."""


class SimpleAeroBackend:
    """Aerodynamic backend computing the polar with :mod:`predim_vtol.aero.simple`.

    Args:
        profile: The wing airfoil (name of :func:`predim_vtol.aero.airfoils.airfoils`).
    """

    name = "simple"

    def __init__(self, profile: str = "SD7003") -> None:
        self.profile = profile
        self.wing_airfoil = airfoil(profile, "wing")
        self.last_eval_seconds = float("nan")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Nothing to release."""

    def is_alive(self) -> bool:
        return True

    # --- geometry --------------------------------------------------------------

    def _aircraft(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        rho: float,
        mu: float,
    ) -> _Aircraft:
        w = planform(wing.root_chord, wing.tip_chord, wing.length, wing.le_offset)
        t = planform(stab.root_chord, stab.tip_chord, stab.length, stab.le_offset)
        stab_airfoil = airfoil(
            _label(STAB_PROFILES, stab.profile, "stab.profile"), "stab"
        )
        gamma = _opening_dihedral_rad(stab.opening)
        cos_gamma = math.cos(gamma)
        stab_span = t.span + stab.lateral_gap
        stab_ar = stab_span**2 / t.area
        a_w = lift_slope(w.aspect_ratio, w.tan_sweep_c2, self.wing_airfoil.cl_alpha)
        sweep_deg = math.degrees(math.atan(w.tan_sweep_c4))
        e_th = oswald(w.aspect_ratio, w.taper, sweep_deg)
        e_w = e_th * (1.0 - 2.0 * (fus.width / (w.span + fus.width)) ** 2)
        a_t = lift_slope(stab_ar, t.tan_sweep_c2, stab_airfoil.cl_alpha) * cos_gamma**2
        e_t = oswald(stab_ar, t.taper, math.degrees(math.atan(t.tan_sweep_c4)))
        x_ac_t = stab.lever + t.x_ac
        deps = min(
            max(downwash_gradient(w, x_ac_t - w.x_ac, stab.stab_height), 0.0), 0.9
        )
        m_alpha = FUSELAGE_MOMENT_FACTOR * self._fuselage_moment(
            w, fus, a_w, deps, x_ac_t
        )
        lift_t = (
            TAIL_EFFICIENCY * TAIL_DYNAMIC_PRESSURE_RATIO * a_t * t.area * (1.0 - deps)
        )
        x_np = (a_w * w.area * w.x_ac + lift_t * x_ac_t - m_alpha) / (
            a_w * w.area + lift_t
        )
        fus_cds = self._fuselage_drag(wing.root_chord, fus, rho, mu)
        return _Aircraft(
            wing=w,
            stab=t,
            wing_airfoil=self.wing_airfoil,
            stab_airfoil=stab_airfoil,
            a_w=a_w,
            e_w=e_w,
            e_w_theoretical=e_th,
            a_t=a_t,
            e_t=e_t,
            cos_gamma=cos_gamma,
            stab_span=stab_span,
            x_ac_t=x_ac_t,
            deps=deps,
            m_alpha_fus=m_alpha,
            x_np=x_np,
            fus_cds_m2=fus_cds,
        )

    @staticmethod
    def _pod(fus: FuselageGeometry, root_chord: float) -> tuple[float, float, float]:
        """Equivalent diameter, pod length (to one diameter behind the wing) and boom length."""
        d_eq = math.sqrt(fus.width * fus.height)
        pod = min(fus.length, fus.nose_lever + root_chord + d_eq)
        return d_eq, pod, max(fus.length - pod, 0.0)

    def _fuselage_moment(
        self,
        w: Planform,
        fus: FuselageGeometry,
        a_w: float,
        deps: float,
        x_ac_t: float,
    ) -> float:
        """Munk moment derivative of the fuselage with the wing upwash (Multhopp), mm³/rad.

        Coordinates from the wing root leading edge; the nose is at ``-nose_lever``.
        """
        d_eq, pod, _ = self._pod(fus, w.root_chord)
        beam_ratio, _, _ = _label(BEAMS, fus.beam, "fuselage.beam")
        _, _, box = _label(FUSELAGE_SHAPES, fus.shape, "fuselage.shape")
        nose = (0.5 if box else 1.5) * d_eq
        x = np.linspace(-fus.nose_lever, fus.length - fus.nose_lever, 400)
        dx = x[1] - x[0]
        from_nose = x + fus.nose_lever
        width = fus.width * np.sqrt(np.clip(from_nose / nose, 0.0, 1.0))
        x_te = w.root_chord
        pod_end = pod - fus.nose_lever
        aft = x > x_te
        taper = np.clip((x - x_te) / max(pod_end - x_te, 1e-9), 0.0, 1.0)
        width = np.where(
            aft, fus.width + (beam_ratio * d_eq - fus.width) * taper, width
        )
        ahead = x < 0.0
        r = -x + 0.25 * w.root_chord
        factor = np.where(
            ahead,
            1.0 + w.root_chord * a_w / (4.0 * math.pi * np.maximum(r, 1e-9)),
            0.0,
        )
        tail_arm = max(x_ac_t - x_te, 1e-9)
        factor = np.where(
            aft, np.clip((x - x_te) / tail_arm, 0.0, 1.0) * (1.0 - deps), factor
        )
        return float(math.pi / 2.0 * np.sum(width**2 * factor) * dx)

    def _fuselage_drag(
        self, root_chord: float, fus: FuselageGeometry, rho: float, mu: float
    ):
        """Fuselage (pod, boom, afterbody, accessory) drag area as a function of speed."""
        wet_factor, form_mult, box = _label(
            FUSELAGE_SHAPES, fus.shape, "fuselage.shape"
        )
        beam_ratio, cd_afterbody, _ = _label(BEAMS, fus.beam, "fuselage.beam")
        _label(WING_POSITIONS, fus.wing_pos, "fuselage.wing_pos")
        _label(INCIDENCES, fus.incidence, "fuselage.incidence")
        cd_accessory = _label(
            ACCESSORY_CD, fus.accessory_shape, "fuselage.accessory_shape"
        )
        d_eq, pod, boom = (v * MM for v in self._pod(fus, root_chord))
        w, h = fus.width * MM, fus.height * MM
        perimeter = 2.0 * (w + h) if box else math.pi * math.sqrt((w * w + h * h) / 2.0)
        fineness = pod / d_eq
        form = form_mult * (1.0 + 1.5 / fineness**1.5 + 7.0 / fineness**3)
        pod_wet = wet_factor * perimeter * pod
        d_boom = beam_ratio * d_eq
        boom_wet = math.pi * d_boom * boom
        frontal = math.pi * w * h / 4.0
        fixed = cd_afterbody * frontal + cd_accessory * fus.accessory_surface * 1e-2

        def cds(v: np.ndarray) -> np.ndarray:
            v = np.asarray(v, dtype=float)
            pod_cf = turbulent_cf(rho * v * pod / mu)
            boom_cf = turbulent_cf(rho * v * max(boom, 1e-6) / mu)
            return pod_cf * form * pod_wet + boom_cf * boom_wet + fixed

        return cds

    # --- evaluation ------------------------------------------------------------

    def evaluate(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        """Evaluate the aerodynamics of a geometry (same contract as PredimRC)."""
        start = time.perf_counter()
        altitude = (
            DEFAULT_ALTITUDE_M if settings.altitude_m is None else settings.altitude_m
        )
        temperature = (
            DEFAULT_TEMPERATURE_C
            if settings.temperature_c is None
            else settings.temperature_c
        )
        rho, mu = air(altitude, temperature)
        ac = self._aircraft(wing, stab, fus, rho, mu)
        w, t = ac.wing, ac.stab
        mass = settings.mass * 1e-3
        weight = mass * G
        s_m2 = w.area * MM**2
        x_cg = ac.x_np - settings.static_margin / 100.0 * w.mac

        # Wing maximum lift: section maximum at the stall Reynolds number (fixed point).
        cos_sweep = 1.0 / math.sqrt(1.0 + w.tan_sweep_c4**2)
        cl_max = WING_CL_MAX_FACTOR * cos_sweep * ac.wing_airfoil.cl_max(2e5)
        for _ in range(4):
            v_stall = math.sqrt(2.0 * weight / (rho * s_m2 * cl_max))
            cl_max = (
                WING_CL_MAX_FACTOR
                * cos_sweep
                * ac.wing_airfoil.cl_max(rho * v_stall * w.mac * MM / mu)
            )
        cl_w = np.geomspace(cl_max, POLAR_CL_MIN, POLAR_POINTS)
        cl_t, cl_tot, _alpha_w = self._trim(ac, cl_w, x_cg, settings.cz_reg)
        ok = cl_tot > 0.0
        cl_w, cl_t, cl_tot = cl_w[ok], cl_t[ok], cl_tot[ok]
        v = np.sqrt(2.0 * weight / (rho * s_m2 * cl_tot))
        cd = self._drag(ac, cl_w, cl_t, v, rho, mu, s_m2)
        valid = np.isfinite(cd)
        cl_w, cl_t, cl_tot, v, cd = (a[valid] for a in (cl_w, cl_t, cl_tot, v, cd))
        if not len(v):
            msg = "The simple model found no trimmed polar point (stabiliser stalled)."
            raise SimpleAeroError(msg)
        drag = 0.5 * rho * v**2 * s_m2 * cd
        power = drag * v
        finesse = cl_tot / cd
        i_trim = self._trim(ac, np.array([settings.cz_reg]), x_cg, settings.cz_reg)
        stab_incidence, dihedral = self._incidences(ac, settings.cz_reg, i_trim)
        imposed = {
            k: self._imposed(ac, vk / 3.6, cl_w, x_cg, settings.cz_reg, rho, mu, s_m2)
            for k, vk in ((1, settings.vx1_kmh), (2, settings.vx2_kmh))
            if vk is not None
        }
        result = AeroResults(
            cz=cl_w,
            cx=cd,
            vx=v,
            sink_rate=-power / weight,
            finesse_vx=finesse,
            drag_n=drag,
            power_required_w=power,
            v_min=float(v[0]),
            v_min_power=float(v[np.argmin(power)]),
            v_max_finesse=float(v[np.argmax(finesse)]),
            mass_kg=mass,
            cg=100.0 * (x_cg - w.x_le_mac) / w.mac,
            foyer=100.0 * (ac.x_np - w.x_le_mac) / w.mac,
            total_surface=w.area / 1e4,
            mean_chord=w.mac,
            span_aero=w.span,
            span_total=w.span + fus.width * BEAMS[fus.beam][2],
            aspect_ratio=w.aspect_ratio,
            aspect_ratio_el=w.aspect_ratio * ac.e_w_theoretical,
            wing_loading=settings.mass / (w.area / 1e4),
            rho=rho,
            power_predimrc_w=power.copy(),
            imposed=imposed,
            altitude_m=altitude,
            temperature_c=temperature,
            cg_mm=x_cg,
            neutral_point_mm=ac.x_np,
            static_margin=settings.static_margin,
            tail_volume=t.area
            * ac.cos_gamma**2
            * (ac.x_ac_t - w.x_ac)
            / (w.area * w.mac),
            stab_incidence_deg=stab_incidence,
            longitudinal_dihedral_deg=dihedral,
        )
        self.last_eval_seconds = time.perf_counter() - start
        return result

    run = evaluate

    def _trim(
        self, ac: _Aircraft, cl_w: np.ndarray, x_cg: float, cz_reg: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Stabiliser lift coefficient (on its area), total lift coefficient (on the wing
        area) and wing angle of attack (rad) in pitch equilibrium about the CG.

        The fuselage axis is aligned with the flow at the trim lift coefficient ``cz_reg``:
        the fuselage Munk moment is proportional to the angle of attack change from there.
        """
        w, t = ac.wing, ac.stab
        alpha0 = math.radians(ac.wing_airfoil.alpha0_deg)
        alpha_w = alpha0 + cl_w / ac.a_w
        alpha_fus = (cl_w - cz_reg) / ac.a_w
        eta = TAIL_DYNAMIC_PRESSURE_RATIO
        moment = (
            cl_w * w.area * (x_cg - w.x_ac)
            + ac.wing_airfoil.cm0 * w.area * w.mac
            + ac.m_alpha_fus * alpha_fus
            + eta * ac.stab_airfoil.cm0 * t.area * t.mac
        )
        cl_t = moment / (eta * t.area * (ac.x_ac_t - x_cg))
        cl_tot = cl_w + eta * t.area / w.area * cl_t
        return cl_t, cl_tot, alpha_w

    def _drag(
        self,
        ac: _Aircraft,
        cl_w: np.ndarray,
        cl_t: np.ndarray,
        v: np.ndarray,
        rho: float,
        mu: float,
        s_m2: float,
    ) -> np.ndarray:
        """Total drag coefficient on the wing area; NaN where the stabiliser stalls."""
        w, t = ac.wing, ac.stab
        re_w = rho * v * w.mac * MM / mu
        re_t = rho * v * t.mac * MM / mu
        cd_w = ac.wing_airfoil.drag(cl_w / WING_CL_MAX_FACTOR, re_w) + cl_w**2 / (
            math.pi * w.aspect_ratio * ac.e_w
        )
        # Panel normal coefficient of a V-tail: vertical lift / cos Γ.
        cn = cl_t / ac.cos_gamma
        stab_ar = ac.stab_span**2 / t.area
        cd_t = ac.stab_airfoil.drag(cn, re_t) + cn**2 / (math.pi * stab_ar * ac.e_t)
        stalled = np.abs(cn) > np.array([ac.stab_airfoil.cl_max(r) for r in re_t])
        cd = (
            cd_w
            + TAIL_DYNAMIC_PRESSURE_RATIO * cd_t * t.area / w.area
            + ac.fus_cds_m2(v) / s_m2
        )
        return np.where(stalled, np.nan, cd)

    def _imposed(
        self,
        ac: _Aircraft,
        v: float,
        cl_w: np.ndarray,
        x_cg: float,
        cz_reg: float,
        rho: float,
        mu: float,
        s_m2: float,
    ) -> ImposedSpeed:
        """Drag and power at one speed versus the wing lift coefficient."""
        cl_t, _, _ = self._trim(ac, cl_w, x_cg, cz_reg)
        speed = np.full_like(cl_w, v)
        cd = self._drag(ac, cl_w, cl_t, speed, rho, mu, s_m2)
        ok = np.isfinite(cd)
        drag = 0.5 * rho * v**2 * s_m2 * cd[ok]
        return ImposedSpeed(float(v), cl_w[ok], drag, drag * v)

    @staticmethod
    def _incidences(ac: _Aircraft, cz_reg: float, trim) -> tuple[float, float]:
        """Stabiliser incidence on the fuselage axis (aligned with the flow at the trim
        C_z) and longitudinal dihedral (wing minus stabiliser incidence), degrees."""
        cl_t, _, alpha_w = trim
        alpha0_w = math.radians(ac.wing_airfoil.alpha0_deg)
        eps = ac.deps * (float(alpha_w[0]) - alpha0_w)
        alpha_t = math.radians(ac.stab_airfoil.alpha0_deg) + float(cl_t[0]) / ac.a_t
        stab_incidence = alpha_t + eps
        return math.degrees(stab_incidence), math.degrees(
            float(alpha_w[0]) - stab_incidence
        )
