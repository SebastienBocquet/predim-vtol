"""Motor pre-selection from a target mass range (the calibration: test_feedback_2026_10_19)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.data import default_database
from predimrc_wrapper.sizing import hover_power_w
from predimrc_wrapper.sizing import motor_power_ranges


def test_hover_power_law_reference_point():
    spec = Project.template("tricopter").sizing
    assert hover_power_w(spec, 1.87) == pytest.approx(280.0)
    assert hover_power_w(spec, 3.74) == pytest.approx(560.0)
    steep = spec.model_copy(update={"mass_exponent": 1.5})
    assert hover_power_w(steep, 3.74) == pytest.approx(280.0 * 2**1.5)


def test_tricopter_power_ranges():
    project = Project.template("tricopter")
    ranges = {r.unit: r for r in motor_power_ranges(project)}
    assert set(ranges) == {"front", "rear"}
    # CG at the centre: equal thrusts; the smaller rear propeller needs more power.
    assert ranges["rear"].need_high_w > ranges["front"].need_high_w
    # 1.7-2.0 kg, T/W 1.5: one third of 255-300 W hover times 1.5^1.5 for the front.
    total_low = 280.0 * 1.7 / 1.87 * 1.5**1.5
    assert ranges["front"].need_low_w == pytest.approx(
        total_low * ranges["front"].need_low_w / total_low
    )
    assert 120 < ranges["front"].need_low_w < ranges["front"].need_high_w < 200
    db = default_database()
    for r in ranges.values():
        assert r.accepted_high_w == pytest.approx(1.3 * r.need_high_w)
        assert all(
            r.need_low_w <= db.motor(m).p_max <= r.accepted_high_w for m in r.candidates
        )


def test_cruise_unit_range_uses_the_cruise_law():
    project = Project.template("quadplane")
    cruise = next(r for r in motor_power_ranges(project) if r.unit == "cruise")
    s = project.sizing
    expected = (
        s.target_mass_kg[1]
        * 9.81
        * s.cruise_max_speed_m_s
        / (s.cruise_lift_to_drag * s.cruise_overall_efficiency)
    )
    assert cruise.need_high_w == pytest.approx(expected)


def test_no_sizing_block():
    with pytest.raises(ValueError, match="sizing"):
        motor_power_ranges(
            Project.template("tricopter").with_overrides({"sizing": None})
        )
