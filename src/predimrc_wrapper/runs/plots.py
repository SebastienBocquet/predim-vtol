"""Figures superposing stored runs and families of runs (plotly, ``ui`` extra).

A figure missing from some runs (older ``result.json`` without the data) leaves these
runs out, with a warning.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from predimrc_wrapper.runs.operations import INPUT_PREFIX
from predimrc_wrapper.runs.operations import OUTPUT_PREFIX
from predimrc_wrapper.ui.studies_view import OUTPUT_LABELS
from predimrc_wrapper.ui.studies_view import label

if TYPE_CHECKING:
    from collections.abc import Iterable

    from predimrc_wrapper.runs.collection import RunResults

LOGGER = logging.getLogger(__name__)

FIGURES = ("flight_time", "power", "margins", "phase_energy", "hover_motors")
"""The figures of :func:`superpose`."""

MARGINS = (
    "margin_motor_power",
    "margin_motor_current",
    "margin_hover_thrust",
    "margin_thrust_to_weight",
    "margin_battery_c",
    "margin_mass",
)

FAMILY_OUTPUTS = (
    "flight_time_v1",
    "flight_time_v2",
    "mass_total",
    "hover_power",
    "margin_motor_power",
    "cost_purchase",
)
"""The outputs plotted against the varying input of a family."""


def _scale(name: str) -> float:
    return OUTPUT_LABELS.get(name, ("", "", 1.0))[2]


def _bars(runs: RunResults, names: Iterable[str], title: str, unit: str) -> go.Figure:
    """Grouped bars: one group per output, one bar per run."""
    names = list(names)
    summaries = runs.summaries
    fig = go.Figure()
    for (_, row), text in zip(summaries.iterrows(), runs.labels(), strict=True):
        fig.add_bar(
            name=text,
            x=[label(n) for n in names],
            y=[row.get(f"{OUTPUT_PREFIX}{n}", math.nan) * _scale(n) for n in names],
        )
    fig.update_layout(
        title=title, barmode="group", yaxis_title=unit, legend_title="run"
    )
    return fig


def _phase_energy(runs: RunResults) -> go.Figure:
    """Energy of each vertical phase and of the cruise at V1, stacked per run (Wh)."""
    fig = go.Figure()
    labels = runs.labels()
    by_phase: dict[str, list[float]] = {}
    for k, run in enumerate(runs):
        phases = run.result.get("phases") or []
        for p in phases:
            by_phase.setdefault(p["name"], [0.0] * len(labels))[k] = (
                p["battery_power_w"] * p["duration_s"] / 3600
            )
    for name, values in by_phase.items():
        fig.add_bar(name=name, x=labels, y=values)
    fig.update_layout(
        title="Energy of the vertical phases",
        barmode="stack",
        yaxis_title="Wh",
        legend_title="phase",
    )
    return fig


def _hover_motors(runs: RunResults) -> go.Figure:
    """Power margin of each lift motor in hover, one line per run."""
    fig = go.Figure()
    for run, text in zip(runs, runs.labels(), strict=True):
        motors = (run.result.get("hover") or {}).get("motors") or []
        if not motors:
            LOGGER.warning("The run %s has no hover motors: left out.", run.id)
            continue
        fig.add_scatter(
            name=text,
            x=[m.get("index", i) + 1 for i, m in enumerate(motors)],
            y=[m.get("power_margin", math.nan) for m in motors],
            mode="lines+markers",
        )
    fig.update_layout(
        title="Hover power margin of each lift motor",
        xaxis_title="motor",
        yaxis_title="power margin",
        xaxis={"dtick": 1},
        legend_title="run",
    )
    return fig


def superpose(runs: RunResults, names: Iterable[str] = ()) -> dict[str, go.Figure]:
    """The figures superposing the runs, labelled by their varying inputs.

    Args:
        runs: The runs.
        names: The names of the figures among :data:`FIGURES`. If empty, all.
    """
    names = list(names) or list(FIGURES)
    if not len(runs):
        return {}
    builders = {
        "flight_time": lambda: _bars(
            runs, ("flight_time_v1", "flight_time_v2"), "Flight time", "min"
        ),
        "power": lambda: _bars(
            runs,
            ("hover_power", "cruise_power_v1", "cruise_power_v2"),
            "Battery power",
            "W",
        ),
        "margins": lambda: _bars(runs, MARGINS, "Margins (≥ 0 is acceptable)", ""),
        "phase_energy": lambda: _phase_energy(runs),
        "hover_motors": lambda: _hover_motors(runs),
    }
    unknown = sorted(set(names) - set(builders))
    if unknown:
        msg = f"Unknown figures {unknown}; known: {list(FIGURES)}."
        raise KeyError(msg)
    return {name: builders[name]() for name in names}


def plot_family(runs: RunResults, along: str, title: str = "") -> dict[str, go.Figure]:
    """The outputs of a family versus its varying input, and its superposed runs.

    Args:
        runs: The runs of the family.
        along: The varying input.
        title: The title, e.g. the key of the family.
    """
    column = f"{INPUT_PREFIX}{along}"
    summaries = runs.summaries.sort_values(column, kind="stable")
    names = [n for n in FAMILY_OUTPUTS if f"{OUTPUT_PREFIX}{n}" in summaries.columns]
    cols = 3
    fig = make_subplots(
        rows=math.ceil(len(names) / cols),
        cols=cols,
        subplot_titles=[label(n) for n in names],
    )
    for k, name in enumerate(names):
        fig.add_scatter(
            x=list(summaries[column]),
            y=list(summaries[f"{OUTPUT_PREFIX}{name}"] * _scale(name)),
            mode="lines+markers",
            name=label(name),
            showlegend=False,
            row=k // cols + 1,
            col=k % cols + 1,
        )
    fig.update_xaxes(title_text=along)
    fig.update_layout(
        title=f"Outputs versus {along}" + (f" ({title})" if title else "")
    )
    return {f"outputs_vs_{along}": fig, **superpose(runs)}
