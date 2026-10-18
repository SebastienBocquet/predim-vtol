"""Tests of the aircraft package (MVP-004)."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest
from pydantic import ValidationError

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import DragModel
from predimrc_wrapper.aircraft import OverrideError
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import ProjectError
from predimrc_wrapper.aircraft import SpeedPolar
from predimrc_wrapper.aircraft import defaults_left
from tests.conftest import requires_excel


@pytest.mark.parametrize("name", ["quadplane", "multicopter", "tricopter", "tiltrotor"])
def test_template_round_trip(tmp_path, name):
    project = Project.template(name)
    path = tmp_path / "p.yaml"
    project.save(path)
    assert Project.load(path) == project


def test_overrides():
    p = Project.template("quadplane").with_overrides({"battery.mass_g": 700, "aero.wing.length_mm.1": 320})
    assert p.battery.mass_g == 700
    assert p.aero.wing.length_mm[1] == 320


def test_unknown_override_suggests():
    with pytest.raises(OverrideError, match="battery.chemistry"):
        Project.template("quadplane").with_overrides({"battery.chemestry": "lipo"})


def test_out_of_bounds_override():
    with pytest.raises(ValidationError, match="n_series"):
        Project.template("quadplane").with_overrides({"battery.n_series": 0})


def test_architecture_invariants():
    data = Project.template("multicopter").model_dump()
    data["body_frontal_area_dm2"] = None
    with pytest.raises(ValidationError, match="body_frontal_area_dm2"):
        Project.model_validate(data)
    data = Project.template("quadplane").model_dump()
    data["motors"] = [m for m in data["motors"] if m["role"] != "cruise"]
    with pytest.raises(ValidationError, match="cruise motor"):
        Project.model_validate(data)
    data = Project.template("multicopter").model_dump()
    data["motors"][0]["role"] = "tilt"
    with pytest.raises(ValidationError, match="role lift"):
        Project.model_validate(data)
    data = Project.template("multicopter").model_dump()
    data["motors"][0]["unit"] = "nope"
    with pytest.raises(ValidationError, match="unknown propulsion units"):
        Project.model_validate(data)


def test_overlapping_propellers():
    with pytest.raises(ValidationError, match="overlap"):
        Project.template("multicopter").with_overrides({"propulsion_units.lift.prop_diameter_in": 18})


def test_unknown_motor():
    with pytest.raises(ValidationError, match="Unknown motor"):
        Project.template("multicopter").with_overrides({"propulsion_units.lift.motor_id": "nope"})


def test_defaults_left():
    assert "mission.reserve_fraction" in defaults_left(Project.template("multicopter"))


def test_mass_budget_exact():
    model = AircraftModel(Project.template("multicopter"))
    unit = model.units["lift"].mass_kg
    expected = 0.5 + 0.3 + 0.12 + 4 * unit + 0.7
    assert model.total_mass_kg == pytest.approx(expected, rel=1e-12)
    assert model.mass["margin_mass"] == pytest.approx(1 - expected / 3.0)


def test_drag_formulas():
    drag = DragModel()
    boom = {"kind": "boom", "count": 2, "diameter_m": 0.016, "length_m": 0.65}
    rotor = {"kind": "stopped_rotor", "count": 4, "n_blades": 2, "blade_chord_m": 0.025, "radius_m": 0.165}
    assert drag.cds(boom) == pytest.approx(2 * (0.005 * np.pi * 0.016 * 0.65 + 0.15 * np.pi * 0.016**2 / 4))
    assert drag.cds(rotor) == pytest.approx(4 * 2 * 0.025 * 0.165 * 0.05)


def test_drag_with_polar_equal_dynamic_pressure():
    polar = SpeedPolar(v_m_s=np.array([10.0, 20.0, 30.0]), drag_n=np.array([2.0, 1.5, 2.5]), rho=1.2)
    y = DragModel().evaluate({"sources": [], "v_m_s": 20.0 * np.sqrt(1.2 / 1.0), "rho": 1.0, "polar": polar})
    assert float(y["drag_n"]) == pytest.approx(1.5)
    assert y["v_min_m_s"] == pytest.approx(10.0 * np.sqrt(1.2))
    outside = DragModel().evaluate({"sources": [], "v_m_s": 5.0, "rho": 1.2, "polar": polar})
    assert np.isnan(outside["drag_n"])


def test_quadplane_without_backend():
    model = AircraftModel(Project.template("quadplane"))
    with pytest.raises(ProjectError, match="PredimRC backend"):
        model.drag(15.0)


def test_rotor_positions():
    quad = AircraftModel(Project.template("quadplane")).rotor_positions_m()
    assert len(quad) == 4 and {round(y, 3) for _, y in quad} == {-0.3, 0.3}
    multi = AircraftModel(Project.template("multicopter")).rotor_positions_m()
    assert len(multi) == 4
    assert all(np.hypot(x, y) == pytest.approx(0.3, abs=1e-4) for x, y in multi)


def test_multicopter_without_xlwings():
    code = (
        "import sys; sys.modules['xlwings'] = None\n"
        "from predimrc_wrapper.aircraft import AircraftModel, Project\n"
        "m = AircraftModel(Project.template('multicopter'))\n"
        "print(float(m.drag(10.0)['drag_n']))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert float(out.stdout) > 0


@pytest.mark.slow
@requires_excel
def test_quadplane_drag_through_predimrc(predimrc):
    model = AircraftModel(Project.template("quadplane"), aero_backend=predimrc)
    y = model.drag(np.array([15.0, 18.0]))
    assert np.all(np.isfinite(y["drag_n"])) and np.all(y["drag_n"] > 0)
    calls = len(model.aero._cache)
    model.drag(16.0)
    assert len(model.aero._cache) == calls
