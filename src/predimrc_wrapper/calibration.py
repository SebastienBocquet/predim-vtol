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

Two-phase flight time (``calibrate_two_phase``, the calibration of the GUI): the hover power
comes from the thrust–power test data through the surrogate, not from a figure of merit.

1. Hover point → ``mission.hover_power_factor`` k_h, multiplier of the motor powers read in
   the test data (bounds 0.5–2): P_h,model(k_h) = P_h,measured at the measured mass.
2. Cruise point, with k_h applied → ``mission.drag_factor`` k_D, multiplier of the total
   cruise drag (PredimRC polar or body C_d·A, plus the drag sources; bounds 0.2–5):
   P_c,model(V, k_D) = P_c,measured. The propeller (blade elements at its pitch) and the
   motor are physics models; the residual goes to the least known term, the drag.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from predimrc_wrapper.aircraft.model import AircraftModel
from predimrc_wrapper.mission.powers import SegmentPower

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


def _power(
    project: Project,
    kind: str,
    v: float,
    mass_kg: float | None,
    backend: AeroBackend | None,
) -> float:
    aircraft = AircraftModel(project, aero_backend=backend, total_mass_kg=mass_kg)
    return float(
        SegmentPower(aircraft).evaluate({"kind": kind, "v_m_s": v})["battery_power_w"]
    )


def _scaled(
    project: Project,
    units: list[str],
    field_name: str,
    base: dict[str, float],
    k: float,
) -> Project:
    return project.with_overrides({
        f"propulsion_units.{u}.{field_name}": base[u] * k for u in units
    })


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


def calibrate(
    project: Project, backend: AeroBackend | None = None
) -> tuple[Project, CalibrationReport]:
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
            return _power(
                _scaled(current, units, "figure_of_merit", base, k),
                "hover",
                0.0,
                spec.hover.mass_kg,
                backend,
            )

        before = hover(1.0)
        k, note = _solve(
            lambda k: hover(k) - spec.hover.battery_power_w, 0.2 / top, 0.95 / top
        )
        current = _scaled(current, units, "figure_of_merit", base, k)
        report.points.append(
            CalibrationPoint(
                "hover",
                spec.hover.battery_power_w,
                before,
                hover(k),
                "figure_of_merit",
                base,
                {u: base[u] * k for u in units},
                k,
                note,
            )
        )

    if spec.cruise is not None:
        parameter = spec.cruise_parameter
        if parameter == "auto":
            parameter = (
                "propeller_efficiency"
                if current.architecture == "quadplane"
                else "drag"
            )
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
                return current.with_overrides({
                    "mission.drag_factor": base["mission"] * k
                })

            low, high, name = 0.2, 5.0, "drag_factor"

        def cruise(k: float) -> float:
            return _power(variant(k), "cruise", c.speed_m_s, c.mass_kg, backend)

        before = cruise(1.0)
        k, note = _solve(lambda k: cruise(k) - c.battery_power_w, low, high)
        current = variant(k)
        report.points.append(
            CalibrationPoint(
                "cruise",
                c.battery_power_w,
                before,
                cruise(k),
                name,
                base,
                {u: v * k for u, v in base.items()},
                k,
                note,
            )
        )
    return current, report
