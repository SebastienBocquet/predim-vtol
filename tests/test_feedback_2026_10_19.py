"""Feedback of 2026-10-19: CG check against PredimRC, two-phase calibration (INC3-005)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.calibration import calibrate_two_phase
from tests.helpers import ParabolicAero


class _Aero:
    """PredimRC results of the reference wing: CG 30.1 % / 66.57 mm, neutral point 35.1 % / 75.77 mm."""

    cg, foyer = 30.09835535242778, 35.09835535242778
    cg_mm, neutral_point_mm = 66.57450015780746, 75.77225953432963

    @property
    def mac_mm(self) -> float:
        return 100.0 * (self.neutral_point_mm - self.cg_mm) / (self.foyer - self.cg)


def test_mac_from_predimrc_equals_the_wing_mac():
    """PredimRC's CG in mm is measured from the wing root leading edge, like the motor x."""
    w = Project.template("quadplane").aero.wing
    c = [w.root_chord_mm, *w.tip_chord_mm]
    x = [0.0, *w.le_offset_mm]
    s = i2 = ixc = 0.0
    for k, length in enumerate(w.length_mm):
        c1, c2, x1, x2 = c[k], c[k + 1], x[k], x[k + 1]
        s += length * (c1 + c2) / 2
        i2 += length * (c1 * c1 + c1 * c2 + c2 * c2) / 3
        ixc += length * (2 * c1 * x1 + c1 * x2 + c2 * x1 + 2 * c2 * x2) / 6
    aero = _Aero()
    assert aero.mac_mm == pytest.approx(i2 / s)
    assert aero.cg_mm - aero.cg / 100 * aero.mac_mm == pytest.approx(ixc / s)


def test_cg_check_levels():
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui.cg_view import cg_check  # noqa: PLC0415

    aero = _Aero()
    assert cg_check(None, 60.0, 5.0)[0] == "none"
    assert cg_check(aero, None, 5.0)[0] == "unset"
    level, text = cg_check(aero, 68.0, 5.0)
    assert level == "ok"
    level, text = cg_check(aero, 20.0, 5.0)
    assert level == "warning"
    assert "static margin would be 30.3 %" in text


def test_two_phase_calibration_matches_the_measurements():
    project = Project.template("multicopter").with_overrides({
        "calibration": {
            "hover": {"battery_power_w": 240.0},
            "cruise": {"speed_m_s": 12.0, "battery_power_w": 150.0},
        }
    })
    calibrated, report = calibrate_two_phase(project)
    assert calibrated.calibration is None
    hover, cruise = report.points
    assert hover.parameter == "hover_power_factor"
    assert hover.model_after_w == pytest.approx(240.0, rel=1e-6)
    assert cruise.parameter == "drag_factor"
    assert cruise.model_after_w == pytest.approx(150.0, rel=1e-6)
    assert calibrated.mission.hover_power_factor == pytest.approx(hover.factor)
    result = evaluate_two_phase(project)
    assert result.hover.battery_power_w == pytest.approx(240.0, rel=1e-6)
    assert [p["point"] for p in result.metadata["calibration"]] == ["hover", "cruise"]


def test_calibration_of_a_winged_cruise_point():
    project = Project.template("quadplane").with_overrides({
        "calibration": {"cruise": {"speed_m_s": 15.0, "battery_power_w": 90.0}}
    })
    calibrated, report = calibrate_two_phase(project, ParabolicAero())
    assert report.points[0].model_after_w == pytest.approx(90.0, rel=1e-6)
    assert calibrated.mission.drag_factor == pytest.approx(report.points[0].factor)


def test_tiltrotor_template_cg_is_the_predimrc_cg():
    project = Project.template("tiltrotor")
    assert project.cg_x_mm == pytest.approx(66.6)
    assert set(project.propulsion_units) == {"front", "rear"}
    assert evaluate_two_phase(project, backend=ParabolicAero()).feasible
