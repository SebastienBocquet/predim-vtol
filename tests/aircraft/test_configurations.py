"""Motor lists: heterogeneous units, roles (lift, cruise, tilt), CG balance, format-1 migration."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import ProjectError
from predimrc_wrapper.aircraft import layouts
from predimrc_wrapper.aircraft.model import hover_thrust_split
from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.mission.powers import SegmentPower
from tests.helpers import ParabolicAero

V1_MULTICOPTER = {
    "format_version": 1,
    "name": "old",
    "architecture": "multicopter",
    "body_cds_m2": 0.03,
    "lift_rotors": {"n_rotors": 6, "arm_length_mm": 400, "max_prop_diameter_in": 13},
    "lift_propulsion": {"motor_id": "tmotor-mn2806-400kv", "prop_diameter_in": 12},
    "battery": {"chemistry": "li-ion", "n_series": 6, "mass_g": 700},
    "mass_items": [{"name": "frame", "category": "airframe", "mass_g": 600}],
    "scenarios": {"s": {"segments": [{"kind": "hover", "duration_s": 60}]}},
}


def test_format_1_is_migrated():
    project = Project.model_validate(V1_MULTICOPTER)
    assert project.format_version == 2
    assert list(project.propulsion_units) == ["lift"]
    assert len(project.motors) == 6
    assert {m.role for m in project.motors} == {"lift"}
    assert all(
        np.hypot(m.x_mm, m.y_mm) == pytest.approx(400, abs=0.1) for m in project.motors
    )


def test_format_1_quadplane_gets_a_pusher():
    data = Project.template("quadplane").to_dict()
    units = data.pop("propulsion_units")
    data.pop("motors")
    data.update({
        "format_version": 1,
        "lift_propulsion": units["lift"],
        "cruise_propulsion": units["cruise"],
        "lift_rotors": {
            "n_rotors": 4,
            "boom_span_mm": 600,
            "x_front_mm": -200,
            "x_rear_mm": 450,
            "max_prop_diameter_in": 15,
        },
    })
    project = Project.model_validate(data)
    assert [m.role for m in project.motors].count("cruise") == 1
    pusher = next(m for m in project.motors if m.role == "cruise")
    assert pusher.x_mm == pytest.approx(760 - 270)
    assert pusher.y_mm == 0


def test_split_without_cg_follows_disc_area():
    f = hover_thrust_split(np.zeros(3), np.zeros(3), np.array([2.0, 1.0, 1.0]))
    assert f.tolist() == pytest.approx([0.5, 0.25, 0.25])


def test_split_balances_the_cg():
    motors = layouts.tricopter(300, 300)
    x = np.array([m["x_mm"] for m in motors]) / 1000
    y = np.array([m["y_mm"] for m in motors]) / 1000
    area = np.array([0.073, 0.073, 0.051])
    f = hover_thrust_split(x, y, area, (0.0, 0.0))
    assert f.sum() == pytest.approx(1.0)
    assert f @ x == pytest.approx(0.0, abs=1e-12)
    assert f @ y == pytest.approx(0.0, abs=1e-12)
    assert f.tolist() == pytest.approx([1 / 3, 1 / 3, 1 / 3], abs=1e-3)


def test_cg_outside_the_rotors():
    project = Project.template("tricopter").with_overrides({"cg_x_mm": 400})
    with pytest.raises(ProjectError, match="outside the polygon"):
        AircraftModel(project)


def test_heterogeneous_hover_thrusts_sum_to_weight():
    aircraft = AircraftModel(Project.template("tricopter"))
    loads = aircraft.hover_loads(aircraft.total_mass_kg * GRAVITY)
    assert sum(float(t) for _, t in loads) == pytest.approx(
        aircraft.total_mass_kg * GRAVITY
    )
    assert {id(u) for u, _ in loads} == {
        id(aircraft.units["front"]),
        id(aircraft.units["rear"]),
    }


def test_tricopter_zero_speed_equals_hover():
    seg = SegmentPower(AircraftModel(Project.template("tricopter")))
    hover = float(seg.evaluate({"kind": "hover"})["battery_power_w"])
    assert float(
        seg.evaluate({"kind": "cruise", "v_m_s": 0.0})["battery_power_w"]
    ) == pytest.approx(hover, rel=1e-9)


def test_thrust_to_weight_limited_by_the_most_loaded_motor():
    project = Project.template("tricopter")
    balanced = AircraftModel(project)
    forward = AircraftModel(project.with_overrides({"cg_x_mm": -60}))
    assert forward.hover_fractions[0] > balanced.hover_fractions[0]
    assert forward.lift_thrust_to_weight() < balanced.lift_thrust_to_weight()


def test_tilt_motors_lift_and_cruise_and_count_once():
    project = Project.template("tiltrotor")
    aircraft = AircraftModel(project, aero_backend=ParabolicAero())
    assert [m.role for m in aircraft.lift_motors] == ["tilt", "tilt", "lift"]
    assert [m.role for m in aircraft.cruise_motors] == ["tilt", "tilt"]
    breakdown = aircraft.mass["breakdown"]
    assert breakdown["tilt propulsion"] == pytest.approx(
        2 * aircraft.units["tilt"].mass_kg
    )
    assert breakdown["lift propulsion"] == pytest.approx(aircraft.units["rear"].mass_kg)
    assert "cruise propulsion" not in breakdown
    cruise = [t for _, t in aircraft.cruise_loads(np.array(4.0))]
    assert [float(t) for t in cruise] == pytest.approx([2.0, 2.0])


def test_quadplane_with_tilting_rear_motors():
    """ArduPilot-like mask: any motor can be made a tilting one."""
    data = Project.template("quadplane").model_dump()
    data["motors"] = [m for m in data["motors"] if m["role"] != "cruise"]
    for m in data["motors"][:2]:
        m["role"] = "tilt"
    aircraft = AircraftModel(Project.model_validate(data), aero_backend=ParabolicAero())
    y = SegmentPower(aircraft).evaluate({"kind": "cruise", "v_m_s": 15.0})
    assert bool(y["feasible"])
    assert float(y["battery_power_w"]) > 0


def test_unknown_unit_in_layout():
    data = Project.template("tricopter").model_dump()
    data["motors"] = layouts.tricopter(300, 300, front_unit="front", rear_unit="tail")
    with pytest.raises(ValidationError, match="unknown propulsion units"):
        Project.model_validate(data)
