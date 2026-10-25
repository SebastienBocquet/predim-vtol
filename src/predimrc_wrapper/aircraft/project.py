"""Project file: all inputs of one design, as a validated pydantic model.

Field levels (``json_schema_extra["level"]``) drive the GUI forms: ``required``,
``default`` (optional, default shown) or ``advanced`` (collapsed). User units are in the
field names (``_mm``, ``_g``, ``_mah``, ``_in``); models work in SI.
"""

from __future__ import annotations

import copy
import difflib
from importlib.resources import files
from pathlib import Path
from typing import Any
from typing import Literal

import yaml
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from predimrc_wrapper.mission.scenario import Scenario

FORMAT_VERSION = 2


class ProjectError(ValueError):
    """An inconsistent project."""


class OverrideError(ValueError):
    """An unknown override path."""


def req(**kw: Any) -> Any:
    """A required field."""
    return Field(json_schema_extra={"level": "required"}, **kw)


def opt(default: Any, **kw: Any) -> Any:
    """An optional field whose default is shown."""
    return Field(default=default, json_schema_extra={"level": "default"}, **kw)


def adv(default: Any, **kw: Any) -> Any:
    """An advanced field, collapsed in the GUI."""
    return Field(default=default, json_schema_extra={"level": "advanced"}, **kw)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class WingSpec(_Strict):
    """Wing, up to 5 panels (PredimRC units)."""

    root_chord_mm: float = req(gt=0, description="Root chord (mm)")
    tip_chord_mm: list[float] = req(
        min_length=1, max_length=5, description="Tip chord per panel (mm)"
    )
    length_mm: list[float] = req(
        min_length=1, max_length=5, description="Span length per panel (mm)"
    )
    le_offset_mm: list[float] = req(
        min_length=1,
        max_length=5,
        description="Leading-edge offset per panel, 'Flèche /BA' (mm)",
    )
    twist_deg: list[float] = req(
        min_length=1, max_length=5, description="Twist per panel (deg)"
    )
    dihedral_deg: list[float] = req(
        min_length=1, max_length=5, description="Dihedral per panel (deg)"
    )

    @model_validator(mode="after")
    def _same_length(self) -> WingSpec:
        n = {
            len(self.tip_chord_mm),
            len(self.length_mm),
            len(self.le_offset_mm),
            len(self.twist_deg),
            len(self.dihedral_deg),
        }
        if len(n) != 1:
            msg = "All wing panel lists must have the same length."
            raise ValueError(msg)
        return self


class StabSpec(_Strict):
    """Horizontal stabiliser (PredimRC units and labels)."""

    root_chord_mm: float = req(gt=0, description="Root chord (mm)")
    tip_chord_mm: list[float] = req(
        min_length=1, max_length=5, description="Tip chord per panel (mm)"
    )
    length_mm: list[float] = req(
        min_length=1, max_length=5, description="Length per panel (mm)"
    )
    le_offset_mm: list[float] = req(
        min_length=1, max_length=5, description="Leading-edge offset per panel (mm)"
    )
    lever_mm: float = req(gt=0, description="Stabiliser lever (mm)")
    height_mm: float = opt(0.0, description="Stabiliser height (mm)")
    profile: str = opt(
        "Biconvexe fin", description="Stabiliser airfoil (PredimRC label)"
    )
    opening: str = opt(
        "--- / 180", description="V-tail opening (PredimRC label; '--- / 180' = flat)"
    )
    lateral_gap_mm: float = opt(0.0, ge=0, description="Lateral gap (mm)")


class FuselageSpec(_Strict):
    """Fuselage (PredimRC units and labels)."""

    length_mm: float = req(gt=0, description="Length (mm)")
    width_mm: float = req(gt=0, description="Width (mm)")
    height_mm: float = req(gt=0, description="Height (mm)")
    nose_lever_mm: float = req(gt=0, description="Nose lever (mm)")
    shape: str = opt("Profilée", description="Shape (PredimRC label)")
    beam: str = opt("Normale", description="Tail beam (PredimRC label)")
    wing_pos: str = opt("médiane", description="Wing position (PredimRC label)")
    incidence: str = opt("aile", description="Linked incidence (PredimRC label)")


class AeroSpec(_Strict):
    """Wing-borne aerodynamics, evaluated by PredimRC."""

    profile: str = opt(
        "SD7003",
        min_length=1,
        description="Wing airfoil: PredimRC workbook PredimRC_<profile>.xls of the PredimRC folder",
    )
    wing: WingSpec = req(description="Wing panels (PredimRC Aile block)")
    stab: StabSpec = req(
        description="Horizontal stabiliser (PredimRC Stabilisateur block)"
    )
    fuselage: FuselageSpec = req(description="Fuselage (PredimRC Fuselage block)")
    static_margin_pct: float = opt(
        5.0, ge=0, le=50, description="Static margin (% of MAC)"
    )
    cz_reg: float = adv(
        0.30, gt=0, le=1.5, description="Trim lift coefficient, multiple of 0.05"
    )


