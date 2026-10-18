"""Two-phase flight time: hover by moment balance and test data, cruise at target speeds (INC2-007)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.mission.two_phase import TwoPhaseEvaluation
from tests.conftest import requires_excel
from tests.helpers import ParabolicAero


def _solve(name: str, hover: float = 90.0, speeds=None, **overrides):
    project = (
        Project.template(name).with_overrides(overrides)
        if overrides
        else Project.template(name)
    )
    return TwoPhaseEvaluation(
        AircraftModel(project, aero_backend=ParabolicAero())
    ).solve(hover, speeds)


def test_flight_time_formula_and_reserve():
    r = _solve("tricopter")
    assert r.energy_available_j == pytest.approx(
        0.8 * r.energy_nominal_j
    )  # 80 % of the nominal energy
    assert r.energy_nominal_j == pytest.approx(
        150.0 * 0.45 * 3600, rel=1e-9
    )  # LiPo 150 Wh/kg, 450 g
    for c in r.cruise:
        expected = (
            90.0
            + (r.energy_available_j - r.hover.battery_power_w * 90.0)
            / c.battery_power_w
        )
        assert c.flight_time_s == pytest.approx(expected, rel=1e-12)
        assert c.range_m == pytest.approx(c.v_m_s * (c.flight_time_s - 90.0), rel=1e-12)
    assert "E_avail" in r.hand_check(1)


def test_zero_hover_and_too_long_hover():
    base = _solve("tricopter", hover=0.0)
    for c in base.cruise:
        assert c.flight_time_s == pytest.approx(
            base.energy_available_j / c.battery_power_w, rel=1e-12
        )
    long = _solve("tricopter", hover=3600.0)
    assert not long.feasible
    assert long.limiting == "hover_too_long"


def test_hover_thrusts_balance_the_moments():
    r = _solve("tricopter")
    project = Project.template("tricopter")
    thrusts = np.array([m.thrust_n for m in r.hover.motors])
    xs = np.array([project.motors[m.index].x_mm for m in r.hover.motors])
    ys = np.array([project.motors[m.index].y_mm for m in r.hover.motors])
    assert thrusts.sum() == pytest.approx(1.87 * GRAVITY, rel=1e-9)
    assert thrusts @ xs == pytest.approx(0.0, abs=1e-9)
    assert thrusts @ ys == pytest.approx(0.0, abs=1e-9)
    assert r.hover.front_rear_ratio == pytest.approx(
        2.0, rel=1e-9
    )  # two front motors, one rear, equal thrusts
    shifted = _solve("tricopter", cg_x_mm=-30.0)
    assert shifted.hover.front_rear_ratio > 2.0


def test_hover_power_from_test_data_and_flags():
    r = _solve("tricopter")
    front, _, rear = r.hover.motors
    assert front.source == "tested_pair"
    assert front.trusted
    assert "p12x4" in front.pair
    assert rear.source == "untested_pair"
    assert "not in the database" in rear.pair
    # The designer's measurement (280 W at 1.87 kg) is within 15 % without calibration.
    assert r.hover.battery_power_w == pytest.approx(280.0, rel=0.15)
    no_pitch = _solve("tricopter", **{"propulsion_units.rear.prop_pitch_in": None})
    assert not no_pitch.hover.motors[2].trusted
    assert "pitch not given" in no_pitch.hover.motors[2].reason


def test_battery_power_includes_the_chain():
    r = _solve("multicopter")
    chain = r.hover.chain
    assert r.hover.battery_power_w == pytest.approx(chain.chemical_power_w)
    assert chain.chemical_power_w > sum(m.power_w for m in r.hover.motors)
    assert chain.chemical_power_w == pytest.approx(
        chain.total_loss_w + chain.motor_power_w + 5.0, rel=1e-9
    )


def test_quadplane_cruise_with_propeller_model():
    r = _solve("quadplane", speeds=(13.0, 16.0))
    for c in r.cruise:
        assert c.battery_power_w > c.aero_power_w
        (m,) = c.motors
        assert m.thrust_n == pytest.approx(c.drag_n, rel=1e-9)
        assert 0.3 < m.prop_efficiency < 0.9
        assert "blade-element" in m.model
    assert any(
        "not available" in w for w in r.warnings
    )  # fake aero: no PredimRC blocks


def test_tilt_motors_push_in_cruise():
    r = _solve("tiltrotor", speeds=(13.0, 16.0))
    assert [m.index for m in r.cruise[0].motors] == [0, 1]
    assert {m.index for m in r.hover.motors} == {0, 1, 2}


def test_project_speeds_and_api():
    project = Project.template("multicopter").with_overrides({
        "mission.target_speeds_m_s": [8.0, 11.0],
        "mission.hover_time_s": 60.0,
    })
    r = evaluate_two_phase(project)
    assert [c.v_m_s for c in r.cruise] == [8.0, 11.0]
    assert r.hover_time_s == 60.0


@pytest.mark.slow
@requires_excel
def test_quadplane_two_phase_through_predimrc(predimrc):
    r = evaluate_two_phase(
        Project.template("quadplane").with_overrides({"environment.altitude_m": 250.0}),
        backend=predimrc,
    )
    assert r.feasible
    assert r.iso_check.passed
    assert not r.warnings
