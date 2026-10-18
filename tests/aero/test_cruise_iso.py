"""PredimRC profiles, accessory migration and iso-model cruise curve (INC2-005)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft.aero import to_predimrc
from predimrc_wrapper.aircraft.cruise import cruise_curve
from predimrc_wrapper.aircraft.cruise import target_points
from predimrc_wrapper.data.drag_shapes import drag_shapes
from predimrc_wrapper.predimrc_wrapper import PredimRCError
from predimrc_wrapper.predimrc_wrapper import discover_profiles
from predimrc_wrapper.predimrc_wrapper import workbook_path
from tests.conftest import requires_excel
from tests.helpers import ParabolicAero


def test_profiles_discovered_by_naming_convention(tmp_path):
    for name in (
        "PredimRC_SD7003.xls",
        "PredimRC_NACA2412.xlsm",
        "PredimRC_SD7003.old.bak.xls",
        "notes.txt",
    ):
        (tmp_path / name).write_bytes(b"")
    assert sorted(discover_profiles(tmp_path)) == ["NACA2412", "SD7003"]
    assert workbook_path(tmp_path, "NACA2412").name == "PredimRC_NACA2412.xlsm"
    with pytest.raises(
        FileNotFoundError, match="Available: \\['NACA2412', 'SD7003'\\]"
    ):
        workbook_path(tmp_path, "E387")
    (tmp_path / "PredimRC_SD7003.xlsx").write_bytes(b"")
    with pytest.raises(PredimRCError, match="Two workbooks"):
        discover_profiles(tmp_path)


def test_shapes_from_predimrc():
    shapes = drag_shapes()
    assert {k: v.cd for k, v in shapes.items()} == {
        "Profilé": 0.2,
        "Mixte": 0.6,
        "Non profilé": 1.0,
    }
    assert all("Calculs1!AD3" in s.source for s in shapes.values())


def test_accessory_of_an_old_file_is_dropped():
    data = Project.template("quadplane").to_dict()
    n_sources = len(data["drag_sources"])
    data["aero"]["fuselage"].update({
        "accessory_area_dm2": 0.5,
        "accessory_shape": "Mixte",
    })
    with pytest.warns(UserWarning, match="ignored: PredimRC runs with 0"):
        project = Project.model_validate(data)
    assert len(project.drag_sources) == n_sources  # no source created from PredimRC
    assert "accessory_area_dm2" not in project.aero.fuselage.model_dump()


def test_predimrc_inputs_accessory_off_and_atmosphere():
    project = Project.template("quadplane").with_overrides({
        "environment.altitude_m": 250.0,
        "environment.delta_isa_k": 6.625,
    })
    inputs = to_predimrc(project.aero, 2.0, project.environment, (45.0, 55.0))
    assert inputs["fus"].accessory_surface == 0.0
    s = inputs["settings"]
    assert s.altitude_m == 250.0
    assert s.temperature_c == pytest.approx(20.0)
    assert (s.vx1_kmh, s.vx2_kmh) == (45.0, 55.0)


def test_curve_with_sources_and_parabolic_speeds():
    """Parabolic polar: V_minP / V_maxL/D = 3^-0.25; sources add ½ρV³ΣCdS exactly."""
    project = Project.template("quadplane").with_overrides({"drag_sources": []})
    aircraft = AircraftModel(project, aero_backend=ParabolicAero())
    curve = cruise_curve(aircraft)
    np.testing.assert_allclose(curve.power_total_w, curve.power_predimrc_w, rtol=1e-12)
    v_p, v_d = curve.speeds()
    assert v_p / v_d == pytest.approx(3**-0.25, rel=0.02)
    with_sources = AircraftModel(
        Project.template("quadplane"), aero_backend=ParabolicAero()
    )
    c2 = cruise_curve(with_sources)
    np.testing.assert_allclose(
        c2.power_total_w - c2.power_predimrc_w,
        0.5 * c2.rho * c2.v_m_s**3 * c2.cds_sources_m2,
        rtol=1e-12,
    )


def test_target_points_without_imposed_blocks():
    aircraft = AircraftModel(
        Project.template("quadplane"), aero_backend=ParabolicAero()
    )
    curve, points, iso = target_points(aircraft, (12.0, 15.0))
    assert [round(p.v_m_s, 6) for p in points] == [12.0, 15.0]
    expected = (
        np.interp(12.0, curve.v_m_s, curve.drag_predimrc_n)
        + 0.5 * curve.rho * 12.0**2 * curve.cds_sources_m2
    )
    assert points[0].drag_n == pytest.approx(expected, rel=1e-12)
    assert points[0].aero_power_w == pytest.approx(points[0].drag_n * 12.0, rel=1e-12)
    assert np.isnan(iso.imposed_max_rel_dev)


@pytest.mark.slow
@requires_excel
def test_iso_model_on_reference_case(predimrc):
    project = Project.template("quadplane").with_overrides({
        "environment.altitude_m": 250.0
    })
    aircraft = AircraftModel(project, aero_backend=predimrc)
    curve, _points, iso = target_points(aircraft)
    assert iso.passed, iso
    assert curve.rho == pytest.approx(1.193, abs=2e-3)
    v_p, v_d = curve.speeds()
    assert iso.imposed_speeds_kmh == pytest.approx([
        round(3.6 * v_p, 2),
        round(3.6 * v_d, 2),
    ])
    assert all(abs(g) < 0.02 for g in iso.curve_gaps)
