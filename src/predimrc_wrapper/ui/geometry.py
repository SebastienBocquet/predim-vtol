"""Geometry preview from the project parameters (REQ-UI-002).

Top view: y spanwise (mm, right positive), x stream-wise station aft-positive from the
wing root LE (or frame centre), drawn nose up. Front view: y spanwise, z up.
Lift rotors are horizontal discs, cruise propellers vertical discs, tilting motors are
drawn in their hover position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.aircraft.project import MotorSlot
    from predimrc_wrapper.aircraft.project import StabSpec
    from predimrc_wrapper.aircraft.project import WingSpec

INCH_MM = 25.4
WING, STAB, BODY, BOOM, CG = "#1f77b4", "#2ca02c", "#7f7f7f", "#444444", "#000000"
ROLE_COLORS = {"lift": "#d62728", "cruise": "#ff7f0e", "tilt": "#9467bd"}


@dataclass
class Outline:
    """Closed outline of a right half-wing (mm)."""

    x: list[float]
    y: list[float]
    half_span_mm: float


def wing_outline(
    wing: WingSpec | StabSpec, root_offset_mm: float = 0.0, span_scale: float = 1.0
) -> Outline:
    """Right half-wing: panels from ``root_offset_mm``, LE offsets absolute from the root LE.

    ``span_scale`` projects inclined panels (V-tail) on the top view.
    """
    y_le, x_le, x_te = [root_offset_mm], [0.0], [wing.root_chord_mm]
    y = root_offset_mm
    for length, chord, le in zip(
        wing.length_mm, wing.tip_chord_mm, wing.le_offset_mm, strict=False
    ):
        y += length * span_scale
        y_le.append(y)
        x_le.append(le)
        x_te.append(le + chord)
    xs = x_le + x_te[::-1] + [x_le[0]]
    ys = y_le + y_le[::-1] + [y_le[0]]
    return Outline(xs, ys, y)


def stab_dihedral_deg(stab: StabSpec) -> float:
    """Panel dihedral of the stabiliser from the PredimRC opening label ('120' → V-tail of 120°)."""
    try:
        opening = float(stab.opening)
    except ValueError:
        return 0.0
    return max(0.0, 90.0 - opening / 2.0) if 0.0 < opening < 180.0 else 0.0


def _mirror(
    fig: go.Figure, x, y, name: str, color: str, dx: float = 0.0, fill: bool = True
) -> None:
    for sign, show in ((1, True), (-1, False)):
        fig.add_trace(
            go.Scatter(
                x=[sign * v for v in y],
                y=[v + dx for v in x],
                mode="lines",
                name=name,
                legendgroup=name,
                showlegend=show,
                line={"color": color},
                fill="toself" if fill else None,
                opacity=0.8,
            )
        )


def _circle(
    cx: float, cy: float, r: float, n: int = 48
) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0, 2 * np.pi, n)
    return cx + r * np.cos(t), cy + r * np.sin(t)


def _radius(project: Project, motor: MotorSlot) -> float:
    return project.propulsion_units[motor.unit].prop_diameter_in * INCH_MM / 2


def rotor_stations(project: Project) -> list[tuple[float, float]]:
    """(station x aft-positive, y) of each lift rotor (role lift or tilt), mm."""
    return [(m.x_mm, m.y_mm) for m in project.lift_motors()]


def _layout(fig: go.Figure, title: str, y_title: str, reverse: bool) -> go.Figure:
    fig.update_layout(
        title=title,
        height=460,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        xaxis_title="y (mm)",
        yaxis_title=y_title,
        legend={"orientation": "h"},
    )
    fig.update_yaxes(
        scaleanchor="x", scaleratio=1, autorange="reversed" if reverse else True
    )
    return fig


def _legend(fig: go.Figure, name: str) -> bool:
    return not any(t.name == name for t in fig.data)


def _booms(project: Project) -> list[tuple[float, float, float]]:
    """(y, x_start, x_end) of the booms carrying the off-centreline lift motors of a quadplane."""
    by_y: dict[float, list[MotorSlot]] = {}
    for m in project.lift_motors():
        if abs(m.y_mm) > 1.0:
            by_y.setdefault(round(m.y_mm, 1), []).append(m)
    out = []
    for y, motors in by_y.items():
        r = max(_radius(project, m) for m in motors)
        xs = [m.x_mm for m in motors]
        out.append((y, min(xs) - r, max(max(xs) + r, 0.0)))
    return out


def _v_arms(fig: go.Figure, project: Project, front: bool) -> None:
    """Draw the V-arms of the drag sources (top view: y–x, front view: y–z)."""
    from predimrc_wrapper.aircraft.drag_sources import v_arm_segments  # noqa: PLC0415

    for source in project.drag_sources:
        if source.kind != "v_arms":
            continue
        for arm in v_arm_segments(source, project):
            (x0, y0, z0), (x1, y1, z1) = arm.root, arm.tip
            fig.add_trace(
                go.Scatter(
                    x=[y0, y1],
                    y=[z0, z1] if front else [x0, x1],
                    mode="lines",
                    name="V-arm",
                    legendgroup="V-arm",
                    showlegend=_legend(fig, "V-arm"),
                    line={"color": BOOM, "width": 3, "dash": "dash"},
                )
            )


def top_view(project: Project) -> go.Figure:
    fig = go.Figure()
    _v_arms(fig, project, front=False)
    if project.architecture == "quadplane" and project.aero is not None:
        fus, wing, stab = project.aero.fuselage, project.aero.wing, project.aero.stab
        x0 = -fus.nose_lever_mm
        fig.add_trace(
            go.Scatter(
                x=[
                    -fus.width_mm / 2,
                    fus.width_mm / 2,
                    fus.width_mm / 2,
                    -fus.width_mm / 2,
                    -fus.width_mm / 2,
                ],
                y=[x0, x0, x0 + fus.length_mm, x0 + fus.length_mm, x0],
                mode="lines",
                fill="toself",
                name="fuselage",
                line={"color": BODY},
            )
        )
        w = wing_outline(wing, fus.width_mm / 2)
        _mirror(fig, w.x, w.y, "wing", WING)
        s = wing_outline(
            stab, stab.lateral_gap_mm / 2, np.cos(np.radians(stab_dihedral_deg(stab)))
        )
        _mirror(fig, s.x, s.y, "stabiliser", STAB, dx=stab.lever_mm)
        for y, xa, xb in _booms(project):
            fig.add_trace(
                go.Scatter(
                    x=[y, y],
                    y=[xa, xb],
                    mode="lines",
                    name="boom",
                    legendgroup="boom",
                    showlegend=_legend(fig, "boom"),
                    line={"color": BOOM, "width": 4},
                )
            )
    else:
        reach = max(np.hypot(m.x_mm, m.y_mm) for m in project.motors)
        for m in project.motors:
            fig.add_trace(
                go.Scatter(
                    x=[0, m.y_mm],
                    y=[0, m.x_mm],
                    mode="lines",
                    name="arm",
                    legendgroup="arm",
                    showlegend=False,
                    line={"color": BOOM, "width": 4},
                )
            )
        cx, cy = _circle(0, 0, 0.18 * reach)
        fig.add_trace(
            go.Scatter(
                x=cy,
                y=cx,
                mode="lines",
                fill="toself",
                name="body",
                line={"color": BODY},
            )
        )
    for i, m in enumerate(project.motors, start=1):
        r, color, name = _radius(project, m), ROLE_COLORS[m.role], f"{m.role} rotor"
        if m.role == "cruise":
            xs, ys = [m.x_mm, m.x_mm], [m.y_mm - r, m.y_mm + r]
        else:
            xs, ys = _circle(m.x_mm, m.y_mm, r)
        fig.add_trace(
            go.Scatter(
                x=ys,
                y=xs,
                mode="lines",
                name=name,
                legendgroup=name,
                showlegend=_legend(fig, name),
                line={
                    "color": color,
                    "dash": "dot",
                    "width": 3 if m.role == "cruise" else 2,
                },
                hovertext=f"motor {i}: {m.unit} ({m.role})",
                hoverinfo="text",
            )
        )
        fig.add_annotation(
            x=m.y_mm, y=m.x_mm, text=str(i), showarrow=False, font={"color": color}
        )
    if project.cg_x_mm is not None:
        fig.add_trace(
            go.Scatter(
                x=[project.cg_y_mm],
                y=[project.cg_x_mm],
                mode="markers",
                name="CG",
                marker={"symbol": "x", "size": 12, "color": CG},
            )
        )
    return _layout(
        fig,
        "Top view (motor numbers as in the project)",
        "station x (mm, aft)",
        reverse=True,
    )


def front_view(project: Project) -> go.Figure:
    fig = go.Figure()
    _v_arms(fig, project, front=True)
    z_rotor = 40.0
    if project.architecture == "quadplane" and project.aero is not None:
        fus, wing, stab = project.aero.fuselage, project.aero.wing, project.aero.stab
        ys, zs = [fus.width_mm / 2], [0.0]
        for length, dihedral in zip(wing.length_mm, wing.dihedral_deg, strict=False):
            ys.append(ys[-1] + length * np.cos(np.radians(dihedral)))
            zs.append(zs[-1] + length * np.sin(np.radians(dihedral)))
        _mirror(fig, zs, ys, "wing", WING, fill=False)
        h, b = fus.height_mm / 2, fus.width_mm / 2
        fig.add_trace(
            go.Scatter(
                x=[-b, b, b, -b, -b],
                y=[-h, -h, h, h, -h],
                mode="lines",
                fill="toself",
                name="fuselage",
                line={"color": BODY},
            )
        )
        dihedral = np.radians(stab_dihedral_deg(stab))
        span = sum(stab.length_mm)
        y0, z0 = stab.lateral_gap_mm / 2, stab.height_mm
        _mirror(
            fig,
            [z0, z0 + span * np.sin(dihedral)],
            [y0, y0 + span * np.cos(dihedral)],
            "stabiliser",
            STAB,
            fill=False,
        )
        for y, _, _ in _booms(project):
            fig.add_trace(
                go.Scatter(
                    x=[y],
                    y=[-h / 2],
                    mode="markers",
                    name="boom",
                    legendgroup="boom",
                    showlegend=_legend(fig, "boom"),
                    marker={"color": BOOM, "size": 10},
                )
            )
        z_rotor = -h / 2 + 40.0
    for m in project.motors:
        r, color, name = _radius(project, m), ROLE_COLORS[m.role], f"{m.role} rotor"
        if m.role == "cruise":
            cy, cz = _circle(m.y_mm, 0.0, r)
        else:
            cy, cz = [m.y_mm - r, m.y_mm + r], [z_rotor, z_rotor]
        fig.add_trace(
            go.Scatter(
                x=cy,
                y=cz,
                mode="lines",
                name=name,
                legendgroup=name,
                showlegend=_legend(fig, name),
                line={"color": color, "dash": "dot"},
            )
        )
    return _layout(fig, "Front view", "z (mm)", reverse=False)
