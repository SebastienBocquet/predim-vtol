"""Power chain tab: diagram of the cables and ESCs, gauge table (INC2-004)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go

from predimrc_wrapper.propulsion.wiring import default_layout

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project

TERMS = """
- **Battery**: in the nose of a winged aircraft, centred on the frame of a multicopter; its connector is at its
  rear end, where the main cable starts (no cable length along the battery).
- **Main cable**: battery connector → distribution point. Carries the whole battery current (2 conductors, plus the
  connector resistance).
- **Distribution point**: where the main cable splits towards the ESCs (power distribution board). With a 4-in-1 ESC
  it is the 4-in-1 board; otherwise the wing spar station on the fuselage (winged aircraft) or the frame centre
  (multicopter).
- **DC cables**: distribution point → each separate ESC (2 conductors per ESC). None with a 4-in-1 board.
- **Phase cables**: ESC → motor (3 conductors). They carry the motor current, larger than the battery-side current at
  part throttle (the ESC lowers the voltage seen by the motor).
- **Gauge (AWG)**: when not entered, the smallest wire whose current rating is at least 1.25 × the hover current it
  carries (table below). Losses use the copper resistance at the wire temperature.
"""

COLORS = {"main": "black", "DC": "#1f77b4", "phase": "#ff7f0e"}


def _path(
    project: Project, ex: float, ey: float, mx: float, my: float, spar: float
) -> tuple[list, list]:
    """Phase cable path in the top view (same rule as the length computation)."""
    if project.aero is not None and abs(my) > 1.0:
        return [ex, spar, spar, mx], [ey, ey, my, my]
    return [ex, mx], [ey, my]


def diagram(project: Project) -> go.Figure:
    """Top view (y horizontal, x downward like the geometry): battery, distribution point, ESCs, cables."""
    layout = default_layout(project)
    fig = go.Figure()
    wing_borne = project.aero is not None
    spar = 0.25 * project.aero.wing.root_chord_mm if wing_borne else 0.0
    battery_length = project.wiring.battery_length_mm if project.wiring else 120.0
    front = layout.battery_rear_x_mm - battery_length
    if wing_borne:
        fus = project.aero.fuselage
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
                name="fuselage",
                line={"color": "lightgrey"},
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[-20, 20, 20, -20, -20],
            y=[front, front, layout.battery_rear_x_mm, layout.battery_rear_x_mm, front],
            mode="lines",
            fill="toself",
            name="battery",
            line={"color": "green"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0, 0],
            y=[layout.battery_rear_x_mm, layout.distribution_x_mm],
            mode="lines",
            name=f"main cable {layout.main_length_mm:.0f} mm",
            line={"color": COLORS["main"], "width": 5},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0],
            y=[layout.distribution_x_mm],
            mode="markers",
            name="distribution point",
            marker={"symbol": "square", "size": 12, "color": "black"},
        )
    )
    for b, m in zip(layout.branches, project.motors, strict=False):
        show = b.motor_index == 0
        if b.dc_length_mm > 0:
            dx = [layout.distribution_x_mm, b.esc_x_mm]
            dy = [0.0, b.esc_y_mm]
            fig.add_trace(
                go.Scatter(
                    x=dy,
                    y=dx,
                    mode="lines",
                    name="DC cables",
                    legendgroup="DC",
                    showlegend=show or not any(t.name == "DC cables" for t in fig.data),
                    line={"color": COLORS["DC"], "width": 3},
                )
            )
        px, py = _path(project, b.esc_x_mm, b.esc_y_mm, m.x_mm, m.y_mm, spar)
        fig.add_trace(
            go.Scatter(
                x=py,
                y=px,
                mode="lines",
                name="phase cables",
                legendgroup="phase",
                showlegend=not any(t.name == "phase cables" for t in fig.data),
                line={"color": COLORS["phase"], "width": 2, "dash": "dot"},
                hovertext=f"motor {b.motor_index + 1}: {b.phase_length_mm:.0f} mm",
                hoverinfo="text",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[b.esc_y_mm],
                y=[b.esc_x_mm],
                mode="markers",
                name="ESC",
                legendgroup="ESC",
                showlegend=not any(t.name == "ESC" for t in fig.data),
                marker={"symbol": "diamond", "size": 10, "color": COLORS["phase"]},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[m.y_mm],
                y=[m.x_mm],
                mode="markers+text",
                text=[str(b.motor_index + 1)],
                textposition="top center",
                name="motor",
                legendgroup="motor",
                showlegend=not any(t.name == "motor" for t in fig.data),
                marker={"size": 12, "color": "red"},
            )
        )
    fig.update_layout(
        title="Cables and ESCs (top view, nose up)",
        xaxis_title="y (mm)",
        yaxis_title="station x (mm, aft)",
        height=480,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h"},
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1, autorange="reversed")
    return fig


def cable_rows(
    project: Project, hover_currents: list[float] | None = None
) -> list[dict]:
    """Lengths and gauges of every cable (gauges from the hover currents when not entered)."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.propulsion.chain import PowerChain  # noqa: PLC0415

    chain = PowerChain.from_project(
        project, AircraftModel(project).battery, hover_currents
    )
    layout = default_layout(project)
    rows = [
        {
            "cable": "main",
            "from → to": "battery → distribution point",
            "length (mm)": round(chain.p.main_length_mm),
            "gauge (AWG)": chain.p.main_awg,
            "gauge from": "entered"
            if project.wiring and project.wiring.main_awg
            else "current",
        }
    ]
    for b, _lay in zip(chain.p.branches, layout.branches, strict=False):
        if b.dc_length_mm > 0:
            rows.append({
                "cable": "DC",
                "from → to": f"distribution → ESC of {b.name}",
                "length (mm)": round(b.dc_length_mm),
                "gauge (AWG)": b.dc_awg,
                "gauge from": "entered"
                if project.wiring and project.wiring.dc_awg
                else "current",
            })
        rows.append({
            "cable": "phase",
            "from → to": f"ESC → {b.name}",
            "length (mm)": round(b.phase_length_mm),
            "gauge (AWG)": b.phase_awg,
            "gauge from": "entered"
            if project.wiring and project.wiring.phase_awg
            else "current",
        })
    return rows
