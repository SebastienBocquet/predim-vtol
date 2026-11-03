"""Calibration on measured reference points (hover, cruise battery power).

Each measured point sets one factor, in this order, so that the two-phase model gives the
measured battery power at the measured mass. The hover power comes from the thrust–power test
data through the surrogate.

1. Hover point → ``mission.hover_power_factor`` k_h, multiplier of the motor powers read in
   the test data (bounds 0.5–2): P_h,model(k_h) = P_h,measured at the measured mass.
2. Cruise point, with k_h applied → ``mission.drag_factor`` k_D, multiplier of the total
   cruise drag (PredimRC polar or body C_d·A, plus the drag sources; bounds 0.2–5):
   P_c,model(V, k_D) = P_c,measured. The propeller (blade elements at its pitch) and the
   motor are physics models; the residual goes to the least known term, the drag.

A factor reaching its bound is reported (``note``): the measurement is then outside what the
model can represent and other inputs (masses, motor, battery) should be checked.

The calibration describes the reference configuration: variants (MDO) reuse its factors
instead of re-calibrating.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from predimrc_wrapper.aircraft.model import AircraftModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from predimrc_wrapper.aircraft.project import Project
    from predimrc_wrapper.predimrc_wrapper import AeroBackend


@dataclass
class CalibrationPoint:
    """Result of one reference point."""

    point: str
    measured_w: float
    model_before_w: float
    model_after_w: float
    parameter: str
    values_before: dict[str, float]
    values_after: dict[str, float]
    factor: float
    note: str = ""


@dataclass
class CalibrationReport:
    """All the calibrated points."""

    points: list[CalibrationPoint] = field(default_factory=list)

    def to_dict(self) -> list[dict]:
        return [asdict(p) for p in self.points]


def _solve(
    residual: Callable[[float], float], low: float, high: float
) -> tuple[float, str]:
    """Root of a monotonic residual on [low, high] (Brent's method); the closest bound otherwise."""
    from scipy.optimize import brentq  # noqa: PLC0415

    r_low, r_high = residual(low), residual(high)
    if r_low * r_high > 0:
        bound = low if abs(r_low) < abs(r_high) else high
        return bound, "factor at its bound: measurement outside the model range"
    if r_low == 0.0:  # noqa: RUF069 - exact root at a bound
        return low, ""
    if r_high == 0.0:  # noqa: RUF069 - exact root at a bound
        return high, ""
    return float(brentq(residual, low, high, xtol=1e-12, rtol=1e-12)), ""


def _two_phase_power(
    project: Project,
    kind: str,
    v: float,
    mass_kg: float | None,
    backend: AeroBackend | None,
) -> float:
    from predimrc_wrapper.mission.two_phase import TwoPhaseEvaluation  # noqa: PLC0415

    model = TwoPhaseEvaluation(
        AircraftModel(project, aero_backend=backend, total_mass_kg=mass_kg)
    )
    if kind == "hover":
        return model.hover().battery_power_w
    cruise, _ = model.cruise((v, v))
    return cruise[0].battery_power_w


def calibrate_two_phase(
    project: Project, backend: AeroBackend | None = None
) -> tuple[Project, CalibrationReport]:
    """Calibrated copy of a project for the two-phase flight time, and the report.

    Args:
        project: The reference project, with a ``calibration`` block.
        backend: The aero backend (wing-borne cruise point).
    """
    spec = project.calibration
    report = CalibrationReport()
    if spec is None:
        return project, report
    current = project.with_overrides({"calibration": None})
    for point, ref, field_name, low, high in (
        ("hover", spec.hover, "hover_power_factor", 0.5, 2.0),
        ("cruise", spec.cruise, "drag_factor", 0.2, 5.0),
    ):
        if ref is None:
            continue
        base = getattr(current.mission, field_name)
        speed = getattr(ref, "speed_m_s", 0.0)
        reference = current

        def model(k: float) -> float:
            variant = reference.with_overrides({f"mission.{field_name}": base * k})  # noqa: B023
            return _two_phase_power(variant, point, speed, ref.mass_kg, backend)  # noqa: B023

        before = model(1.0)
        if not math.isfinite(before):
            mass = "the project mass" if ref.mass_kg is None else f"{ref.mass_kg:g} kg"
            msg = (
                f"calibration {point} point: the model gives no power at {mass}"
                " (beyond the motors, propellers or battery); check the mass, in kg"
            )
            raise ValueError(msg)
        k, note = _solve(lambda k: model(k) - ref.battery_power_w, low, high)  # noqa: B023
        current = current.with_overrides({f"mission.{field_name}": base * k})
        report.points.append(
            CalibrationPoint(
                point,
                ref.battery_power_w,
                before,
                model(k),
                field_name,
                {"mission": base},
                {"mission": base * k},
                k,
                note,
            )
        )
    return current, report
