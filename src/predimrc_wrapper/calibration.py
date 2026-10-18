"""Calibration on measured reference points (hover, cruise battery power).

Strategy: each measured point sets one factor, in this order, so that the model gives
the measured battery power at the measured mass:

1. Hover point → figure of merit of the lift propellers. All lift and tilt unit types are
   multiplied by the same factor (FM ≤ 0.95). The hover power gathers the propeller,
   motor and ESC losses; the motor and ESC models come from data sheets, so the residual
   is put on the least known term, the propeller.
2. Cruise point, with the hover factor applied →
   - wing-borne aircraft (``auto`` or ``propeller_efficiency``): cruise propulsive
     efficiency η_c of the cruise and tilt unit types (η_c ≤ 0.95); the PredimRC polar is
     kept;
   - multicopter (``auto``) or ``drag``: the mission drag factor (multiplier of the
     total drag, PredimRC polar or body CdS and drag sources).

One point cannot separate drag and propeller efficiency: with a wing-borne aircraft
choose ``drag`` when the propeller is known (pitch study, bench test) and the airframe
drag is not. A factor reaching its bound is reported (``note``): the measurement is then
outside what the model can represent and other inputs (masses, motor, battery) should
be checked.

The calibration describes the reference configuration: variants (MDO) reuse its factors
instead of re-calibrating.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from predimrc_wrapper.aircraft.model import AircraftModel
from predimrc_wrapper.mission.powers import SegmentPower

if TYPE_CHECKING:
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


def _solve(residual: Callable[[float], float], low: float, high: float) -> tuple[float, str]:
    """Root of a monotonic residual on [low, high] by bisection; the closest bound otherwise."""
    r_low, r_high = residual(low), residual(high)
    if r_low * r_high > 0:
        bound = low if abs(r_low) < abs(r_high) else high
        return bound, "factor at its bound: measurement outside the model range"
    for _ in range(60):
        mid = 0.5 * (low + high)
        r_mid = residual(mid)
        if r_low * r_mid <= 0:
            high = mid
        else:
            low, r_low = mid, r_mid
    return 0.5 * (low + high), ""


def _power(project: Project, kind: str, v: float, mass_kg: float | None, backend: AeroBackend | None) -> float:
    aircraft = AircraftModel(project, aero_backend=backend, total_mass_kg=mass_kg)
    return float(SegmentPower(aircraft).evaluate({"kind": kind, "v_m_s": v})["battery_power_w"])


def _scaled(project: Project, units: list[str], field_name: str, base: dict[str, float], k: float) -> Project:
    return project.with_overrides({f"propulsion_units.{u}.{field_name}": base[u] * k for u in units})


def calibrate(project: Project, backend: AeroBackend | None = None) -> tuple[Project, CalibrationReport]:
    """Calibrated copy of a project (``calibration`` block removed) and the report.

    Args:
        project: The reference project, with a ``calibration`` block.
        backend: The aero backend (wing-borne cruise point).
    """
    spec = project.calibration
    report = CalibrationReport()
    if spec is None:
        return project, report
    current = project.with_overrides({"calibration": None})

    if spec.hover is not None:
        units = sorted({m.unit for m in current.lift_motors()})
        base = {u: current.propulsion_units[u].figure_of_merit for u in units}
        top = max(base.values())

        def hover(k: float) -> float:
            return _power(_scaled(current, units, "figure_of_merit", base, k), "hover", 0.0, spec.hover.mass_kg, backend)

        before = hover(1.0)
        k, note = _solve(lambda k: hover(k) - spec.hover.battery_power_w, 0.2 / top, 0.95 / top)
        current = _scaled(current, units, "figure_of_merit", base, k)
        report.points.append(CalibrationPoint(
            "hover", spec.hover.battery_power_w, before, hover(k), "figure_of_merit", base,
            {u: base[u] * k for u in units}, k, note))

    if spec.cruise is not None:
        parameter = spec.cruise_parameter
        if parameter == "auto":
            parameter = "propeller_efficiency" if current.architecture == "quadplane" else "drag"
        c = spec.cruise
        if parameter == "propeller_efficiency":
            if current.architecture != "quadplane":
                msg = "The propeller efficiency is calibrated on a wing-borne aircraft only: use 'drag'."
                raise ValueError(msg)
            units = sorted({m.unit for m in current.cruise_motors()})
            base = {u: current.propulsion_units[u].cruise_efficiency for u in units}
            top = max(base.values())

            def variant(k: float) -> Project:
                return _scaled(current, units, "cruise_efficiency", base, k)

            low, high, name = 0.1 / top, 0.95 / top, "cruise_efficiency"
        else:
            base = {"mission": current.mission.drag_factor}

            def variant(k: float) -> Project:
                return current.with_overrides({"mission.drag_factor": base["mission"] * k})

            low, high, name = 0.2, 5.0, "drag_factor"

        def cruise(k: float) -> float:
            return _power(variant(k), "cruise", c.speed_m_s, c.mass_kg, backend)

        before = cruise(1.0)
        k, note = _solve(lambda k: cruise(k) - c.battery_power_w, low, high)
        current = variant(k)
        report.points.append(CalibrationPoint(
            "cruise", c.battery_power_w, before, cruise(k), name, base, {u: v * k for u, v in base.items()}, k, note))
    return current, report
