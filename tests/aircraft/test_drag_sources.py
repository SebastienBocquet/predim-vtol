"""Drag sources with V-arms, PredimRC shapes and the model shown (INC2-006)."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft.drag_sources import drag_report
from predimrc_wrapper.aircraft.drag_sources import v_arm_segments

V_ARMS = {"name": "V-arms", "kind": "v_arms", "shape": "Non profilé", "thickness_mm": 12.0}


def _tricopter(**source):
    return Project.template("tricopter").with_overrides({"drag_sources": [{**V_ARMS, **source}]})


def test_tricopter_v_arms_hand_calculation():
    """Roots at the centre, 40 mm below the motors; arms of 300 mm at ±60° and 180° from the nose."""
    project = _tricopter()
    (result,) = drag_report(project)
    front = np.sqrt(150.0**2 + 259.8**2 + 40.0**2)  # motor at (-150, ±259.8) in the template
    rear = np.sqrt(300.0**2 + 40.0**2)
    sin_front = np.sqrt(1 - (150.0 / front) ** 2)
    sin_rear = np.sqrt(1 - (300.0 / rear) ** 2)
    expected = 12e-3 * 1e-3 * (2 * front * sin_front + rear * sin_rear)
    assert result.frontal_area_m2 == pytest.approx(expected, rel=1e-9)
    assert result.cds_m2 == pytest.approx(1.0 * expected, rel=1e-9)
    assert result.area_from == "geometry" and "Calculs1!AD3" in result.coefficient_source
    drag = AircraftModel(project).drag(10.0)["drag_n"]
    body = AircraftModel(Project.template("tricopter")).drag(10.0)["drag_n"]
    assert float(drag - body) == pytest.approx(0.5 * AircraftModel(project).rho * 100 * expected, rel=1e-9)


def test_area_follows_motors_and_user_area_overrides():
    a = drag_report(_tricopter())[0].frontal_area_m2
    data = _tricopter().model_dump()
    data["motors"][0]["y_mm"] = 350.0
    b = drag_report(Project.model_validate(data))[0].frontal_area_m2
    assert b > a
    user = drag_report(_tricopter(frontal_area_dm2=1.5))[0]
    assert user.area_from == "user" and user.cds_m2 == pytest.approx(0.015)


def test_quadplane_arms_from_under_the_fuselage():
    project = Project.template("quadplane")
    project = project.with_overrides({"drag_sources": [{**V_ARMS, "shape": "Mixte"}]})
    arms = v_arm_segments(project.drag_sources[0], project)
    assert len(arms) == 4
    assert arms[0].root == pytest.approx((50.0, 42.5, -57.5))
    result = drag_report(project)[0]
    assert result.cd == 0.6 and result.model == "V-arms, shape Mixte"


def test_every_source_reports_its_model():
    for result in drag_report(Project.template("quadplane")):
        assert result.model and result.formula and result.coefficient_source and result.cds_m2 > 0


def test_shape_validated():
    with pytest.raises(ValidationError, match="unknown shape"):
        _tricopter(shape="Carré")
    with pytest.raises(ValidationError, match="thickness_mm"):
        Project.template("tricopter").with_overrides({"drag_sources": [{"name": "x", "kind": "v_arms", "shape": "Mixte"}]})


def test_geometry_draws_the_arms():
    pytest.importorskip("plotly")
    from predimrc_wrapper.ui import geometry  # noqa: PLC0415

    fig = geometry.top_view(_tricopter())
    assert sum(t.name == "V-arm" for t in fig.data) == 3
    assert sum(t.name == "V-arm" for t in geometry.front_view(_tricopter()).data) == 3
