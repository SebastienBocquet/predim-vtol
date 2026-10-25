"""Power chain and cable layout (INC2-004)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.propulsion import BatteryModel
from predimrc_wrapper.propulsion import PowerChain
from predimrc_wrapper.propulsion.chain import BranchSpec
from predimrc_wrapper.propulsion.wiring import awg_area_mm2
from predimrc_wrapper.propulsion.wiring import awg_for_current
from predimrc_wrapper.propulsion.wiring import default_layout
from predimrc_wrapper.propulsion.wiring import resistance_ohm


def test_copper_resistance():
    assert awg_area_mm2(12) == pytest.approx(3.31, rel=0.01)
    assert resistance_ohm(1000.0, 12, 20.0) == pytest.approx(
        1.72e-8 / 3.31e-6, rel=0.01
    )
    assert resistance_ohm(1000.0, 12, 40.0) == pytest.approx(
        resistance_ohm(1000.0, 12, 20.0) * 1.0786, rel=1e-4
    )
    assert awg_for_current(10.0) == 18
    assert awg_for_current(30.0) == 12


def test_tricopter_default_lengths():
    """Arms of 300 mm, separate ESCs at 50 % of the arm, battery of 120 mm centred."""
    layout = default_layout(Project.template("tricopter"))
    assert layout.main_length_mm == pytest.approx(60.0)
    for b in layout.branches:
        assert b.dc_length_mm == pytest.approx(150.0, abs=0.1)
        assert b.phase_length_mm == pytest.approx(150.0, abs=0.1)
    four = default_layout(
        Project.template("tricopter").with_overrides({
            "wiring": {"lift_esc": "four_in_one", "four_in_one_mass_g": 15.0}
        })
    )
    assert all(
        b.dc_length_mm == 0 and b.phase_length_mm == pytest.approx(300.0, abs=0.1)
        for b in four.branches
    )


def test_quadplane_lengths_in_fuselage_percent():
    p = Project.template("quadplane").with_overrides({
        "wiring": {"lift_esc_position_pct": 40.0, "battery_length_mm": 150.0}
    })
    layout = default_layout(p)
    x_nose, length, spar = -270.0, 760.0, 50.0
    assert layout.battery_rear_x_mm == pytest.approx(x_nose + 150.0)
    esc_x = x_nose + 0.4 * length
    front = layout.branches[0]  # motor at (-200, 300)
    assert front.esc_x_mm == pytest.approx(esc_x)
    assert front.phase_length_mm == pytest.approx(
        abs(esc_x - spar) + 300.0 + abs(-200.0 - spar)
    )
    pusher = layout.branches[4]
    assert pusher.phase_length_mm == pytest.approx(abs(490.0 - (x_nose + 0.7 * length)))


def test_override_lengths():
    p = Project.template("tricopter").with_overrides({
        "wiring": {"overrides": [{"motor_index": 2, "phase_length_mm": 500.0}]}
    })
    chain = PowerChain.from_project(p, AircraftModel(p).battery)
    assert chain.p.branches[2].phase_length_mm == 500.0
    assert chain.p.branches[0].phase_length_mm == pytest.approx(150, abs=0.1)


def _chain(**kw):
    return PowerChain(
        branches=[BranchSpec("m", 300.0, 16, 400.0, 16, 0.95)],
        main_length_mm=150.0,
        main_awg=12,
        battery=BatteryModel.from_mass("lipo", 4, 0.45),
        **kw,
    )


def test_energy_balance_and_cable_length():
    r = _chain().evaluate({
        "motor_power_w": [100.0],
        "motor_current_a": [12.0],
        "avionics_power_w": 5.0,
    })["result"]
    assert r.chemical_power_w == pytest.approx(r.total_loss_w + 100.0 + 5.0, rel=1e-9)
    longer = PowerChain(
        branches=[BranchSpec("m", 300.0, 16, 800.0, 16, 0.95)],
        main_length_mm=150.0,
        main_awg=12,
        battery=BatteryModel.from_mass("lipo", 4, 0.45),
    )
    r2 = longer.evaluate({
        "motor_power_w": [100.0],
        "motor_current_a": [12.0],
        "avionics_power_w": 5.0,
    })["result"]
    phase = next(s.loss_w for s in r.segments if "phase" in s.name)
    phase2 = next(s.loss_w for s in r2.segments if "phase" in s.name)
    assert phase2 == pytest.approx(2 * phase, rel=1e-9)  # same motor current


def test_esc_input_data_not_counted_twice():
    motor = _chain().evaluate({"motor_power_w": [100.0], "motor_current_a": [12.0]})[
        "result"
    ]
    esc = _chain().evaluate({
        "motor_power_w": [100.0],
        "motor_current_a": [12.0],
        "esc_input": [True],
    })["result"]
    esc_seg = next(s for s in esc.segments if s.name.endswith("ESC"))
    assert esc_seg.in_data
    assert esc_seg.loss_w == pytest.approx(0.05 * esc_seg.power_in_w)
    assert esc.motor_power_w == pytest.approx(95.0)
    assert (
        esc.battery_power_w < motor.battery_power_w
    )  # the ESC loss is not added on top
    assert esc.chemical_power_w == pytest.approx(
        esc.total_loss_w + esc.motor_power_w + esc_seg.loss_w, rel=1e-9
    )


def test_feasibility_flag():
    r = _chain().evaluate({"motor_power_w": [5e4], "motor_current_a": [50.0]})["result"]
    assert not r.feasible
    assert np.isfinite(r.battery_power_w)
