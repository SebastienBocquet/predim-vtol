"""Tests of the mission solver (MVP-005)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate
from predimrc_wrapper.mission import Scenario
from predimrc_wrapper.mission import Segment
from predimrc_wrapper.mission.powers import SegmentPower
from predimrc_wrapper.mission.solver import MissionSolver
from tests.conftest import requires_excel
from tests.helpers import ConstantEfficiencyUnit
from tests.helpers import ParabolicAero


def test_segment_validation():
    with pytest.raises(ValidationError, match="exactly one"):
        Segment(kind="cruise", duration_s=10)
    with pytest.raises(ValidationError, match="positive altitude"):
        Segment(kind="vertical_climb", altitude_change_m=-5)
    with pytest.raises(ValidationError, match="At most one"):
        Scenario(
            segments=[
                Segment(kind="cruise", until_reserve=True),
                Segment(kind="loiter", until_reserve=True),
            ]
        )


def test_hover_time_builder():
    s = Scenario.hover_time(60, wing_borne=False)
    assert [seg.kind for seg in s.segments] == [
        "vertical_climb",
        "hover",
        "cruise",
        "vertical_descent",
    ]
    assert [seg.kind for seg in Scenario.hover_time(0).segments].count("hover") == 0


def test_multicopter_energy_and_reserve():
    r = evaluate(Project.template("multicopter"))
    assert r.feasible, r.limiting
    total = sum(s.energy_j for s in r.segments)
    assert total == pytest.approx(r.energy_used_j, rel=1e-12)
    assert r.energy_used_j == pytest.approx(r.energy_available_j, rel=1e-9)
    assert r.flight_time_s == pytest.approx(sum(s.duration_s for s in r.segments))
    assert r.v_range > r.v_endurance > 0


def test_multicopter_zero_speed_equals_hover():
    seg = SegmentPower(AircraftModel(Project.template("multicopter")))
    hover = float(seg.evaluate({"kind": "hover"})["battery_power_w"])
    assert float(
        seg.evaluate({"kind": "cruise", "v_m_s": 0.0})["battery_power_w"]
    ) == pytest.approx(hover, rel=1e-9)


def test_zero_hover_gives_longer_flight():
    p = Project.template("multicopter")
    base = evaluate(p)
    no_hover = p.with_overrides({
        "scenarios": {"s": Scenario.hover_time(0, wing_borne=False).model_dump()}
    })
    assert evaluate(no_hover, "s").flight_time_s > base.flight_time_s


def test_quadplane_with_fake_aero():
    r = evaluate(Project.template("quadplane"), backend=ParabolicAero())
    assert r.feasible, r.limiting
    cruise = next(s for s in r.segments if s.kind == "cruise")
    assert cruise.speed_m_s == pytest.approx(r.v_range)
    assert r.energy_used_j == pytest.approx(r.energy_available_j, rel=1e-9)


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
    sweep = MissionSolver(aircraft).cruise_sweep()
    assert sweep.v_range / sweep.v_endurance == pytest.approx(3**0.25, abs=0.01)


def test_undersized_lift_motor_is_infeasible():
    p = Project.template("multicopter").with_overrides({
        "battery.mass_g": 2500,
        "max_takeoff_mass_kg": 6,
    })
    r = evaluate(p)
    assert not r.feasible
    assert r.limiting


def test_physics_time_budget():
    import time  # noqa: PLC0415

    p = Project.template("multicopter")
    start = time.perf_counter()
    for _ in range(10):
        evaluate(p)
    assert (time.perf_counter() - start) / 10 < 0.05


@pytest.mark.slow
@requires_excel
def test_quadplane_through_predimrc(predimrc):
    r = evaluate(Project.template("quadplane"), backend=predimrc)
    assert r.feasible, r.limiting
    assert r.flight_time_s > 0
    assert r.range_m > 0
