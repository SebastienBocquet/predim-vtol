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
        {"block": "Aile", "quantity": "Surface totale (dm²)", "value": round(a.total_surface, 2)},
        {"block": "Aile", "quantity": "Corde moyenne (mm)", "value": round(a.mean_chord, 1)},
        {"block": "Aile", "quantity": "Envergure aéro (mm)", "value": round(a.span_aero)},
        {"block": "Aile", "quantity": "Envergure totale (mm)", "value": round(a.span_total)},
        {"block": "Aile", "quantity": "Allongement", "value": round(a.aspect_ratio, 2)},
        {"block": "Aile", "quantity": "Allongement ellip.", "value": round(a.aspect_ratio_el, 2)},
        {"block": "Réglages", "quantity": "CG (% corde moyenne)", "value": round(a.cg, 1)},
        {"block": "Réglages", "quantity": "Foyer (% corde moyenne)", "value": round(a.foyer, 1)},
        {"block": "Réglages", "quantity": "Masses (g)", "value": round(1000 * a.mass_kg)},
        {"block": "Réglages", "quantity": "Charge (g/dm²)", "value": round(a.wing_loading, 1)},
        {"block": "Performances", "quantity": "Altitude (m)", "value": a.altitude_m},
        {"block": "Performances", "quantity": "Temp. (°C)", "value": round(a.temperature_c, 1)},
        {"block": "Performances", "quantity": "Densité air (kg/m³)", "value": round(a.rho, 4)},
    ]


def palier_figure(r: TwoPhaseResult) -> go.Figure:
    """"Performances en palier (plané)": sink rate, L/D and C_z versus V_x (km/h)."""
    a = r.aero_results
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    vx = 3.6 * np.asarray(a.vx)
    fig.add_trace(go.Scatter(x=vx, y=a.sink_rate, name="Vz (m/s)"), 1, 1)
    fig.add_trace(go.Scatter(x=vx, y=a.finesse_vx, name="Finesse (Cz/Cx)"), 2, 1)
    fig.add_trace(go.Scatter(x=vx, y=a.cz, name="Cz aile"), 3, 1)
    for c in r.cruise:
        fig.add_vline(x=3.6 * c.v_m_s, line={"color": V_COLORS[c.index], "dash": "dash"})
    fig.update_yaxes(title_text="Vz (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="Cz / Cx", row=2, col=1)
    fig.update_yaxes(title_text="Cz", row=3, col=1)
    fig.update_xaxes(title_text="Vx (km/h)", row=3, col=1)
    fig.update_layout(title="Performances en palier (plané)", height=620, showlegend=False,
                      margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def power_figure(r: TwoPhaseResult) -> go.Figure:
    """Aerodynamic power versus speed: PredimRC, drag sources, total; V₁, V₂ from the imposed-speed blocks."""
    c = r.curve
    fig = go.Figure()
    v = 3.6 * c.v_m_s
    fig.add_trace(go.Scatter(x=v, y=c.power_predimrc_w, name="PredimRC (P (W) column)", line={"dash": "dot"}))
    fig.add_trace(go.Scatter(x=v, y=c.drag_sources_n * c.v_m_s * c.drag_factor, name="drag sources ½ρV³ΣCdS"))
    fig.add_trace(go.Scatter(x=v, y=c.power_total_w, name="total", line={"width": 3}))
    for p in r.cruise:
        fig.add_trace(go.Scatter(x=[3.6 * p.v_m_s], y=[p.aero_power_w], mode="markers+text", text=[f"V{p.index}"],
                                 textposition="top center", name=f"V{p.index} (PredimRC vitesse imposée)",
                                 marker={"size": 12, "color": V_COLORS[p.index]}))
    fig.update_layout(title=f"Aerodynamic power versus speed (ρ = {c.rho:.4f} kg/m³)", xaxis_title="Vx (km/h)",
                      yaxis_title="aerodynamic power (W)", height=400, margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def imposed_figure(r: TwoPhaseResult) -> go.Figure:
    """"Performances à vitesse imposée": aerodynamic power and L/D versus C_z, trimmed C_z marked."""
    a, c = r.aero_results, r.curve
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06)
    for k, block in sorted(a.imposed.items()):
        lift = 0.5 * c.rho * block.vx_m_s**2 * c.wing_area_m2 * block.cz_wing
        name = f"Vx {k} = {3.6 * block.vx_m_s:.1f} km/h"
        fig.add_trace(go.Scatter(x=block.cz_wing, y=block.power_w, name=name, line={"color": V_COLORS[k]}), 1, 1)
        fig.add_trace(go.Scatter(x=block.cz_wing, y=lift / block.drag_n, name=name, showlegend=False,
                                 line={"color": V_COLORS[k]}), 2, 1)
        cz = 2 * c.mass_kg * GRAVITY / (c.rho * c.wing_area_m2 * block.vx_m_s**2)
        fig.add_vline(x=cz, line={"color": V_COLORS[k], "dash": "dash"})
    fig.update_yaxes(title_text="Puissance aéro (W)", row=1, col=1)
    fig.update_yaxes(title_text="Finesse (Cz / Cx)", row=2, col=1)
    fig.update_xaxes(title_text="Cz", row=2, col=1)
    fig.update_layout(title="Performances à vitesse imposée (trimmed Cz dashed)", height=520,
                      margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def iso_text(r: TwoPhaseResult) -> tuple[bool | None, str]:
    """(passed or None when not available, message) of the iso-model check."""
    iso = r.iso_check
    if iso is None:
        return None, "No PredimRC evaluation (multicopter)."
    if not iso.available:
        return None, "Iso-model check not available (no PredimRC blocks)."
    gaps = ", ".join(f"V{i + 1} {100 * g:+.2f} %" for i, g in enumerate(iso.curve_gaps))
    return iso.passed, (f"Iso-model with PredimRC: curve {iso.curve_max_rel_dev:.1e}, imposed speeds "
                        f"{iso.imposed_max_rel_dev:.1e} (tolerance 1e-6). Interpolated curve versus PredimRC at the "
                        f"target speeds: {gaps} (coarse polar grid; the target-speed values are PredimRC's).")
