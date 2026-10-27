"""PredimRC profiles, accessory migration and iso-model cruise curve (INC2-005)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft.aero import to_predimrc
from predimrc_wrapper.aircraft.cruise import cruise_curve
from predimrc_wrapper.aircraft.cruise import target_points
from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.data.drag_shapes import drag_shapes
from predimrc_wrapper.predimrc_wrapper import ImposedSpeed
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
    project = Project.template("quadplane").with_overrides({
        "drag_sources": [],
        "booms": None,
    })
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


_K_3D = 0.784
_BLOCK_CZ = _K_3D * np.array([0.01, 0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0, 1.15])
"""PredimRC imposed-speed grid (airfoil Cz 0.01, 0.1, 0.25 → 1.15) in wing Cz."""


class ImposedAero(ParabolicAero):
    """Parabolic polar up to Cz 0.9 plus imposed-speed blocks on the PredimRC grid.

    The last block node (Cz 0.902) is beyond the polar, in a stall drag rise (×4), as in
    the SD7003 workbook; ``bias`` scales the block powers.
    """

    def __init__(self, bias: float = 1.0) -> None:
        super().__init__(cz_max=0.9)
        self.bias = bias

    def evaluate(self, wing, stab, fus, settings):
        r = super().evaluate(wing, stab, fus, settings)
        for k, vx_kmh in ((1, settings.vx1_kmh), (2, settings.vx2_kmh)):
            if vx_kmh is None:
                continue
            v = vx_kmh / 3.6
            cx = self.cx0 + self.k * _BLOCK_CZ**2
            cx[self.cz_max < _BLOCK_CZ] *= 4.0
            drag = 0.5 * self.rho * self.area_m2 * v**2 * cx * self.bias
            r.imposed[k] = ImposedSpeed(v, _BLOCK_CZ.copy(), drag, drag * v)
        return r


def test_at_cz_parabola_without_the_stall_node():
    v, cz = 12.0, _BLOCK_CZ
    drag = 0.2 + 1.5 * cz**2
    drag[-1] *= 4.0  # stall drag rise beyond the polar
    block = ImposedSpeed(v, cz, drag, drag * v)
    d, p = block.at_cz(0.7, cz_max=0.862)
    assert d == pytest.approx(0.2 + 1.5 * 0.7**2, rel=1e-12)  # exact on a parabola
    assert p == pytest.approx(d * v, rel=1e-12)
    assert np.isnan(block.at_cz(0.798, cz_max=0.862)[0])  # beyond the last usable node
    assert block.at_cz(0.798)[0] > 1.1 * (
        0.2 + 1.5 * 0.798**2
    )  # the bias that was fixed
    assert np.isnan(block.at_cz(0.001)[1])  # no extrapolation


def test_wing_cz_includes_the_stabiliser_lift():
    curve = cruise_curve(
        AircraftModel(Project.template("quadplane"), aero_backend=ParabolicAero())
    )
    v = 15.0
    cz_lift = 2 * curve.mass_kg * GRAVITY / (curve.rho * curve.wing_area_m2 * v**2)
    # ParabolicAero: no stabiliser, g = 9.81 in the polar.
    assert curve.wing_cz(v) == pytest.approx(cz_lift * 9.81 / GRAVITY, rel=1e-9)
    ref = (
        2 * curve.mass_kg * GRAVITY / (curve.rho * curve.wing_area_m2 * curve.v_m_s**2)
    )
    curve.cz_wing = 1.04 * ref + 0.012  # a download stabiliser: more wing lift
    assert curve.wing_cz(v) == pytest.approx(1.04 * cz_lift + 0.012, rel=1e-9)


def _speed(curve, cz: float) -> float:
    return float(
        np.sqrt(2 * curve.mass_kg * 9.81 / (curve.rho * curve.wing_area_m2 * cz))
    )


def test_target_points_block_and_stall_edge_fallback():
    project = Project.template("quadplane")
    aircraft = AircraftModel(project, aero_backend=ImposedAero())
    base = cruise_curve(aircraft)
    speeds = (_speed(base, 0.6), _speed(base, 0.85))
    curve, points, iso = target_points(aircraft, speeds)
    p1, p2 = points
    assert p1.source == "block"
    assert p1.cz_trim == pytest.approx(0.6, rel=1e-3)
    v = p1.v_m_s
    exact = 0.5 * curve.rho * curve.wing_area_m2 * v**3 * (0.03 + 0.04 * p1.cz_trim**2)
    assert p1.power_predimrc_w == pytest.approx(exact, rel=1e-9)
    assert p2.source == "polar"  # Cz 0.85 > 0.784, the 0.902 node is beyond the polar
    assert p2.drag_predimrc_n == pytest.approx(
        np.interp(p2.v_m_s, curve.v_m_s, curve.drag_predimrc_n), rel=1e-12
    )
    assert iso.imposed_max_rel_dev < 1e-12
    assert len(iso.warnings) == 1
    assert iso.warnings[0].startswith("V2: trimmed Cz 0.850")


def test_target_points_warn_on_a_curve_gap():
    aircraft = AircraftModel(
        Project.template("quadplane"), aero_backend=ImposedAero(bias=1.1)
    )
    base = cruise_curve(aircraft)
    _curve, points, iso = target_points(
        aircraft, (_speed(base, 0.6), _speed(base, 0.4))
    )
    assert all(p.source == "block" for p in points)
    assert [w[:3] for w in iso.warnings] == ["V1:", "V2:"]
    assert "differ by -" in iso.warnings[0]