class PropulsionSpec(_Strict):
    """A propulsion unit type: motor, propeller and ESC. Motors reference it by name."""

    motor_id: str = req(description="Motor id in the database")
    motor_mass_g: float | None = opt(
        None,
        gt=0,
        description="Motor mass (g); empty: the mass of the motor database",
    )
    propeller_id: str | None = opt(
        None,
        description="Propeller id in the database (diameter and pitch must match it)",
    )
    prop_diameter_in: float = req(gt=0, le=40, description="Propeller diameter (in)")
    prop_pitch_in: float | None = opt(
        None, gt=0, le=40, description="Propeller pitch (in), used by the pitch study"
    )
    prop_mass_g: float = opt(25.0, gt=0, description="Propeller mass (g)")
    esc_mass_g: float | None = opt(
        None,
        ge=0,
        description="Mass of one separate ESC (g); needed when this unit has separate ESCs",
    )
    esc_efficiency: float = adv(0.95, gt=0, le=1, description="ESC efficiency")
    figure_of_merit: float = adv(0.65, gt=0, lt=1, description="Hover figure of merit")
    static_ct: float = adv(0.10, gt=0, description="Static thrust coefficient")
    cruise_efficiency: float = adv(
        0.70, gt=0, le=1, description="Cruise propulsive efficiency"
    )

    @model_validator(mode="after")
    def _propeller(self) -> PropulsionSpec:
        if self.propeller_id is None:
            return self
        from predimrc_wrapper.data import default_propellers  # noqa: PLC0415

        try:
            prop = default_propellers().propeller(self.propeller_id)
        except KeyError as error:
            raise ValueError(error.args[0]) from None
        if abs(prop.diameter_in - self.prop_diameter_in) > 1e-9:
            msg = f"Propeller {prop.id} has a diameter of {prop.diameter_in:g} in, not {self.prop_diameter_in:g} in."
            raise ValueError(msg)
        if self.prop_pitch_in is None:
            object.__setattr__(self, "prop_pitch_in", prop.pitch_in)
        elif abs(prop.pitch_in - self.prop_pitch_in) > 1e-9:
            msg = f"Propeller {prop.id} has a pitch of {prop.pitch_in:g} in, not {self.prop_pitch_in:g} in."
            raise ValueError(msg)
        return self


MotorRole = Literal["lift", "cruise", "tilt"]
"""lift: vertical flight only; cruise: forward flight only; tilt: both (tilting motor)."""

LIFT_ROLES = ("lift", "tilt")
CRUISE_ROLES = ("cruise", "tilt")


class MotorSlot(_Strict):
    """One motor at the end of an arm or boom (no coaxial pairs); numbered by its position in the list."""

    unit: str = req(description="Propulsion unit type (name in propulsion_units)")
    role: MotorRole = req(
        description="lift, cruise or tilt (lift and cruise, tilting motor)"
    )
    x_mm: float = req(
        description="Station, aft-positive from the reference: wing root LE or frame centre (mm)"
    )
    y_mm: float = req(description="Lateral position, right-positive (mm)")
    spin: Literal["cw", "ccw"] | None = adv(
        None,
        description="Propeller rotation seen from above (yaw balance of the motor-out check); alternating around the frame when not set",
    )


class BoomSpec(_Strict):
    """Booms carrying the lift motors, set in the configuration tab (REQ-CFG-014)."""

    layout: Literal["parallel", "diagonal"] = req(
        description=(
            "parallel: booms along the flow carrying the off-centreline lift motors (quadplane); "
            "diagonal: one straight boom per lift motor from an anchor under the fuselage"
        )
    )
    section: Literal["round", "square", "profiled"] = opt(
        "round",
        description="Boom section: round tube, square tube, profiled (streamlined)",
    )
    thickness_mm: float = opt(
        16.0,
        gt=0,
        description="Boom thickness seen by the flow (mm): diameter, side or profile thickness",
    )
    chord_mm: float | None = opt(
        None,
        gt=0,
        description="Chord of a profiled section (mm); 4 × thickness when not set",
    )
    anchor_x_mm: float | None = opt(
        None,
        description="Diagonal booms: anchor station (mm); wing quarter chord or frame centre when not set",
    )
    anchor_half_width_mm: float | None = opt(
        None,
        ge=0,
        description="Diagonal booms: half distance between the left and right anchors (mm); fuselage half width when not set",
    )
    anchor_z_mm: float | None = opt(
        None,
        description="Diagonal booms: anchor height (mm, up-positive); under the fuselage (or 0 for a frame) when not set",
    )
    motor_z_mm: float = opt(0.0, description="Height of the motors on the booms (mm)")


class CostSpec(_Strict):
    """Prices entered and wear assumptions (REQ-COST-001, REQ-COST-002)."""

    frame: float = opt(
        0.0,
        ge=0,
        description="Frame price: airframe, booms, fuselage (EUR)",
    )
    avionics: float = opt(
        0.0, ge=0, description="Avionics price: flight controller, GPS, receiver (EUR)"
    )
    overrides: dict[str, float] = opt(
        {},
        description=(
            "Prices replacing the database (EUR): keys motor:<id>, propeller:<id>, esc, esc4in1, "
            "battery_per_wh, cable:<awg>"
        ),
    )
    usd_per_eur: float | None = adv(
        None,
        gt=0,
        description="Exchange rate (USD per EUR) of the database prices; ECB rate of the price list when not set",
    )
    battery_cycles: int | None = opt(
        None,
        gt=0,
        description="Battery cycle life (cycles); 300 for LiPo, 500 for Li-ion when not set",
    )
    motor_life_h: float = opt(
        1000.0, gt=0, description="Motor life before replacement (flight hours)"
    )
    propeller_flights: int = opt(
        200,
        gt=0,
        description="Flights between propeller replacements (wear, small damage)",
    )


