"""Propeller sizing tab: pitch for the two target speeds (REQ-PROP-007), hover penalty of a tilting unit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.ui import propulsion_charts as pc

if TYPE_CHECKING:
    import plotly.graph_objects as go

    from predimrc_wrapper.aircraft import AircraftModel
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult


def cruise_pitch_rows(
    aircraft: AircraftModel, two: TwoPhaseResult, unit_name: str
) -> tuple[list[dict], dict]:
    """Per pitch: propeller × motor efficiency at V₁ and V₂ (unit thrust of the result) and, for a
    tilting unit, the electric power in hover; plus the recommendations."""
    spec = aircraft.project.propulsion_units[unit_name]
    unit = aircraft.units[unit_name]
    pitches = sorted(
        set(pc.default_pitches(spec.prop_diameter_in))
        | ({spec.prop_pitch_in} if spec.prop_pitch_in else set())
    )
    speeds, thrusts = [], []
    for c in two.cruise:
        motors = [m for m in c.motors if m.unit == unit_name]
        if motors:
            speeds.append(c.v_m_s)
            thrusts.append(motors[0].thrust_n)
    if not speeds:
        return [], {}
    u = two.hover.chain.bus_voltage_v
    study = pc.pitch_study(
        unit,
        spec.prop_diameter_in,
        pitches,
        np.array(speeds),
        np.array(thrusts),
        aircraft.rho,
        u,
    )
    hover_motors = [m for m in two.hover.motors if m.unit == unit_name]
    hover = {}
    if hover_motors:
        for row in pc.hover_pitch_rows(
            unit,
            spec.prop_diameter_in,
            pitches,
            hover_motors[0].thrust_n,
            aircraft.rho,
            u,
        ):
            hover[row["pitch (in)"]] = row
    rows = []
    for i, p in enumerate(pitches):
        row = {
            "pitch (in)": p,
            "current": bool(spec.prop_pitch_in and abs(p - spec.prop_pitch_in) < 1e-9),
        }
        for k in range(len(speeds)):
            row[f"η prop × motor V{k + 1}"] = round(float(study["efficiency"][i, k]), 3)
            row[f"η propeller V{k + 1}"] = round(
                float(study["prop_efficiency"][i, k]), 3
            )
            row[f"rpm V{k + 1}"] = (
                None
                if not np.isfinite(study["rpm"][i, k])
                else round(float(study["rpm"][i, k]))
            )
            row[f"within limits V{k + 1}"] = bool(study["feasible"][i, k])
        if hover:
            h = hover.get(p, {})
            row["hover electric power (W)"] = h.get("electric power (W)")
            row["hover within limits"] = h.get("within motor limits")
        rows.append(row)
    feasible = np.all(study["feasible"], axis=1)
    mean = np.where(feasible, np.nanmean(study["efficiency"], axis=1), -np.inf)
    rec = {
        f"best pitch V{k + 1} (in)": float(study["best_pitch_in"][k])
        for k in range(len(speeds))
    }
    rec["best compromise V1 + V2 (in)"] = (
        float(pitches[int(np.argmax(mean))]) if np.isfinite(mean).any() else None
    )
    if hover:
        powers = {
            p: r["electric power (W)"]
            for p, r in hover.items()
            if r["electric power (W)"] is not None
        }
        if powers and rec["best compromise V1 + V2 (in)"] is not None:
            best_h = min(powers, key=powers.get)
            comp = rec["best compromise V1 + V2 (in)"]
            rec["best hover pitch (in)"] = best_h
            rec["hover penalty of the compromise (%)"] = round(
                100 * (powers.get(comp, np.nan) / powers[best_h] - 1), 1
            )
    return rows, rec


def pitch_figure(rows: list[dict], rec: dict, title: str) -> go.Figure:
    """Propeller × motor efficiency versus pitch at V1 and V2, best pitches and compromise marked."""
    import plotly.graph_objects as go  # noqa: PLC0415

    fig = go.Figure()
    colors = {1: "#d62728", 2: "#2ca02c"}
    pitches = [r["pitch (in)"] for r in rows]
    for k in (1, 2):
        key = f"η prop × motor V{k}"
        if key not in rows[0]:
            continue
        ok = [r[f"within limits V{k}"] for r in rows]
        fig.add_trace(
            go.Scatter(
                x=pitches,
                y=[r[key] for r in rows],
                mode="lines+markers",
                name=f"propeller × motor, V{k}",
                line={"color": colors[k]},
                marker={"symbol": ["circle" if o else "x" for o in ok], "size": 9},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=pitches,
                y=[r[f"η propeller V{k}"] for r in rows],
                mode="lines",
                name=f"propeller alone, V{k}",
                line={"color": colors[k], "dash": "dot"},
            )
        )
        best = rec.get(f"best pitch V{k} (in)")
        if best is not None and best == best:
            y = next(r[key] for r in rows if r["pitch (in)"] == best)
            fig.add_trace(
                go.Scatter(
                    x=[best],
                    y=[y],
                    mode="markers+text",
                    text=[f"best V{k}: {best:g} in"],
                    textposition="top center",
                    showlegend=False,
                    marker={"size": 16, "symbol": "star", "color": colors[k]},
                )
            )
    comp = rec.get("best compromise V1 + V2 (in)")
    if comp is not None:
        fig.add_vline(
            x=comp,
            line={"color": "black", "dash": "dash"},
            annotation_text=f"compromise {comp:g} in",
        )
    current = next((r["pitch (in)"] for r in rows if r.get("current")), None)
    if current is not None:
        fig.add_vline(
            x=current,
            line={"color": "grey", "dash": "dot"},
            annotation_text=f"current {current:g} in",
            annotation_position="bottom right",
        )
    fig.update_layout(
        title=title,
        xaxis_title="pitch (in)",
        yaxis_title="efficiency",
        height=400,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h"},
    )
    return fig


def database_propellers(diameter_in: float) -> list[str]:
    """Database propellers of the same diameter."""
    from predimrc_wrapper.data import default_propellers  # noqa: PLC0415

    db = default_propellers()
    return [f"{p} ({db.propeller(p).pitch_in:g} in)" for p in db.ids(diameter_in)]
