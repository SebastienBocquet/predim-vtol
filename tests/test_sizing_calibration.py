"""Motor pre-selection from a target mass range, and calibration on measured points."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate
from predimrc_wrapper.calibration import calibrate
from predimrc_wrapper.data import default_database
from predimrc_wrapper.mission.powers import SegmentPower
from predimrc_wrapper.sizing import hover_power_w
from predimrc_wrapper.sizing import motor_power_ranges
from tests.helpers import ParabolicAero


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


def test_hover_calibration_matches_the_measurement():
    project = Project.template("tricopter")
    calibrated, report = calibrate(project)
    point = report.points[0]
    assert point.model_after_w == pytest.approx(280.0, rel=1e-6)
    fm = {u: s.figure_of_merit for u, s in calibrated.propulsion_units.items()}
    assert fm["front"] == pytest.approx(fm["rear"])
    assert fm["front"] == pytest.approx(0.65 * point.factor)
    assert calibrated.calibration is None
    aircraft = AircraftModel(calibrated, total_mass_kg=1.87)
    assert float(
        SegmentPower(aircraft).evaluate({"kind": "hover"})["battery_power_w"]
    ) == pytest.approx(280.0, rel=1e-6)


def test_measurement_out_of_range_is_reported():
    project = Project.template("tricopter").with_overrides({
        "calibration.hover.battery_power_w": 20.0
    })
    _, report = calibrate(project)
    assert "bound" in report.points[0].note


@pytest.mark.parametrize(
    ("parameter", "name"), [("auto", "cruise_efficiency"), ("drag", "drag_factor")]
)
def test_quadplane_cruise_calibration(parameter, name):
    project = Project.template("quadplane").with_overrides({
        "calibration": {
            "hover": {"battery_power_w": 360.0},
            "cruise": {"speed_m_s": 15.0, "battery_power_w": 90.0},
            "cruise_parameter": parameter,
        }
    })
    calibrated, report = calibrate(project, ParabolicAero())
    _hover, cruise = report.points
    assert cruise.parameter == name
    assert cruise.model_after_w == pytest.approx(90.0, rel=1e-6)
    # The cruise factor leaves the hover point unchanged.
    aircraft = AircraftModel(calibrated, aero_backend=ParabolicAero())
    assert float(
        SegmentPower(aircraft).evaluate({"kind": "hover"})["battery_power_w"]
    ) == pytest.approx(360.0, rel=1e-6)


def test_multicopter_cruise_calibrates_the_drag():
    project = Project.template("multicopter").with_overrides({
        "calibration": {"cruise": {"speed_m_s": 12.0, "battery_power_w": 260.0}}
    })
    _, report = calibrate(project)
    assert report.points[0].parameter == "drag_factor"
    assert report.points[0].model_after_w == pytest.approx(260.0, rel=1e-6)
    with pytest.raises(ValueError, match="wing-borne"):
        calibrate(
            project.with_overrides({
                "calibration.cruise_parameter": "propeller_efficiency"
            })
        )


def test_evaluate_reports_the_calibration():
    result = evaluate(Project.template("tricopter"))
    assert result.metadata["calibration"][0]["point"] == "hover"
    assert result.metadata["calibration"][0]["model_after_w"] == pytest.approx(
        280.0, rel=1e-6
    )
