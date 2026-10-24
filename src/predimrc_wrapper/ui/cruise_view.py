"""Cruise tab with the PredimRC layout (REQ-AERO-008, REQ-AERO-011): results, palier and
imposed-speed curves, aerodynamic power versus speed with the target speeds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from predimrc_wrapper.core.units import GRAVITY

if TYPE_CHECKING:
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult

V_COLORS = {1: "#d62728", 2: "#2ca02c"}


def results_rows(r: TwoPhaseResult) -> list[dict]:
    """PredimRC result blocks (labels of the sheet)."""
    a = r.aero_results
    if a is None:
        return []
    return [
        {
            "block": "Aile",
            "quantity": "Surface totale (dm²)",
            "value": round(a.total_surface, 2),
        },
        {
            "block": "Aile",
            "quantity": "Corde moyenne (mm)",
            "value": round(a.mean_chord, 1),
        },
        {
            "block": "Aile",
            "quantity": "Envergure aéro (mm)",
            "value": round(a.span_aero),
        },
        {
            "block": "Aile",
            "quantity": "Envergure totale (mm)",
            "value": round(a.span_total),
        },
        {"block": "Aile", "quantity": "Allongement", "value": round(a.aspect_ratio, 2)},
        {
            "block": "Aile",
            "quantity": "Allongement ellip.",
            "value": round(a.aspect_ratio_el, 2),
        },
        {
            "block": "Réglages",
            "quantity": "Masses (g)",
            "value": round(1000 * a.mass_kg),
        },
        {
            "block": "Réglages",
            "quantity": "Charge (g/dm²)",
            "value": round(a.wing_loading, 1),
        },
        {"block": "Performances", "quantity": "Altitude (m)", "value": a.altitude_m},
        {
            "block": "Performances",
            "quantity": "Temp. (°C)",
            "value": round(a.temperature_c, 1),
        },
        {
            "block": "Performances",
            "quantity": "Densité air (kg/m³)",
            "value": round(a.rho, 4),
        },
    ]


STABILITY_DESCRIPTIONS = {
    "cg": "Centrage pour la marge statique désirée (% de corde moyenne)",
    "cg_mm": "Centrage pour la marge statique désirée : position sur la corde d'emplanture par "
    "rapport au bord d'attaque",
    "foyer": "Foyer (= centrage neutre) du modèle complet, tenant compte de l'influence du "
    "fuselage et du stabilisateur (% de corde moyenne)",
    "neutral_point_mm": "Foyer (= centrage neutre) du modèle complet : position sur la corde "
    "d'emplanture par rapport au bord d'attaque",
    "static_margin": "de 0% (modèle parfaitement neutre) à 10% (modèle très stable). Valable "
    "autant pour un modèle classique qu'une aile volante. Valeur usuelle : 3 à 5%",
    "tail_volume": "Valeurs courantes : de 0.3 : modèle de vitesse ou de perfo, à 1 : modèle de "
    "début ou de voltige/accro. Doit être d'autant plus important que le modèle est amené à "
    "voler aux grands angles",
    "stab_incidence_deg": "Incidence du stab par rapport à la ligne neutre du fuselage, pour le "
    "Cz de réglage. Tenant compte de la marge statique, du sillage de l'aile (sauf dans le cas "
    "d'une formule canard) et de l'effet du fuselage (via le calage aile / fuselage)",
    "longitudinal_dihedral_deg": "Angle entre l'aile et le stab",
}
"""PredimRC comments of the 3-Geometrie cells (B29-B31, C30, D30, I21, G31, G32)."""


def _value(x: float, digits: int) -> float | str:
    """A value rounded, "-" when PredimRC gives none (e.g. no stabiliser)."""
    return "-" if np.isnan(x) else round(x, digits)


def stability_rows(r: TwoPhaseResult) -> list[dict]:
    """PredimRC longitudinal stability outputs (3-Geometrie "Réglages") with their comments."""
    a = r.aero_results
    if a is None:
        return []
    rows = (
        ("Centrage (% corde moyenne)", "cg", 1),
        ("Centrage (mm)", "cg_mm", 1),
        ("Foyer (% corde moyenne)", "foyer", 1),
        ("Foyer (mm)", "neutral_point_mm", 1),
        ("Marge statique (%)", "static_margin", 1),
        ("Volume de stab", "tail_volume", 3),
        ("Calage stab (°)", "stab_incidence_deg", 2),
        ("Vé longi. (°)", "longitudinal_dihedral_deg", 2),
    )
    return [
        {
            "quantity": label,
            "value": _value(getattr(a, name), digits),
            "description": STABILITY_DESCRIPTIONS[name],
        }
        for label, name, digits in rows
    ]


def v_limit_kmh(r: TwoPhaseResult) -> float:
    """Upper speed shown on the cruise charts: 1.5 × V2 (km/h)."""
    return 1.5 * 3.6 * max(c.v_m_s for c in r.cruise)


def palier_figure(r: TwoPhaseResult) -> go.Figure:
    """ "Performances en palier (plané)": sink rate, L/D and C_z versus V_x (km/h)."""
    a = r.aero_results
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    vx = 3.6 * np.asarray(a.vx)
    keep = vx <= v_limit_kmh(r)
    fig.add_trace(
        go.Scatter(x=vx[keep], y=np.asarray(a.sink_rate)[keep], name="Vz (m/s)"), 1, 1
    )
    fig.add_trace(
        go.Scatter(
            x=vx[keep], y=np.asarray(a.finesse_vx)[keep], name="Finesse (Cz/Cx)"
        ),
        2,
        1,
    )
    fig.add_trace(
        go.Scatter(x=vx[keep], y=np.asarray(a.cz)[keep], name="Cz aile"), 3, 1
    )
    for c in r.cruise:
        fig.add_vline(
            x=3.6 * c.v_m_s, line={"color": V_COLORS[c.index], "dash": "dash"}
        )
    fig.update_yaxes(title_text="Vz (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="Cz / Cx", row=2, col=1)
    fig.update_yaxes(title_text="Cz", row=3, col=1)
    fig.update_xaxes(title_text="Vx (km/h)", row=3, col=1)
    fig.update_layout(
        title="Performances en palier (plané)",
        height=620,
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def power_figure(r: TwoPhaseResult) -> go.Figure:
    """Aerodynamic power versus speed: PredimRC, drag sources, total; V₁, V₂ from the imposed-speed blocks."""
    c = r.curve
    fig = go.Figure()
    v = 3.6 * c.v_m_s
    keep = v <= v_limit_kmh(r)
    fig.add_trace(
        go.Scatter(
            x=v[keep],
            y=np.asarray(c.power_predimrc_w)[keep],
            name="PredimRC (P (W) column)",
            line={"dash": "dot"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=v[keep],
            y=np.asarray(c.drag_sources_n * c.v_m_s * c.drag_factor)[keep],
            name="drag sources ½ρV³ΣCdS",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=v[keep],
            y=np.asarray(c.power_total_w)[keep],
            name="total",
            line={"width": 3},
        )
    )
    for p in r.cruise:
        fig.add_trace(
            go.Scatter(
                x=[3.6 * p.v_m_s],
                y=[p.aero_power_w],
                mode="markers+text",
                text=[f"V{p.index}"],
                textposition="top center",
                name=f"V{p.index} (PredimRC vitesse imposée)",
                marker={"size": 12, "color": V_COLORS[p.index]},
            )
        )
    fig.update_layout(
        title=f"Aerodynamic power versus speed (ρ = {c.rho:.4f} kg/m³)",
        xaxis_title="Vx (km/h)",
        yaxis_title="aerodynamic power (W)",
        height=400,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def imposed_figure(r: TwoPhaseResult) -> go.Figure:
    """ "Performances à vitesse imposée": aerodynamic power and L/D versus C_z, trimmed C_z marked."""
    a, c = r.aero_results, r.curve
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06)
    for k, block in sorted(a.imposed.items()):
        lift = 0.5 * c.rho * block.vx_m_s**2 * c.wing_area_m2 * block.cz_wing
        name = f"Vx {k} = {3.6 * block.vx_m_s:.1f} km/h"
        fig.add_trace(
            go.Scatter(
                x=block.cz_wing, y=block.power_w, name=name, line={"color": V_COLORS[k]}
            ),
            1,
            1,
        )
        fig.add_trace(
            go.Scatter(
                x=block.cz_wing,
                y=lift / block.drag_n,
                name=name,
                showlegend=False,
                line={"color": V_COLORS[k]},
            ),
            2,
            1,
        )
        cz = 2 * c.mass_kg * GRAVITY / (c.rho * c.wing_area_m2 * block.vx_m_s**2)
        fig.add_vline(x=cz, line={"color": V_COLORS[k], "dash": "dash"})
    fig.update_yaxes(title_text="Puissance aéro (W)", row=1, col=1)
    fig.update_yaxes(title_text="Finesse (Cz / Cx)", row=2, col=1)
    fig.update_xaxes(title_text="Cz", row=2, col=1)
    fig.update_layout(
        title="Performances à vitesse imposée (trimmed Cz dashed)",
        height=520,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig


def iso_text(r: TwoPhaseResult) -> tuple[bool | None, str]:
    """(passed or None when not available, message) of the iso-model check."""
    iso = r.iso_check
    if iso is None:
        return None, "No PredimRC evaluation (multicopter)."
    if not iso.available:
        return None, "Iso-model check not available (no PredimRC blocks)."
    gaps = ", ".join(f"V{i + 1} {100 * g:+.2f} %" for i, g in enumerate(iso.curve_gaps))
    return iso.passed, (
        f"Iso-model with PredimRC: curve {iso.curve_max_rel_dev:.1e}, imposed speeds "
        f"{iso.imposed_max_rel_dev:.1e} (tolerance 1e-6). Interpolated curve versus PredimRC at the "
        f"target speeds: {gaps} (coarse polar grid; the target-speed values are PredimRC's)."
    )
