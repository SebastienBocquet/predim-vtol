"""Explanations of the Test data tab: what is compared, formulas, energy chain sketch (REQ-UI-011)."""

from __future__ import annotations

import plotly.graph_objects as go

INTRO = """
**What this tab does.** You enter battery powers measured in flight (telemetry: voltage × current at
the pack). For each point the tool recomputes the battery power **with the model, without any
calibration**, at the mass, altitude and temperature of the point, and shows the deviation. The
95 % band is the uncertainty of the thrust–power surrogate (hover points only).

- **Hover point:** the aircraft hovers; give the battery power and, if different from the project,
  the mass.
- **Cruise point:** level flight at a steady airspeed; give the airspeed (km/h) and the battery power.

A deviation of a few % is the model accuracy; a large one points to an input to check (masses,
propellers, battery, drag) — or to the calibration below.
"""

HOVER = [
    (
        "1. Thrust of each lift motor, from the balance of forces and moments about the CG",
        (
            r"\sum_i T_i = k_{dl}\,m\,g,\qquad \sum_i T_i\,(x_i - x_{CG}) = 0,"
            r"\qquad \sum_i T_i\,(y_i - y_{CG}) = 0"
        ),
    ),
    (
        (
            "2. Electric power of each motor, read in the thrust–power test data of its motor + propeller "
            "pair through the surrogate (physics model × Gaussian-process correction, mean ± σ)"
        ),
        r"P_i = \mathrm{GP}(T_i, U)\quad\text{(at the motor input, or at the ESC input when the table names the ESC)}",
    ),
    (
        "3. Battery power: the motors, the losses of the power chain and the avionics",
        r"P_{bat} = \sum_i P_i + \underbrace{P_{ESC} + P_{cables} + R_{bat}I^2}_{\text{power chain}} + P_{av}",
    ),
]

CRUISE_WINGED = [
    (
        (
            "1. Aerodynamic power at the airspeed V: PredimRC (wing, tail, fuselage at the imposed speed) "
            "plus the drag sources of the Drag tab"
        ),
        r"P_{aero}(V) = P_{PredimRC}(V) + \tfrac12 \rho V^3 \sum_k (C_dS)_k = D\,V",
    ),
    (
        (
            "2. Thrust D shared by the cruise motors (by disc area); propeller by blade elements at its pitch, "
            "then the motor model"
        ),
        (
            r"T_j = D\,\frac{A_j}{\sum A},\qquad P_{shaft,j} = \mathrm{BEM}(T_j, V, \text{pitch}),"
            r"\qquad P_j = P_{shaft,j} + R_m I_j^2 + I_0 U_{emf}"
        ),
    ),
    (
        "3. Battery power, as in hover",
        r"P_{bat} = \sum_j P_j + P_{chain} + P_{av}",
    ),
]

CRUISE_MULTICOPTER = [
    (
        (
            "1. Drag of the multicopter: in-house model (body C_d × frontal area of the Drag tab, plus the "
            "drag sources) — PredimRC is not used for a multicopter"
        ),
        r"D = \tfrac12 \rho V^2 \Big(C_{d,body} A_{body} + \sum_k (C_dS)_k\Big)",
    ),
    (
        "2. The frame tilts forward by α so that the rotors carry the weight and push against the drag",
        r"\tan\alpha = \frac{D}{m g},\qquad T_i = f_i \sqrt{(m g)^2 + D^2}",
    ),
    (
        (
            "3. Rotor power in forward flight (Glauert induced velocity, figure of merit FM), then the "
            "motor, ESC and battery"
        ),
        (
            r"v_i = \frac{v_h^2}{\sqrt{(V\cos\alpha)^2 + (V\sin\alpha + v_i)^2}},\qquad"
            r" P_{shaft,i} = \frac{T_i\,(V\sin\alpha + v_i)}{FM}"
        ),
    ),
]

CALIBRATION = """
**Calibration.** The comparison above never changes the model. The calibration does: each measured
point ticked here sets **one** factor so that the two-phase model gives exactly the measured battery
power, at the mass of the point. The Run then uses the calibrated factors (flight time, power
budget...).

- **Why one factor per point:** one measurement is one equation, it can determine only one unknown.
  The factor goes to the least known term.
- **Hover point → k_h**, multiplier of the motor powers read in the thrust–power test data
  (`mission.hover_power_factor`, 0.5 to 2): P_hover,model(k_h) = P_hover,measured. It covers what the
  test bench did not see: installation, propeller differences, battery and wiring of the aircraft.
- **Cruise point, after k_h → k_D**, multiplier of the total cruise drag (`mission.drag_factor`, 0.2
  to 5; PredimRC polar or body C_d·A, plus the drag sources): P_cruise,model(V, k_D) =
  P_cruise,measured. The propeller (blade elements at its pitch) and the motor are physics models,
  the drag is the least known term.
- A factor reaching its bound means the measurement is outside what the model can represent: check
  the masses, the motor and the battery first.
"""


def _box(fig: go.Figure, x: float, y: float, text: str, color: str) -> None:
    fig.add_shape(
        type="rect",
        x0=x - 0.55,
        x1=x + 0.55,
        y0=y - 0.35,
        y1=y + 0.35,
        line={"color": color, "width": 2},
        fillcolor="rgba(0,0,0,0)",
    )
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, font={"size": 12})


def energy_chain_figure(winged: bool) -> go.Figure:
    """Sketch of the energy chain, from the cells to the air, with the model of each block."""
    blocks = [
        ("cells", "battery<br><sub>R_bat·I²</sub>", "#2ca02c"),
        ("cables", "main + DC<br>cables<br><sub>ρL/A·I²</sub>", "#7f7f7f"),
        ("esc", "ESC<br><sub>η_ESC</sub>", "#1f77b4"),
        ("phase", "phase<br>cables", "#7f7f7f"),
        ("motor", "motor<br><sub>R_m, I₀, K_v</sub>", "#ff7f0e"),
        (
            "prop",
            "propeller<br><sub>hover: test<br>data + GP<br>cruise: BEM</sub>",
            "#d62728",
        ),
        (
            "air",
            "air<br><sub>"
            + (
                "PredimRC<br>+ drag sources"
                if winged
                else "body C_d·A<br>+ drag sources"
            )
            + "</sub>",
            "#9467bd",
        ),
    ]
    fig = go.Figure()
    for k, (_, text, color) in enumerate(blocks):
        _box(fig, 1.3 * k, 0.0, text, color)
        if k:
            fig.add_annotation(
                x=1.3 * k - 0.55,
                y=0.0,
                ax=1.3 * (k - 1) + 0.55,
                ay=0.0,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.2,
                text="",
            )
    fig.add_annotation(
        x=1.3 * 3,
        y=-0.6,
        text="P_bat measured at the cells' terminals ← compared with the model → P_bat computed",
        showarrow=False,
        font={"size": 11, "color": "grey"},
    )
    fig.update_xaxes(visible=False, range=[-0.7, 1.3 * (len(blocks) - 1) + 0.7])
    fig.update_yaxes(visible=False, range=[-0.75, 0.5])
    fig.update_layout(
        height=240,
        margin={"l": 5, "r": 5, "t": 30, "b": 5},
        title="Energy chain and the model of each block",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