class BatterySpec(_Strict):
    """Battery pack, defined by its mass or its capacity."""

    chemistry: Literal["lipo", "li-ion"] = req(description="Cell chemistry")
    n_series: int = req(ge=1, le=14, description="Cells in series")
    mode: Literal["mass", "capacity"] = opt(
        "mass",
        description=(
            "Battery defined by: its mass (the capacity follows from the specific energy of the "
            "chemistry) or its capacity (the mass follows)"
        ),
    )
    mass_g: float | None = opt(None, gt=0, description="Pack mass (g), mass mode")
    capacity_mah: float | None = opt(
        None, gt=0, description="Pack capacity (mAh), capacity mode"
    )

    @model_validator(mode="after")
    def _given(self) -> BatterySpec:
        if self.mode == "mass" and self.mass_g is None:
            msg = "battery.mass_g is required in mass mode."
            raise ValueError(msg)
        if self.mode == "capacity" and self.capacity_mah is None:
            msg = "battery.capacity_mah is required in capacity mode."
            raise ValueError(msg)
        return self


class MassItem(_Strict):
    """A user mass item."""

    name: str = req(description="Item name")
    category: Literal["airframe", "vtol_structure", "payload", "avionics", "other"] = (
        req(description="Category")
    )
    mass_g: float = req(ge=0, description="Mass (g)")


class DragSource(_Strict):
    """A dedicated parasitic drag source, active in cruise."""

    name: str = req(description="Source name")
    kind: Literal["boom", "stopped_rotor", "v_arms", "body_part", "cds"] = req(
        description="Kind: boom, stopped rotor, V-arms (motor arms under the fuselage), body part (shape + frontal area), free CdS"
    )
    count: int = opt(1, ge=1, description="Number of identical items")
    diameter_mm: float | None = opt(None, gt=0, description="Boom diameter (mm)")
    length_mm: float | None = opt(None, gt=0, description="Boom exposed length (mm)")
    n_blades: int = opt(2, ge=1, description="Blades per stopped rotor")
    blade_chord_mm: float | None = opt(None, gt=0, description="Mean blade chord (mm)")
    radius_mm: float | None = opt(None, gt=0, description="Rotor radius (mm)")
    cds_m2: float | None = opt(None, ge=0, description="Drag area CdS (m²), kind cds")
    shape: str | None = opt(
        None,
        description="Shape as in PredimRC: Profilé, Mixte, Non profilé (v_arms, body_part)",
    )
    frontal_area_dm2: float | None = opt(
        None,
        ge=0,
        description="Frontal area (dm²); v_arms: from the geometry when not set",
    )
    thickness_mm: float | None = opt(
        None, gt=0, description="Arm thickness seen by the flow (mm), v_arms"
    )
    attach_x_mm: float | None = opt(
        None,
        description="Arm attachment station (mm), v_arms; default wing quarter chord / frame centre",
    )
    attach_z_mm: float | None = opt(
        None,
        description="Arm attachment height (mm), v_arms; default under the fuselage",
    )
    attach_half_width_mm: float | None = opt(
        None, ge=0, description="Half distance between the arm roots (mm), v_arms"
    )
    motor_z_mm: float = opt(0.0, description="Height of the motors (mm), v_arms")
    motors: list[int] | None = opt(
        None,
        description="Motors carried by V-arms (0-based); all lift motors when not set",
    )

    @model_validator(mode="after")
    def _kind_params(self) -> DragSource:
        needed = {
            "boom": ("diameter_mm", "length_mm"),
            "stopped_rotor": ("blade_chord_mm", "radius_mm"),
            "cds": ("cds_m2",),
            "v_arms": ("shape", "thickness_mm"),
            "body_part": ("shape", "frontal_area_dm2"),
        }[self.kind]
        missing = [k for k in needed if getattr(self, k) is None]
        if missing:
            msg = f"Drag source '{self.name}' ({self.kind}) needs {missing}."
            raise ValueError(msg)
        if self.shape is not None:
            from predimrc_wrapper.data.drag_shapes import drag_shapes  # noqa: PLC0415

            if self.shape not in drag_shapes():
                msg = f"Drag source '{self.name}': unknown shape '{self.shape}'. Known: {list(drag_shapes())}"
                raise ValueError(msg)
        return self


class EnvironmentSpec(_Strict):
    """Flight conditions."""

    altitude_m: float = opt(0.0, ge=0, le=11000, description="Pressure altitude (m)")
    delta_isa_k: float = adv(
        0.0, ge=-40, le=40, description="Temperature offset to ISA (K)"
    )


