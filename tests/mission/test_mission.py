"""Tests of the segment powers and the cruise speed sweep (MVP-005)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.mission.powers import INDUCED_POWER_FACTOR
from predimrc_wrapper.mission.powers import SegmentPower
from predimrc_wrapper.mission.powers import _rotor_forward_power
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


def test_multicopter_cruise_keeps_the_profile_power():
    """Template: the shaft power at V1 saves about 25 % on hover, not 35 % (all / FM)."""
    seg = SegmentPower(AircraftModel(Project.template("multicopter")))
    sweep = seg.cruise_sweep()
    hover = float(seg.evaluate({"kind": "hover"})["shaft_power_w"])
    saving = 1.0 - float(np.min(sweep.shaft_power_w)) / hover
    assert 0.20 < saving < 0.30


@pytest.mark.parametrize("figure_of_merit", [0.65, 0.95])
def test_rotor_forward_power_at_zero_speed_is_hover(figure_of_merit):
    """V = 0 gives T·v_h/FM, also when κ is capped at 1/FM."""
    power = _rotor_forward_power(5.0, 0.0, 0.0, 4.9, 4.9, figure_of_merit, 60.0)
    assert power == pytest.approx(5.0 * 4.9 / figure_of_merit, rel=1e-12)


def test_rotor_forward_power_profile_does_not_follow_v_i():
    """Halving v_i at μ = 0 removes only the induced half κ·T·v_h/2."""
    hover = _rotor_forward_power(5.0, 0.0, 0.0, 4.9, 4.9, 0.65, 60.0)
    half = _rotor_forward_power(5.0, 0.0, 0.0, 4.9, 2.45, 0.65, 60.0)
    assert hover - half == pytest.approx(INDUCED_POWER_FACTOR * 5.0 * 2.45, rel=1e-12)


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
