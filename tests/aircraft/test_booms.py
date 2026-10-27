"""Booms: geometry, drag on the frontal area, cable paths (REQ-CFG-014, REQ-CFG-004)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft.booms import anchor
from predimrc_wrapper.aircraft.booms import boom_drag
from predimrc_wrapper.aircraft.booms import booms
from predimrc_wrapper.aircraft.drag import DragModel
from predimrc_wrapper.data.boom_sections import boom_section
from predimrc_wrapper.data.boom_sections import boom_sections
from predimrc_wrapper.propulsion.wiring import default_layout

CF, CD_END = DragModel().p.boom_cf, DragModel().p.boom_cd_end


def _diagonal(name: str, section: str = "round", **kw) -> Project:
    return Project.template(name).with_overrides({
        "booms": {"layout": "diagonal", "section": section, "thickness_mm": 16.0, **kw}
    })


def test_sections_have_a_source():
    assert set(boom_sections()) == {"round", "square", "profiled"}
    for s in boom_sections().values():
        assert s.cd > 0
        assert "Hoerner" in s.source
    with pytest.raises(KeyError, match="Known"):
        boom_section("hexagonal")


@pytest.mark.parametrize("section", ["round", "square", "profiled"])
def test_diagonal_boom_drag_by_hand(section):
    project = _diagonal("tricopter", section)
    drags = boom_drag(project, CF, CD_END)
    assert len(drags) == 3  # one boom per lift motor
    cd = boom_section(section).cd
    t, chord = 0.016, 4 * 0.016
    perimeter = {"round": np.pi * t, "square": 4 * t, "profiled": 2.04 * chord}[section]
    for d in drags:
        m = project.motors[d.boom.motors[0]]
        length = np.hypot(m.x_mm, m.y_mm) / 1000  # frame: anchor at the centre, z = 0
        sin = abs(m.y_mm) / 1000 / length
        frontal = t * length * sin
        assert d.frontal_area_m2 == pytest.approx(frontal)
        assert d.cd_effective == pytest.approx(cd * sin**2)
        assert d.cds_m2 == pytest.approx(
            cd * sin**2 * frontal + CF * perimeter * length
        )


def test_rear_boom_aligned_with_the_flow_has_friction_only():
    project = _diagonal("tricopter")
    rear = boom_drag(project, CF, CD_END)[2]
    assert rear.boom.angle_to_flow_deg == pytest.approx(0.0)
    assert rear.frontal_area_m2 == pytest.approx(0.0)
    assert rear.cds_m2 == pytest.approx(CF * np.pi * 0.016 * rear.boom.length_mm / 1000)


def test_diagonal_booms_anchored_under_the_fuselage():
    project = _diagonal("quadplane")
    x_a, half, z_a = anchor(project, project.booms)
    fus = project.aero.fuselage
    assert (x_a, half, z_a) == (
        0.25 * project.aero.wing.root_chord_mm,
        fus.width_mm / 2,
        -fus.height_mm / 2,
    )
    for b in booms(project):
        m = project.motors[b.motors[0]]
        expected = np.linalg.norm([
            m.x_mm - x_a,
            m.y_mm - np.sign(m.y_mm) * half,
            0.0 - z_a,
        ])
        assert b.length_mm == pytest.approx(expected)


def test_parallel_booms_equal_the_former_manual_sources():
    """The templates' booms replace the manual 'boom' drag sources with the same drag."""
    model = DragModel()
    for name, length in (("quadplane", 0.65), ("tiltrotor", 0.25)):
        project = Project.template(name)
        assert project.booms.layout == "parallel"
        total = sum(d.cds_m2 for d in boom_drag(project, CF, CD_END))
        manual = model.cds({
            "kind": "boom",
            "count": 2,
            "diameter_m": 0.016,
            "length_m": length,
        })
        assert total == pytest.approx(manual)


def test_booms_are_in_the_aircraft_drag():
    project = _diagonal("tricopter")
    sources = AircraftModel(project).drag_sources()
    assert len(sources) == 3 + len(project.drag_sources)
    assert sum(s["cds_m2"] for s in sources[:3]) == pytest.approx(
        sum(d.cds_m2 for d in boom_drag(project, CF, CD_END))
    )


def test_cables_follow_the_diagonal_booms():
    project = _diagonal("quadplane").with_overrides({
        "wiring": {"lift_esc": "separate"}
    })
    layout = default_layout(project)
    x_a, half, z_a = anchor(project, project.booms)
    for b, boom in zip(
        [b for b in layout.branches if project.motors[b.motor_index].role == "lift"],
        booms(project),
        strict=True,
    ):
        expected = (
            abs(b.esc_x_mm - x_a)
            + np.hypot(half - abs(b.esc_y_mm), z_a)
            + boom.length_mm
        )
        assert b.phase_length_mm == pytest.approx(expected)