class MissionSettings(_Strict):
    """Mission settings and simplified-model factors."""

    reserve_fraction: float = opt(
        0.20,
        ge=0,
        le=0.5,
        description=(
            "Energy reserve: fraction of the nominal energy kept at landing (two-phase flight time; "
            "of the usable energy in the scenario mode of the Python API)"
        ),
    )
    hover_time_s: float = opt(
        60.0,
        ge=0,
        description="Hover time at the transition altitude, before the transition (s)",
    )
    transition_altitude_m: float = opt(
        30.0,
        ge=0,
        description="Transition altitude (m): vertical climb to it, vertical descent from it",
    )
    vertical_climb_speed_m_s: float = opt(
        2.0, gt=0, description="Vertical climb speed to the transition altitude (m/s)"
    )
    vertical_descent_speed_m_s: float = opt(
        1.5,
        gt=0,
        description="Vertical descent speed from the transition altitude (m/s)",
    )
    transition_time_s: float = opt(
        15.0,
        ge=0,
        description="Duration of the transition from hover to cruise (s), winged aircraft",
    )
    transition_tilt_deg: float = opt(
        60.0,
        gt=0,
        le=90,
        description=(
            "Tilt angle of the tilting motors during the transition, from the horizontal (°): "
            "90° = vertical; a tilting motor gives T·sin θ vertically"
        ),
    )
    target_speeds_m_s: list[float] | None = opt(
        None,
        min_length=2,
        max_length=2,
        description=(
            "Cruise target speeds [V1, V2] (m/s); default: minimum aerodynamic power and maximum L/D speeds"
        ),
    )
    min_thrust_to_weight: float = opt(
        1.5, ge=1, description="Minimum lift thrust-to-weight"
    )
    avionics_power_w: float = opt(
        5.0, ge=0, description="Avionics and payload power (W)"
    )
    download_factor: float | None = adv(
        None,
        ge=1,
        description="Hover thrust / weight (default 1.05 quadplane, 1.0 multicopter)",
    )
    transition_factor: float = adv(
        1.0, gt=0, description="Transition power / hover power"
    )
    stall_margin: float = adv(
        1.2, ge=1, description="Minimum cruise speed / minimum polar speed"
    )
    speed_step: float = adv(0.25, gt=0, description="Speed sweep step (m/s)")
    drag_factor: float = adv(
        1.0,
        gt=0,
        description="Multiplier of the total cruise drag (set by the calibration)",
    )
    hover_power_factor: float = adv(
        1.0,
        gt=0,
        description="Multiplier of the hover motor powers read in the test data (set by the calibration)",
    )


class SizingSpec(_Strict):
    """Pre-selection of the motors: hover power law P = P_ref·(m / m_ref)^k on a target mass range."""

    target_mass_kg: list[float] = req(
        min_length=2,
        max_length=2,
        description="Target take-off mass range [min, max] (kg)",
    )
    reference_mass_kg: float = opt(
        1.87, gt=0, description="Mass of the reference aircraft (kg)"
    )
    reference_hover_power_w: float = opt(
        280.0, gt=0, description="Measured hover battery power of the reference (W)"
    )
    mass_exponent: float = adv(
        1.0,
        gt=0,
        le=2,
        description="Exponent k (1: propellers scale with the mass, 1.5: same propellers)",
    )
    headroom: float = adv(
        1.3, ge=1, description="Largest accepted motor power / needed power"
    )
    cruise_max_speed_m_s: float = opt(
        25.0, gt=0, description="Maximum cruise speed (m/s), cruise motors"
    )
    cruise_lift_to_drag: float = adv(
        8.0, gt=0, description="Lift-to-drag ratio at maximum speed, cruise motors"
    )
    cruise_overall_efficiency: float = adv(
        0.5, gt=0, le=1, description="Propeller × motor × ESC efficiency in cruise"
    )

    @model_validator(mode="after")
    def _ordered(self) -> SizingSpec:
        low, high = self.target_mass_kg
        if not 0 < low <= high:
            msg = "target_mass_kg must be [min, max] with 0 < min <= max."
            raise ValueError(msg)
        return self


class HoverReference(_Strict):
    """A measured hover point."""

    battery_power_w: float = req(
        gt=0, description="Measured battery power in hover (W)"
    )
    mass_kg: float | None = opt(
        None,
        gt=0,
        description="Mass during the measurement (kg); project mass by default",
    )


class CruiseReference(_Strict):
    """A measured cruise point."""

    speed_m_s: float = req(gt=0, description="Airspeed (m/s)")
    battery_power_w: float = req(
        gt=0, description="Measured battery power in cruise (W)"
    )
    mass_kg: float | None = opt(
        None,
        gt=0,
        description="Mass during the measurement (kg); project mass by default",
    )


class BranchOverride(_Strict):
    """Cable lengths entered for one motor, replacing the defaults from the geometry."""

    motor_index: int = req(
        ge=0, description="Motor number (0-based, order of the motor list)"
    )
    dc_length_mm: float | None = opt(
        None, ge=0, description="DC cable distribution → ESC (mm)"
    )
    phase_length_mm: float | None = opt(
        None, ge=0, description="Phase cable ESC → motor (mm)"
    )


FOUR_IN_ONE_CHANNELS = 4
"""Motors one 4-in-1 ESC board can drive."""


