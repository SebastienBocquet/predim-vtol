"""Test data tab: model versus the measured flight points (REQ-DATA-006, REQ-NFR-005)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.predimrc_wrapper import AeroBackend


def calibration_rows(report: list[dict]) -> list[dict]:
    """One row per calibrated point: measured, model before / after, factor."""
    return [
        {
            "point": r["point"],
            "measured (W)": round(r["measured_w"], 1),
            "model before (W)": round(r["model_before_w"], 1),
            "model after (W)": round(r["model_after_w"], 1),
            "factor set": r["parameter"],
            "factor": round(r["factor"], 4),
            "note": r["note"],
        }
        for r in report
    ]


def compare_points(project: Project, backend: AeroBackend | None = None) -> list[dict]:
    """Battery power of the two-phase model at the conditions of each flight point (uncalibrated)."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.mission.two_phase import TwoPhaseEvaluation  # noqa: PLC0415

    rows = []
    for i, point in enumerate(project.test_data):
        p = project
        if point.altitude_m is not None:
            p = p.with_overrides({"environment.altitude_m": point.altitude_m})
        if point.temperature_c is not None:
            isa = 15.0 - 0.0065 * p.environment.altitude_m
            p = p.with_overrides({"environment.delta_isa_k": point.temperature_c - isa})
        aircraft = AircraftModel(p, aero_backend=backend, total_mass_kg=point.mass_kg)
        model = TwoPhaseEvaluation(aircraft)
        row = {
            "point": i + 1,
            "kind": point.kind,
            "date": point.date,
            "mass (kg)": round(aircraft.total_mass_kg, 3),
            "speed (km/h)": None
            if point.speed_m_s is None
            else round(3.6 * point.speed_m_s, 1),
            "measured (W)": point.battery_power_w,
        }
        try:
            if point.kind == "hover":
                h = model.hover()
                power, sd = h.battery_power_w, h.battery_power_sd_w
            else:
                cruise, _ = model.cruise((point.speed_m_s, point.speed_m_s))
                power, sd = cruise[0].battery_power_w, float("nan")
            row.update({
                "model (W)": round(power, 1),
                "deviation (%)": round(100 * (power / point.battery_power_w - 1), 1),
                "inside the 95 % band": bool(
                    abs(point.battery_power_w - power) <= 1.96 * sd
                )
                if np.isfinite(sd)
                else None,
                "error": "",
            })
        except Exception as error:  # ruff: ignore[blind-except]
            row.update({
                "model (W)": None,
                "deviation (%)": None,
                "inside the 95 % band": None,
                "error": str(error),
            })
        rows.append(row)
    return rows
