"""Aircraft model: turns a project into masses, propulsion units and drag."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.aircraft.aero import AeroModel
from predimrc_wrapper.aircraft.drag import DragModel
from predimrc_wrapper.aircraft.mass import MassBudget
from predimrc_wrapper.aircraft.project import ProjectError
from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.core.units import INCH
from predimrc_wrapper.core.units import MM
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import default_database
from predimrc_wrapper.propulsion import BatteryModel
from predimrc_wrapper.propulsion import MomentumPropeller
from predimrc_wrapper.propulsion import MotorModel
from predimrc_wrapper.propulsion import PropulsionUnit
from predimrc_wrapper.propulsion import density

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import MotorSlot
    from predimrc_wrapper.aircraft.project import Project
    from predimrc_wrapper.aircraft.project import PropulsionSpec
    from predimrc_wrapper.predimrc_wrapper import AeroBackend

ROLE_CATEGORY = {
    "lift": "lift propulsion",
    "cruise": "cruise propulsion",
    "tilt": "tilt propulsion",
}


def hover_thrust_split(
    x_m: np.ndarray,
    y_m: np.ndarray,
    area_m2: np.ndarray,
    cg_m: tuple[float, float] | None = None,
) -> np.ndarray:
    """Fractions of the hover thrust carried by each lift rotor (sum 1).

    Minimises Σ T_i² / A_i (close to the minimum induced power) under the vertical force
    balance and, when the CG is given, the pitch and roll moment balances. Without CG the
    thrust is shared in proportion to the disc areas.

    Raises:
        ProjectError: When a rotor would need a negative thrust (CG outside the rotors).
    """
    area = np.asarray(area_m2, dtype=float)
    if cg_m is None:
        return area / area.sum()
    m = np.vstack([
        np.ones_like(area),
        np.asarray(x_m, dtype=float),
        np.asarray(y_m, dtype=float),
    ])
    b = np.array([1.0, cg_m[0], cg_m[1]])
    weighted = m * area
    lam = np.linalg.lstsq(weighted @ m.T, b, rcond=None)[0]
    fractions = area * (m.T @ lam)
    if not np.allclose(m @ fractions, b, atol=1e-9):
        msg = "The CG cannot be balanced by the lift rotors (all rotors aligned with an offset CG)."
        raise ProjectError(msg)
    if np.any(fractions <= 0.0):
        msg = (
            f"CG ({1000 * cg_m[0]:.0f}, {1000 * cg_m[1]:.0f}) mm outside the polygon of the lift rotors: "
            f"thrust fractions {np.round(fractions, 3).tolist()}."
        )
        raise ProjectError(msg)
    return fractions


class AircraftModel:
    """Physical view of a project.

    Args:
        project: The project.
        db: The motor database (default: shipped one).
        aero_backend: The PredimRC backend, required to compute the quadplane drag.
        total_mass_kg: A mass replacing the mass budget (calibration points measured at
            another mass).
    """

    def __init__(
        self,
        project: Project,
        db: MotorDatabase | None = None,
        aero_backend: AeroBackend | None = None,
        total_mass_kg: float | None = None,
    ) -> None:
        self.project = project
        self.db = db or default_database()
        self.wing_borne = project.architecture == "quadplane"
        self.aero = (
            AeroModel(project.aero, aero_backend, project.environment)
            if (self.wing_borne and aero_backend is not None)
            else None
        )
        self.drag_model = DragModel()
        self.battery = self._battery()
        self._board_units: dict[str, PropulsionUnit] = {}
        self.units: dict[str, PropulsionUnit] = {
            name: self._unit(spec) for name, spec in project.propulsion_units.items()
        }
        self.rho = density(
            project.environment.altitude_m, project.environment.delta_isa_k
        )
        self.mass = self._mass()
        if total_mass_kg is not None:
            self.mass["total_kg"] = total_mass_kg
        self.lift_motors: list[MotorSlot] = project.lift_motors()
        self.cruise_motors: list[MotorSlot] = (
            project.cruise_motors() if self.wing_borne else []
        )
        self.hover_fractions = hover_thrust_split(
            np.array([m.x_mm * MM for m in self.lift_motors]),
            np.array([m.y_mm * MM for m in self.lift_motors]),
            np.array([self.disc_area_m2(m) for m in self.lift_motors]),
            None
            if project.cg_x_mm is None
            else (project.cg_x_mm * MM, project.cg_y_mm * MM),
        )

    # --- components ----------------------------------------------------------

    def _battery(self) -> BatteryModel:
        spec = self.project.battery
        if spec.mode == "mass":
            return BatteryModel.from_mass(
                spec.chemistry, spec.n_series, spec.mass_g / 1000.0
            )
        return BatteryModel.from_capacity(
            spec.chemistry, spec.n_series, spec.capacity_mah
        )

    def _unit(
        self, spec: PropulsionSpec, esc_efficiency: float | None = None
    ) -> PropulsionUnit:
        motor = self.db.motor(spec.motor_id).model_parameters()
        if spec.motor_mass_g is not None:
            motor["mass_kg"] = spec.motor_mass_g / 1000.0
        return PropulsionUnit(
            MotorModel(**motor),
            MomentumPropeller(
                diameter_m=spec.prop_diameter_in * INCH,
                mass_kg=spec.prop_mass_g / 1000.0,
                figure_of_merit=spec.figure_of_merit,
                static_ct=spec.static_ct,
                cruise_efficiency=spec.cruise_efficiency,
            ),
            esc_efficiency=spec.esc_efficiency
            if esc_efficiency is None
            else esc_efficiency,
            esc_mass_kg=(spec.esc_mass_g or 0.0) / 1000.0,
        )

    def unit_of(self, motor: MotorSlot) -> PropulsionUnit:
        """The propulsion unit model of a motor, with the 4-in-1 efficiency when the board drives it."""
        if not self.project.on_four_in_one(motor):
            return self.units[motor.unit]
        if motor.unit not in self._board_units:
            self._board_units[motor.unit] = self._unit(
                self.project.propulsion_units[motor.unit],
                self.project.wiring.four_in_one_efficiency,
            )
        return self._board_units[motor.unit]

    def disc_area_m2(self, motor: MotorSlot) -> float:
        """Propeller disc area of a motor (m²)."""
        return (
            np.pi
            * (self.project.propulsion_units[motor.unit].prop_diameter_in * INCH) ** 2
            / 4.0
        )

    def _mass(self) -> dict:
        p = self.project
        from predimrc_wrapper.propulsion.wiring import wiring_mass_kg  # noqa: PLC0415

        four_in_one = (
            [("lift propulsion", p.wiring.four_in_one_mass_g / 1000.0)]
            if p.wiring is not None and p.wiring.lift_esc == "four_in_one"
            else []
        )
        return MassBudget().evaluate({
            "mass_items": [(i.category, i.mass_g / 1000.0) for i in p.mass_items]
            + [("wiring", wiring_mass_kg(p))],
            "propulsion_items": [
                (ROLE_CATEGORY[m.role], self._motor_mass_kg(m)) for m in p.motors
            ]
            + four_in_one,
            "battery_mass_kg": self.battery.p.mass_kg,
            "max_takeoff_mass_kg": p.max_takeoff_mass_kg,
        })

    def _motor_mass_kg(self, motor: MotorSlot) -> float:
        """Motor + propeller, + its ESC unless the 4-in-1 board drives it (kg)."""
        unit = self.units[motor.unit]
        if self.project.on_four_in_one(motor):
            return unit.mass_kg - unit.p.esc_mass_kg
        return unit.mass_kg

    # --- derived quantities --------------------------------------------------

    @property
    def total_mass_kg(self) -> float:
        """Total mass (kg)."""
        return self.mass["total_kg"]

    @property
    def n_lift(self) -> int:
        """Number of lift rotors (role lift or tilt)."""
        return len(self.lift_motors)

    @property
    def download_factor(self) -> float:
        """Hover thrust / weight."""
        value = self.project.mission.download_factor
        return value if value is not None else (1.05 if self.wing_borne else 1.0)

    def hover_loads(
        self, total_thrust_n: float | np.ndarray
    ) -> list[tuple[PropulsionUnit, np.ndarray]]:
        """(unit, thrust) of each lift rotor for a total vertical thrust."""
        return [
            (self.unit_of(m), f * np.asarray(total_thrust_n, dtype=float))
            for m, f in zip(self.lift_motors, self.hover_fractions, strict=False)
        ]

    def cruise_loads(
        self, thrust_n: np.ndarray
    ) -> list[tuple[PropulsionUnit, np.ndarray]]:
        """(unit, thrust) of each cruise motor of a wing-borne aircraft, shared by disc area."""
        areas = np.array([self.disc_area_m2(m) for m in self.cruise_motors])
        return [
            (self.unit_of(m), a / areas.sum() * np.asarray(thrust_n, dtype=float))
            for m, a in zip(self.cruise_motors, areas, strict=False)
        ]

    def lift_thrust_to_weight(self) -> float:
        """Largest total lift thrust keeping the hover split, over the weight, at nominal voltage."""
        v0 = self.battery.open_circuit_voltage
        cache: dict[str, float] = {}
        limits = []
        for m, f in zip(self.lift_motors, self.hover_fractions, strict=False):
            if m.unit not in cache:
                cache[m.unit] = self.unit_of(m).max_thrust(self.rho, v0)
            limits.append(cache[m.unit] / f)
        return min(limits) / (self.total_mass_kg * GRAVITY)

    def drag_sources(self) -> list[dict]:
        """Dedicated drag sources in SI, the booms of ``project.booms`` first."""
        from predimrc_wrapper.aircraft.booms import boom_drag  # noqa: PLC0415
        from predimrc_wrapper.aircraft.drag_sources import source_cds  # noqa: PLC0415

        out = [
            {"kind": "cds", "count": 1, "cds_m2": b.cds_m2}
            for b in boom_drag(
                self.project, self.drag_model.p.boom_cf, self.drag_model.p.boom_cd_end
            )
        ]
        for s in self.project.drag_sources:
            if s.kind in ("v_arms", "body_part"):
                out.append({
                    "kind": "cds",
                    "count": 1,
                    "cds_m2": source_cds(s, self.project, self.drag_model).cds_m2,
                })
                continue
            out.append({
                "kind": s.kind,
                "count": s.count,
                "n_blades": s.n_blades,
                "blade_position": s.blade_position,
                "diameter_m": (s.diameter_mm or 0) * MM,
                "length_m": (s.length_mm or 0) * MM,
                "blade_chord_m": (s.blade_chord_mm or 0) * MM,
                "radius_m": (s.radius_mm or 0) * MM,
                "cds_m2": s.cds_m2 or 0.0,
            })
        return out

    def drag(self, v_m_s: np.ndarray | float) -> dict:
        """Total drag at the flight density and total mass, times the mission drag factor.

        Raises:
            ProjectError: For a quadplane without PredimRC backend.
        """
        x = {"sources": self.drag_sources(), "v_m_s": v_m_s, "rho": self.rho}
        if self.wing_borne:
            if self.aero is None:
                msg = "A quadplane needs a PredimRC backend to compute its drag."
                raise ProjectError(msg)
            x["polar"] = self.aero.polar(self.total_mass_kg)
        else:
            x["body_cds_m2"] = self.project.body_drag()[0]
        y = self.drag_model.evaluate(x)
        y["drag_n"] = self.project.mission.drag_factor * y["drag_n"]
        return y

    def rotor_positions_m(self) -> list[tuple[float, float]]:
        """Lift rotor positions (x: station aft-positive from the wing LE / centre, y right), metres."""
        return [(m.x_mm * MM, m.y_mm * MM) for m in self.lift_motors]