class WiringSpec(_Strict):
    """Power chain: battery, cables, ESCs (INC2-004). Lengths default from the geometry."""

    battery_length_mm: float = opt(
        120.0,
        gt=0,
        description="Battery length (mm); the main cable starts at its rear end",
    )
    lift_esc: Literal["four_in_one", "separate"] = opt(
        "separate", description="Lift ESCs: one 4-in-1 board or separate ESCs"
    )
    lift_esc_position_pct: float = opt(
        50.0,
        ge=0,
        le=100,
        description=(
            "Lift ESC position: % of the fuselage length (4-in-1 board, quadplane) or % of the arm length "
            "(separate ESCs of a multicopter / tricopter)"
        ),
    )
    cruise_esc_position_pct: float = opt(
        70.0, ge=0, le=100, description="Cruise ESC position (% of the fuselage length)"
    )
    cruise_on_four_in_one: bool = opt(
        False,
        description="The cruise motors are driven by the 4-in-1 board (no separate cruise ESC)",
    )
    four_in_one_mass_g: float | None = opt(
        None, ge=0, description="Mass of the 4-in-1 ESC board (g); needed with a 4-in-1"
    )
    four_in_one_efficiency: float = adv(
        0.95, gt=0, le=1, description="Efficiency of the 4-in-1 ESC board (every channel)"
    )
    main_awg: int | None = opt(
        None,
        ge=8,
        le=24,
        description="Main cable gauge (AWG); from the current when not set",
    )
    dc_awg: int | None = opt(
        None,
        ge=8,
        le=24,
        description="DC branch cable gauge (AWG); from the current when not set",
    )
    phase_awg: int | None = opt(
        None,
        ge=8,
        le=24,
        description="Phase cable gauge (AWG); from the current when not set",
    )
    connector_mohm: float = adv(
        0.5, ge=0, description="Resistance of the battery connector (mΩ)"
    )
    wire_temperature_c: float = adv(
        40.0, description="Wire temperature for the copper resistance (°C)"
    )
    overrides: list[BranchOverride] = adv(
        [], description="Cable lengths entered per motor"
    )


class FlightPoint(_Strict):
    """A measured flight point (REQ-DATA-006)."""

    kind: Literal["hover", "cruise"] = req(description="Flight phase")
    battery_power_w: float = req(gt=0, description="Measured battery power (W)")
    mass_kg: float | None = opt(
        None,
        gt=0,
        description="Mass during the measurement (kg); project mass by default",
    )
    speed_m_s: float | None = opt(
        None, gt=0, description="Airspeed (m/s), cruise point"
    )
    voltage_v: float | None = opt(
        None, gt=0, description="Battery voltage during the measurement (V)"
    )
    date: str | None = opt(None, description="Date of the flight (YYYY-MM-DD)")
    altitude_m: float | None = opt(None, ge=0, description="Altitude of the flight (m)")
    temperature_c: float | None = opt(None, description="Air temperature (°C)")
    comment: str | None = opt(None, description="Comment")

    @model_validator(mode="after")
    def _speed(self) -> FlightPoint:
        if self.kind == "cruise" and self.speed_m_s is None:
            msg = "A cruise point needs speed_m_s."
            raise ValueError(msg)
        return self


class CalibrationSpec(_Strict):
    """Measured reference points; each one sets one model factor (see predimrc_wrapper.calibration)."""

    hover: HoverReference | None = opt(None, description="Hover reference point")
    cruise: CruiseReference | None = opt(None, description="Cruise reference point")
    cruise_parameter: Literal["auto", "propeller_efficiency", "drag"] = adv(
        "auto",
        description=(
            "Factor set by the cruise point in the scenario mode (auto: propeller efficiency if "
            "wing-borne, else drag); the two-phase calibration always sets the drag factor"
        ),
    )


