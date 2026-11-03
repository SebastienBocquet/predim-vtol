"""Tests of the segment powers and the cruise speed sweep (MVP-005)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.mission.powers import SegmentPower
from tests.helpers import ConstantEfficiencyUnit
from tests.helpers import ParabolicAero


def test_multicopter_zero_speed_equals_hover():
    seg = SegmentPower(AircraftModel(Project.template("multicopter")))
    hover = float(seg.evaluate({"kind": "hover"})["battery_power_w"])
    assert float(
        seg.evaluate({"kind": "cruise", "v_m_s": 0.0})["battery_power_w"]
    ) == pytest.approx(hover, rel=1e-9)


def test_multicopter_sweep_gives_the_two_speeds():
    sweep = SegmentPower(AircraftModel(Project.template("multicopter"))).cruise_sweep()
    assert sweep.v_range > sweep.v_endurance > 0


def test_optimal_speed_ratio_parabolic_polar():
    """Constant efficiencies and parabolic polar: V_r / V_e = 3^0.25."""
    project = Project.template("quadplane").with_overrides({
        "drag_sources": [],
        "mission.avionics_power_w": 0.0,
        "mission.stall_margin": 1.0,
        "mission.speed_step": 0.02,
    })
    aircraft = AircraftModel(project, aero_backend=ParabolicAero())
    aircraft.units["cruise"] = ConstantEfficiencyUnit()
    sweep = SegmentPower(aircraft).cruise_sweep()
    assert sweep.v_range / sweep.v_endurance == pytest.approx(3**0.25, abs=0.01)


def test_scenario_mode_inputs_of_old_files_are_dropped():
    data = Project.template("tricopter").to_dict()
    data["scenarios"] = {"s": {"segments": [{"kind": "hover", "duration_s": 60}]}}
    data["calibration"]["cruise_parameter"] = "drag"
    project = Project.model_validate(data)
    assert "scenarios" not in project.to_dict()
    assert "cruise_parameter" not in project.to_dict()["calibration"]
