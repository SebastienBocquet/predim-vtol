"""Power chain tab: diagram of the cables and ESCs, gauge table (INC2-004)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go

from predimrc_wrapper.propulsion.wiring import cable_rows_mass
from predimrc_wrapper.propulsion.wiring import default_layout
from predimrc_wrapper.propulsion.wiring import phase_path

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
- **4-in-1 ESC**: one board for the lift motors, and for the cruise motor when *cruise on four in one* is set
  (no separate cruise ESC: its mass and loss go to the board), 4 motors at most. Its mass and efficiency are entered
  here; separate ESCs take the ESC mass and efficiency of their unit type.
- **Phase cables**: ESC → motor (3 conductors). They carry the motor current, larger than the battery-side current at
  part throttle (the ESC lowers the voltage seen by the motor).
- **Gauge (AWG)**: when not entered, the smallest wire whose current rating is at least 1.25 × the maximum current
  of the motor (data sheet), the same cable at every operating point (table below). Losses use the copper resistance at the wire temperature.
"""

COLORS = {"main": "black", "DC": "#1f77b4", "phase": "#ff7f0e"}


def _path(project: Project, index: int, ex: float, ey: float) -> tuple[list, list]:
    """Phase cable path in the top view (same rule as the length computation)."""
    points = phase_path(project, index, ex, ey)
    return [p[0] for p in points], [p[1] for p in points]


def diagram(project: Project) -> go.Figure:
    """Top view (y horizontal, x downward like the geometry): battery, distribution point, ESCs, cables."""
    layout = default_layout(project)
    fig = go.Figure()
    wing_borne = project.aero is not None
    0.25 * project.aero.wing.root_chord_mm if wing_borne else 0.0
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
        px, py = _path(project, b.motor_index, b.esc_x_mm, b.esc_y_mm)
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


def cable_rows(project: Project) -> list[dict]:
    """Every cable: length, conductors, gauge (entered or sized for the motor I_max), mass."""
    rows = cable_rows_mass(project)
    spec = project.wiring
    entered = {
        "main": spec is not None and spec.main_awg is not None,
        "DC": spec is not None and spec.dc_awg is not None,
        "phase": spec is not None and spec.phase_awg is not None,
    }
    for r in rows:
        r["gauge from"] = "entered" if entered[r["cable"]] else "motor I_max"
    return rows