class Project(_Strict):
    """All inputs of one design."""

    format_version: Literal[2] = adv(
        FORMAT_VERSION, description="Project file format version"
    )
    name: str = req(min_length=1, description="Project name")
    architecture: Literal["quadplane", "multicopter"] = req(
        description="quadplane: wing-borne VTOL (4+1, tilt-rotor...); multicopter: rotary wing, 3 rotors or more"
    )
    aero: AeroSpec | None = opt(None, description="Wing-borne aerodynamics (quadplane)")
    body_shape: str = opt(
        "Non profilé",
        description=(
            "Body shape in cruise as in PredimRC: Profilé (C_d 0.2), Mixte (0.6), Non profilé (1.0) (multicopter)"
        ),
    )
    body_frontal_area_dm2: float | None = opt(
        None,
        gt=0,
        description=(
            "Frontal area of the body (frame, battery, payload) seen by the flow in cruise (multicopter, dm²)"
        ),
    )
    body_cd: float | None = adv(
        None,
        gt=0,
        description="Body drag coefficient replacing the C_d of the shape (multicopter)",
    )
    body_cds_m2: float | None = adv(
        None,
        gt=0,
        description=(
            "Body drag area CdS replacing shape × frontal area (multicopter, m²)"
        ),
    )
    propulsion_units: dict[str, PropulsionSpec] = req(
        min_length=1, description="Propulsion unit types, by name"
    )
    motors: list[MotorSlot] = req(
        min_length=3, description="Motors, one per arm or boom end"
    )
    cg_x_mm: float | None = opt(
        None,
        description="CG station (mm); thrust shared in proportion to disc area when not set",
    )
    cg_y_mm: float = adv(0.0, description="CG lateral position (mm)")
    battery: BatterySpec = req(description="Battery pack")
    mass_items: list[MassItem] = req(
        min_length=1,
        description="Mass items entered by the user (structure, payload, avionics)",
    )
    drag_sources: list[DragSource] = opt(
        [],
        description="Parasitic drag sources added to the PredimRC polar or the body drag",
    )
    max_takeoff_mass_kg: float | None = opt(
        None, gt=0, description="Maximum take-off mass (kg)"
    )
    environment: EnvironmentSpec = opt(
        EnvironmentSpec(),
        description="Flight conditions (altitude, temperature offset)",
    )
    mission: MissionSettings = opt(
        MissionSettings(),
        description="Mission settings: hover time, target speeds, reserve, limits",
    )
    scenarios: dict[str, Scenario] = req(
        min_length=1,
        description="Flight scenarios of the scenario mode (MVP solver), by name",
    )
    sizing: SizingSpec | None = opt(
        None, description="Motor pre-selection from a target mass range"
    )
    calibration: CalibrationSpec | None = opt(
        None, description="Measured reference points"
    )
    test_data: list[FlightPoint] = opt(
        [], description="Measured flight points (test data)"
    )
    wiring: WiringSpec | None = opt(
        None, description="Power chain: battery, cables, ESCs (defaults when not set)"
    )
    booms: BoomSpec | None = opt(
        None,
        description="Booms carrying the lift motors: layout and section (drag and cable paths)",
    )
    cost: CostSpec | None = opt(
        None, description="Prices entered and wear assumptions (defaults when not set)"
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate(cls, data: Any) -> Any:
        if isinstance(data, dict) and "lift_rotors" in data:
            data = migrate_v1(data)
        if isinstance(data, dict):
            data = migrate_accessory(data)
        return data

    @field_validator("propulsion_units")
    @classmethod
    def _motor_exists(
        cls, units: dict[str, PropulsionSpec]
    ) -> dict[str, PropulsionSpec]:
        from predimrc_wrapper.data import default_database  # noqa: PLC0415

        for name, spec in units.items():
            try:
                default_database().motor(spec.motor_id)
            except KeyError as error:
                msg = f"{name}: {error.args[0]}"
                raise ValueError(msg) from None
        return units

    def body_drag(self) -> tuple[float, str]:
        """Body drag area of a multicopter (m²) and the model used."""
        if self.body_cds_m2 is not None:
            return self.body_cds_m2, f"CdS entered: {100 * self.body_cds_m2:.3g} dm²"
        if self.body_frontal_area_dm2 is None:
            return 0.0, "no body drag"
        from predimrc_wrapper.data.drag_shapes import shape_cd  # noqa: PLC0415

        cd = self.body_cd if self.body_cd is not None else shape_cd(self.body_shape).cd
        origin = (
            "entered"
            if self.body_cd is not None
            else f"shape {self.body_shape} (PredimRC)"
        )
        return cd * self.body_frontal_area_dm2 / 100.0, (
            f"C_d·A = {cd:g} ({origin}) × {self.body_frontal_area_dm2:g} dm²"
        )

    def on_four_in_one(self, motor: MotorSlot) -> bool:
        """The motor is driven by the 4-in-1 board (else by its own separate ESC)."""
        spec = self.wiring
        if spec is None or spec.lift_esc != "four_in_one":
            return False
        return motor.role != "cruise" or spec.cruise_on_four_in_one

    def esc_efficiency(self, motor: MotorSlot) -> float:
        """Efficiency of the ESC driving the motor: the 4-in-1 board or its unit type's ESC."""
        if self.on_four_in_one(motor):
            return self.wiring.four_in_one_efficiency
        return self.propulsion_units[motor.unit].esc_efficiency

    def lift_motors(self) -> list[MotorSlot]:
        """Motors used in vertical flight (lift and tilt)."""
        return [m for m in self.motors if m.role in LIFT_ROLES]

    def cruise_motors(self) -> list[MotorSlot]:
        """Motors used in the forward flight of a wing-borne aircraft (cruise and tilt)."""
        return [m for m in self.motors if m.role in CRUISE_ROLES]

    @model_validator(mode="after")
    def _architecture(self) -> Project:
        unknown = sorted({m.unit for m in self.motors} - set(self.propulsion_units))
        if unknown:
            msg = f"Motors use unknown propulsion units {unknown}; defined: {sorted(self.propulsion_units)}."
            raise ValueError(msg)
        if len(self.lift_motors()) < 3:
            msg = "At least 3 lift motors (role lift or tilt) are needed."
            raise ValueError(msg)
        if self.architecture == "quadplane":
            if self.aero is None:
                msg = "A quadplane needs 'aero'."
                raise ValueError(msg)
            if not self.cruise_motors():
                msg = (
                    "A quadplane needs at least one cruise motor (role cruise or tilt)."
                )
                raise ValueError(msg)
        else:
            if self.aero is not None:
                msg = "A multicopter has no 'aero'."
                raise ValueError(msg)
            if self.body_cds_m2 is None and self.body_frontal_area_dm2 is None:
                msg = "A multicopter needs 'body_frontal_area_dm2' (or 'body_cds_m2')."
                raise ValueError(msg)
            if any(m.role != "lift" for m in self.motors):
                msg = "All the motors of a multicopter have the role lift (tilting motors need a wing)."
                raise ValueError(msg)
            from predimrc_wrapper.data.drag_shapes import drag_shapes  # noqa: PLC0415

            if self.body_shape not in drag_shapes():
                msg = f"Unknown body shape '{self.body_shape}'. Known: {list(drag_shapes())}"
                raise ValueError(msg)
        self._check_overlap()
        self._check_escs()
        return self

    def _check_escs(self) -> None:
        """ESC masses entered (unit type for separate ESCs, board for a 4-in-1); board channels."""
        missing = sorted({
            m.unit
            for m in self.motors
            if not self.on_four_in_one(m)
            and self.propulsion_units[m.unit].esc_mass_g is None
        })
        if missing:
            msg = (
                f"Separate ESCs need the ESC mass of the unit types {missing}: enter 'esc_mass_g' "
                "or drive these motors with the 4-in-1 board (Power chain tab)."
            )
            raise ValueError(msg)
        if (
            self.wiring is not None
            and self.wiring.lift_esc == "four_in_one"
            and self.wiring.four_in_one_mass_g is None
        ):
            msg = "A 4-in-1 ESC needs its board mass: enter 'four_in_one_mass_g' (Power chain tab)."
            raise ValueError(msg)
        driven = [i + 1 for i, m in enumerate(self.motors) if self.on_four_in_one(m)]
        if len(driven) > FOUR_IN_ONE_CHANNELS:
            msg = (
                f"The 4-in-1 ESC drives {len(driven)} motors ({', '.join(map(str, driven))}) but has "
                f"{FOUR_IN_ONE_CHANNELS} channels: use separate ESCs"
                + (
                    " or a separate cruise ESC (untick 'cruise on four in one')."
                    if self.wiring.cruise_on_four_in_one
                    else "."
                )
            )
            raise ValueError(msg)

    def overlaps(self) -> list[tuple[int, int, float, float]]:
        """Overlapping lift propeller discs: (motor i, motor j, centre distance, minimum distance) in mm."""
        lift = [(i, m) for i, m in enumerate(self.motors) if m.role in LIFT_ROLES]
        out = []
        for k, (i, a) in enumerate(lift):
            for j, b in lift[k + 1 :]:
                ra = self.propulsion_units[a.unit].prop_diameter_in * 25.4 / 2
                rb = self.propulsion_units[b.unit].prop_diameter_in * 25.4 / 2
                gap = ((a.x_mm - b.x_mm) ** 2 + (a.y_mm - b.y_mm) ** 2) ** 0.5
                if gap < ra + rb - 1e-6:
                    out.append((i, j, gap, ra + rb))
        return out

    def _check_overlap(self) -> None:
        """Lift propeller discs must not overlap (one motor per arm end)."""
        found = self.overlaps()
        if not found:
            return
        i, j, gap, minimum = found[0]
        a, b = self.motors[i], self.motors[j]
        da = self.propulsion_units[a.unit].prop_diameter_in
        db = self.propulsion_units[b.unit].prop_diameter_in
        msg = (
            f"The propellers of motor {i + 1} ({da:g} in, at x = {a.x_mm:g}, y = {a.y_mm:g} mm) "
            f"and motor {j + 1} ({db:g} in, at x = {b.x_mm:g}, y = {b.y_mm:g} mm) overlap: their centres are "
            f"{gap:.0f} mm apart, they need at least {minimum:.0f} mm (sum of the two propeller radii). "
            f"Move the motors {minimum - gap:.0f} mm further apart (longer arms or booms) or use smaller "
            "propellers."
            + (
                f" {len(found) - 1} other pair(s) overlap too."
                if len(found) > 1
                else ""
            )
        )
        raise ValueError(msg)

    # --- I/O -----------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Project:
        """Load a project file."""
        return cls.model_validate(
            yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        )

    @classmethod
    def template(cls, name: str) -> Project:
        """Load a template: shipped (names in ``TEMPLATES``) or user (``user:<name>``)."""
        from predimrc_wrapper.aircraft import templates  # noqa: PLC0415

        if name.startswith(templates.USER):
            return cls.model_validate(templates.load_user(name))
        text = (
            files("predimrc_wrapper.templates")
            .joinpath(f"{name}.yaml")
            .read_text(encoding="utf-8")
        )
        return cls.model_validate(yaml.safe_load(text))

    def to_dict(self) -> dict[str, Any]:
        """Return the project as plain data (YAML-ready)."""
        return self.model_dump(mode="json", exclude_none=True)

    def save(self, path: str | Path) -> None:
        """Save the project file."""
        Path(path).write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    # --- overrides -----------------------------------------------------------

    def with_overrides(self, overrides: dict[str, Any]) -> Project:
        """Return a copy with dotted-path fields replaced, fully re-validated.

        Args:
            overrides: Values by dotted path, e.g. ``{"battery.mass_g": 700,
                "aero.wing.length_mm.1": 320}`` (list indexes as integers).

        Raises:
            OverrideError: For an unknown path, with close suggestions.
            ValidationError: For an invalid value.
        """
        data = copy.deepcopy(self.model_dump(mode="python"))
        for path, value in overrides.items():
            _set_path(data, path, value, _valid_paths(type(self)))
            parts = path.split(".")
            if (
                len(parts) == 3
                and parts[0] == "propulsion_units"
                and parts[2] == "motor_id"
                and parts[1] in self.propulsion_units
                and value != self.propulsion_units[parts[1]].motor_id
                and f"propulsion_units.{parts[1]}.motor_mass_g" not in overrides
            ):
                # Another motor: the mass of the database, not that of the former one.
                data["propulsion_units"][parts[1]]["motor_mass_g"] = None
        return type(self).model_validate(data)


TEMPLATES = {
    "multicopter": "Quadcopter X (no wing)",
    "tricopter": "Tricopter (no wing)",
    "quadplane": "Quadplane 4+1 (wing, 4 lift + 1 pusher)",
    "tiltrotor": "Tricopter with wing (tilting motors chosen by the tilt mask)",
}
"""Shipped templates: file name → configuration label."""


def migrate_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a format-1 project (one lift unit type, symmetric layout) to format 2."""
    from predimrc_wrapper.aircraft import layouts  # noqa: PLC0415

    data = copy.deepcopy(data)
    layout = data.pop("lift_rotors")
    units = {"lift": data.pop("lift_propulsion")}
    cruise = data.pop("cruise_propulsion", None)
    n = layout["n_rotors"]
    if data.get("architecture") == "quadplane":
        fus = (data.get("aero") or {}).get("fuselage") or {}
        units["cruise"] = cruise
        motors = layouts.quadplane(
            layout["boom_span_mm"],
            layout["x_front_mm"],
            layout["x_rear_mm"],
            x_pusher_mm=fus.get("length_mm", 0.0) - fus.get("nose_lever_mm", 0.0),
            per_boom=n // 2,
        )
    else:
        motors = layouts.multirotor(n, layout["arm_length_mm"])
    data["propulsion_units"] = {k: v for k, v in units.items() if v}
    for spec in data["propulsion_units"].values():  # format 1 had a 30 g ESC by default
        spec.setdefault("esc_mass_g", 30.0)
    data["motors"] = motors
    data["format_version"] = FORMAT_VERSION
    return data


def migrate_accessory(data: dict[str, Any]) -> dict[str, Any]:
    """Drop the PredimRC accessory surface of an old project file (REQ-AERO-006).

    PredimRC is always evaluated with an accessory surface of 0 (written by the tool at
    every evaluation). An accessory found in a project file is removed with a warning; it is
    not turned into a drag source: the user enters the parasitic drag in the Drag tab.
    """
    fus = ((data.get("aero") or {}).get("fuselage")) or {}
    if "accessory_area_dm2" not in fus and "accessory_shape" not in fus:
        return data
    import warnings  # noqa: PLC0415

    from predimrc_wrapper.data.drag_shapes import shape_cd  # noqa: PLC0415

    data = copy.deepcopy(data)
    fus = data["aero"]["fuselage"]
    area = float(fus.pop("accessory_area_dm2", 0.0) or 0.0)
    label = fus.pop("accessory_shape", "Non profilé")
    if area > 0:
        shape = shape_cd(label)
        warnings.warn(
            f"The PredimRC accessory surface ({area:g} dm², {label}, CdS {shape.cd * area:g} dm²) is "
            "ignored: PredimRC runs with 0. Enter this drag as a source of the Drag tab if needed.",
            stacklevel=2,
        )
    return data


def _valid_paths(model_cls: type[BaseModel], prefix: str = "") -> list[str]:
    paths = []
    for name, info in model_cls.model_fields.items():
        path = f"{prefix}{name}"
        paths.append(path)
        sub = _model_of(info.annotation)
        if sub is not None:
            paths += _valid_paths(sub, f"{path}.")
    return paths


def _model_of(annotation: Any) -> type[BaseModel] | None:
    for candidate in (annotation, *getattr(annotation, "__args__", ())):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def _set_path(data: dict, path: str, value: Any, valid: list[str]) -> None:
    keys = path.split(".")
    node: Any = data
    for i, key in enumerate(keys):
        last = i == len(keys) - 1
        if isinstance(node, list):
            if not key.isdigit() or int(key) >= len(node):
                msg = f"Unknown override path '{path}': bad list index '{key}'."
                raise OverrideError(msg)
            if last:
                node[int(key)] = value
                return
            node = node[int(key)]
        elif isinstance(node, dict) and (
            key in node or (keys[0] == "scenarios" and i == 1)
        ):
            if last:
                node[key] = value
                return
            if node[key] is None:
                node[key] = {}
            node = node[key]
        else:
            close = difflib.get_close_matches(path, valid, n=3, cutoff=0.6)
            msg = f"Unknown override path '{path}'. Did you mean {close}?"
            raise OverrideError(msg)


def defaults_left(project: Project) -> list[str]:
    """Return the dotted paths of optional fields still equal to their default."""
    left: list[str] = []

    def walk(model: BaseModel, prefix: str) -> None:
        for name, info in type(model).model_fields.items():
            value = getattr(model, name)
            extra = info.json_schema_extra or {}
            if isinstance(value, BaseModel):
                walk(value, f"{prefix}{name}.")
            elif (
                extra.get("level") in ("default", "advanced")
                and value == info.default
                and value is not None
            ):
                left.append(f"{prefix}{name}")

    walk(project, "")
    return left


__all__ = [
    "CRUISE_ROLES",
    "LIFT_ROLES",
    "TEMPLATES",
    "AeroSpec",
    "BatterySpec",
    "BoomSpec",
    "BranchOverride",
    "CalibrationSpec",
    "CostSpec",
    "CruiseReference",
    "DragSource",
    "EnvironmentSpec",
    "FlightPoint",
    "FuselageSpec",
    "HoverReference",
    "MassItem",
    "MissionSettings",
    "MotorSlot",
    "OverrideError",
    "Project",
    "ProjectError",
    "PropulsionSpec",
    "SizingSpec",
    "StabSpec",
    "ValidationError",
    "WingSpec",
    "WiringSpec",
    "defaults_left",
    "migrate_accessory",
    "migrate_v1",
]
