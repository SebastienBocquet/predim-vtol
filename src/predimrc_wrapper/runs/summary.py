"""Inputs, outputs and metadata of a run, flat, for the table of the summaries.

The inputs are the scalar leaves of the project, by the dotted paths of
:meth:`.Project.with_overrides` (``battery.mass_g``, ``motors.0.unit``,
``aero.wing.length_mm.1``); the outputs are those of the two-phase discipline
(``OUTPUTS_TWO_PHASE``), so that a stored run and a study point share their names.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project

LOGGER = logging.getLogger(__name__)

SUMMARY_VERSION = 1
"""Version of the format of ``summary.json``."""

OUTPUTS_TWO_PHASE = (
    "flight_time_v1",
    "flight_time_v2",
    "range_v1",
    "range_v2",
    "v1",
    "v2",
    "hover_power",
    "cruise_power_v1",
    "cruise_power_v2",
    "mass_total",
    "front_rear_ratio",
    "margin_motor_power",
    "margin_motor_current",
    "margin_hover_thrust",
    "margin_thrust_to_weight",
    "margin_battery_c",
    "margin_mass",
    "max_sd_rel",
    "cost_purchase",
    "cost_per_hour",
    "motor_out_tw",
    "feasible",
)
"""Outputs of the two-phase mode (INC2-007): times s, ranges m, speeds m/s, powers W; costs in
the currency of the prices (INC3-004); ``motor_out_tw``: worst remaining thrust-to-weight with
one lift motor stopped (0 when a motor loss is not survivable)."""

OUTPUT_RENAMES: dict[str, str] = {}
"""Former name → current name of the outputs, applied to the summaries of older runs."""

METADATA_KEYS = ("name", "architecture", "format_version")
"""Project fields stored as metadata of a run, not as inputs."""


def flatten_inputs(data: Any, prefix: str = "") -> dict[str, Any]:
    """The scalar leaves of project data, by dotted path (list items by index).

    Args:
        data: The project as plain data (:meth:`.Project.to_dict`).
        prefix: The path of ``data``.
    """
    if isinstance(data, dict):
        items = data.items()
    elif isinstance(data, list):
        items = enumerate(data)
    else:
        return {prefix: data}
    out = {}
    for key, value in items:
        if not prefix and key in METADATA_KEYS:
            continue
        out.update(flatten_inputs(value, f"{prefix}.{key}" if prefix else str(key)))
    return out


def _cost_and_reliability(project: Project, r: Any) -> dict[str, float]:
    """Purchase cost, cost per flight hour and worst motor-out T/W (NaN when they fail)."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.cost import cost  # noqa: PLC0415
    from predimrc_wrapper.reliability import motor_out  # noqa: PLC0415

    try:
        aircraft = AircraftModel(project)
        c = cost(aircraft, r.cruise[0].flight_time_s)
        return {
            "cost_purchase": c.purchase,
            "cost_per_hour": c.cost_per_hour,
            "motor_out_tw": motor_out(aircraft).worst_thrust_to_weight,
        }
    except Exception as error:  # ruff: ignore[blind-except]
        LOGGER.warning("Cost / reliability failed: %s", error)
        return dict.fromkeys(
            ("cost_purchase", "cost_per_hour", "motor_out_tw"), math.nan
        )


def two_phase_outputs(project: Project, r: Any) -> dict[str, float]:
    """The outputs ``OUTPUTS_TWO_PHASE`` of a ``TwoPhaseResult``."""
    m = r.margins
    c1, c2 = r.cruise
    values = {
        "flight_time_v1": c1.flight_time_s,
        "flight_time_v2": c2.flight_time_s,
        "range_v1": c1.range_m,
        "range_v2": c2.range_m,
        "v1": c1.v_m_s,
        "v2": c2.v_m_s,
        "hover_power": r.hover.battery_power_w,
        "cruise_power_v1": c1.battery_power_w,
        "cruise_power_v2": c2.battery_power_w,
        "mass_total": r.metadata["mass_total_kg"],
        "front_rear_ratio": r.hover.front_rear_ratio,
        "margin_motor_power": m["motor_power"],
        "margin_motor_current": m["motor_current"],
        "margin_hover_thrust": m["hover_thrust"],
        "margin_thrust_to_weight": m["thrust_to_weight"],
        "margin_battery_c": m["battery_c"],
        "margin_mass": m["mass"],
        "max_sd_rel": max(m_.power_sd_w / m_.power_w for m_ in r.hover.motors),
        **_cost_and_reliability(project, r),
        "feasible": float(r.feasible),
    }
    return {k: float(v) for k, v in values.items()}


def upgrade_outputs(outputs: dict[str, Any]) -> dict[str, float]:
    """The outputs of a stored summary under their current names, NaN when missing."""
    renamed = {OUTPUT_RENAMES.get(k, k): v for k, v in outputs.items()}
    return {
        **dict.fromkeys(OUTPUTS_TWO_PHASE, math.nan),
        **{k: math.nan if v is None else v for k, v in renamed.items()},
    }
