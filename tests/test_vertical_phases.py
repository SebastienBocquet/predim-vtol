"""Vertical phases, transition at a tilt angle, cable mass, mass recap (INC3-006)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.mission.two_phase import TwoPhaseEvaluation
from predimrc_wrapper.propulsion.wiring import awg_for_current
from predimrc_wrapper.propulsion.wiring import conductor_mass_g_per_m
from predimrc_wrapper.propulsion.wiring import default_gauges
from predimrc_wrapper.propulsion.wiring import wiring_mass_kg
from tests.helpers import ParabolicAero


def _solve(name: str, hover: float = 60.0, speeds=(13.0, 16.0), **overrides):
    project = Project.template(name).with_overrides(overrides)
    model = TwoPhaseEvaluation(AircraftModel(project, aero_backend=ParabolicAero()))
    return project, model.solve(hover, speeds)


def test_without_vertical_phases_the_former_formula_holds():
    _, r = _solve(
        "quadplane",
        hover=90.0,
        **{"mission.transition_altitude_m": 0.0, "mission.transition_time_s": 0.0},
    )
    assert [p.name for p in r.phases] == ["hover"]
    for c in r.cruise:
        expected = (
            90.0
            + (r.energy_available_j - r.hover.battery_power_w * 90.0)
            / c.battery_power_w
        )
        assert c.flight_time_s == pytest.approx(expected, rel=1e-12)


def test_climb_power_by_momentum_theory():
    project, r = _solve("multicopter")
    aircraft = AircraftModel(project)
    v_c = project.mission.vertical_climb_speed_m_s
    for hover, climb in zip(r.hover.motors, r.climb.motors, strict=True):
        assert climb.thrust_n == pytest.approx(hover.thrust_n)
        v_h = np.sqrt(
            hover.thrust_n
            / (2 * aircraft.rho * aircraft.disc_area_m2(project.motors[hover.index]))
        )
        ratio = v_c / (2 * v_h)
        # Same factor; the surrogate is read at the (slightly lower) bus voltage of the climb.
        assert climb.power_w / hover.power_w == pytest.approx(
            ratio + np.sqrt(ratio**2 + 1), rel=1e-3
        )
    durations = {p.name: p.duration_s for p in r.phases}
    assert durations["climb"] == pytest.approx(30.0 / 2.0)
    assert durations["descent"] == pytest.approx(30.0 / 1.5)
    assert "transition" not in durations  # multicopter


@pytest.mark.parametrize("theta", [60.0, 90.0])
def test_transition_thrust_of_the_tilting_motors(theta):
    project, r = _solve("tiltrotor", **{"mission.transition_tilt_deg": theta})
    for hover, tr in zip(r.hover.motors, r.transition.motors, strict=True):
        tilting = project.motors[hover.index].role == "tilt"
        factor = 1.0 / np.sin(np.radians(theta)) if tilting else 1.0
        assert tr.thrust_n == pytest.approx(hover.thrust_n * factor, rel=1e-12)
    if theta == 90.0:
        assert r.transition.battery_power_w == pytest.approx(r.hover.battery_power_w)
    else:
        assert r.transition.battery_power_w > r.hover.battery_power_w
        assert r.margins["transition"] < min(
            min(m.power_margin, m.current_margin) for m in r.hover.motors
        )


def test_transition_too_steep_is_the_limit():
    _, r = _solve("tiltrotor", **{"mission.transition_tilt_deg": 30.0})
    assert not r.feasible
    assert r.margins["transition"] < 0  # the battery current may be the first limit hit


def test_winged_aircraft_without_tilting_motor_transitions_at_hover_power():
    _, r = _solve("quadplane")
    transition = next(p for p in r.phases if p.name == "transition")
    assert r.transition is None
    assert transition.battery_power_w == pytest.approx(r.hover.battery_power_w)


def test_cable_mass_against_published_wires():
    """Pimoroni dual silicone wire (1 m red + 1 m black): 20 AWG 14.2 g, 14 AWG 56.3 g."""
    assert conductor_mass_g_per_m(20) == pytest.approx(14.2 / 2, rel=0.02)
    assert conductor_mass_g_per_m(14) == pytest.approx(56.3 / 2, rel=0.02)


def test_gauges_from_the_motor_maximum_current_and_mass_budget():
    project = Project.template("quadplane")
    aircraft = AircraftModel(project)
    _, gauges = default_gauges(project)
    for m, (dc, phase) in zip(project.motors, gauges, strict=True):
        i_max = aircraft.db.motor(project.propulsion_units[m.unit].motor_id).i_max
        assert dc == phase == awg_for_current(i_max)
    assert aircraft.mass["breakdown"]["wiring"] == pytest.approx(
        wiring_mass_kg(project)
    )


def test_mass_recap_adds_up_to_the_total():
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui.mass_view import battery_text  # noqa: PLC0415
    from predimrc_wrapper.ui.mass_view import mass_rows  # noqa: PLC0415

    for name in ("multicopter", "tricopter", "quadplane", "tiltrotor"):
        aircraft = AircraftModel(Project.template(name))
        total = sum(r["mass (g)"] for r in mass_rows(aircraft))
        assert total == pytest.approx(1000 * aircraft.total_mass_kg, abs=0.5)
    assert "mAh" in battery_text(AircraftModel(Project.template("quadplane")))


def test_tricopter_template_keeps_its_measured_mass():
    assert AircraftModel(Project.template("tricopter")).total_mass_kg == pytest.approx(
        1.87, abs=1e-6
    )


def test_charts_units_and_range():
    pytest.importorskip("plotly")
    from predimrc_wrapper.ui import cruise_view as cv  # noqa: PLC0415
    from predimrc_wrapper.ui import hover_view as hv  # noqa: PLC0415

    _, r = _solve("tiltrotor")
    for pair in hv.pairs(r):
        fig = hv.pair_figure(r, pair)
        xs = np.concatenate([np.asarray(t.x, dtype=float) for t in fig.data])
        assert np.nanmax(xs) < 30.0  # every trace in N (grams would be hundreds)
    limit = 1.5 * 3.6 * max(c.v_m_s for c in r.cruise)
    for fig in (cv.power_figure(r), cv.palier_figure(r)):
        xs = np.concatenate([np.asarray(t.x, dtype=float) for t in fig.data])
        assert np.nanmax(xs) <= limit + 1e-9


def test_cruise_tab_shows_the_predimrc_stability_with_its_descriptions():
    pytest.importorskip("plotly")
    from predimrc_wrapper.ui import cruise_view as cv  # noqa: PLC0415

    _, r = _solve("tiltrotor")
    rows = {row["quantity"]: row for row in cv.stability_rows(r)}
    assert list(rows) == [
        "Centrage (% corde moyenne)",
        "Centrage (mm)",
        "Foyer (% corde moyenne)",
        "Foyer (mm)",
        "Marge statique (%)",
        "Volume de stab",
        "Calage stab (°)",
        "Vé longi. (°)",
    ]
    assert rows["Foyer (mm)"]["value"] == round(r.aero_results.neutral_point_mm, 1)
    assert rows["Volume de stab"]["value"] == "-"  # not given by the stub backend
    assert rows["Vé longi. (°)"]["description"] == "Angle entre l'aile et le stab"
    assert all(row["description"] for row in rows.values())


def test_front_yaw_tilt_is_differential():
    theta, delta = 60.0, 15.0
    project, r = _solve(
        "tiltrotor",
        **{
            "mission.transition_tilt_deg": theta,
            "mission.yaw_tilt": "front",
            "mission.yaw_tilt_max_deg": delta,
        },
    )
    front = {i for i, m in enumerate(project.motors) if m.role == "tilt"}
    assert len(r.yaw_cases) == 2  # each side tilted forward in turn
    for case in r.yaw_cases:
        assert set(case.vertical) == front
        assert sorted(case.tilt_deg.values()) == [theta - delta, theta + delta]
        # Three rotors and a CG: the vertical forces are set by the balances
        for hover, worst in zip(r.hover.motors, case.point.motors, strict=True):
            k = case.vertical.get(hover.index, 1.0)
            assert worst.thrust_n == pytest.approx(hover.thrust_n / k, rel=1e-9)
    forward = [
        {i for i, a in c.tilt_deg.items() if a == theta - delta} for c in r.yaw_cases
    ]
    assert forward[0] | forward[1] == front
    assert not forward[0] & forward[1]
    assert r.margins["yaw_tilt"] < r.margins["transition"]
    assert [p.name for p in r.phases] == ["climb", "hover", "transition", "descent"]
    from predimrc_wrapper.ui import two_phase_view as tpv  # noqa: PLC0415

    rows = tpv.hover_tilt_rows(r, front, theta, "front", delta)
    assert [row["phase"] for row in rows if "worst" in row["phase"]] == [
        (
            "worst case yaw (transition 60°, differential yaw ±15°, tilted 45°, "
            "other side 75°)"
        )
    ] * 2


def test_yaw_tilt_of_the_tricopter_rear_rotor_is_lateral():
    delta = 20.0
    project, r = _solve(
        "tricopter", **{"mission.yaw_tilt": "rear", "mission.yaw_tilt_max_deg": delta}
    )
    rear = max(range(len(project.motors)), key=lambda i: project.motors[i].x_mm)
    k = np.cos(np.radians(delta))
    (case,) = r.yaw_cases
    assert case.vertical == {rear: pytest.approx(k)}
    worst = next(m for m in case.point.motors if m.index == rear)
    assert worst.thrust_n == pytest.approx(r.hover.motors[rear].thrust_n / k, rel=1e-9)
    from predimrc_wrapper.ui import two_phase_view as tpv  # noqa: PLC0415

    rows = tpv.hover_tilt_rows(r, set(), 60.0, "rear", delta)
    assert [row["phase"] for row in rows if "worst" in row["phase"]] == [
        f"worst case yaw (yaw 20° lateral, k = {k:.3f})"
    ]


def test_lateral_yaw_tilt_combines_with_the_transition_tilt():
    theta, delta = 60.0, 20.0
    project = Project.template("tiltrotor").with_overrides({
        "mission.transition_tilt_deg": theta,
        "mission.yaw_tilt": "rear",
        "mission.yaw_tilt_max_deg": delta,
    })
    data = project.model_dump()
    rear = max(range(len(project.motors)), key=lambda i: project.motors[i].x_mm)
    data["motors"][rear]["role"] = "tilt"  # the rear rotor tilts for the transition too
    project = Project.model_validate(data)
    r = TwoPhaseEvaluation(AircraftModel(project, aero_backend=ParabolicAero())).solve(
        60.0, (13.0, 16.0)
    )
    assert r.yaw_cases[0].vertical[rear] == pytest.approx(
        np.sin(np.radians(theta)) * np.cos(np.radians(delta))
    )


def test_tilted_split_balances_the_vertical_forces_and_moments():
    from predimrc_wrapper.aircraft.model import hover_thrust_split  # noqa: PLC0415

    x = np.array([-0.2, -0.2, 0.2, 0.2])
    y = np.array([0.2, -0.2, 0.2, -0.2])
    area = np.ones(4)
    k = np.array([np.cos(np.radians(20.0)), 1.0, 1.0, 1.0])
    f = hover_thrust_split(x, y, area, (0.0, 0.0), k)
    assert k @ f == pytest.approx(1.0)
    assert (k * f) @ x == pytest.approx(0.0, abs=1e-12)
    assert (k * f) @ y == pytest.approx(0.0, abs=1e-12)
    # Redundant rotors: the tilted rotor's loss is shared, not carried by it alone
    assert k[0] * f[0] < 0.25
    assert f[0] < 0.25 / k[0]


def test_without_yaw_tilt_no_worst_case():
    _, r = _solve("tiltrotor")
    assert r.yaw_cases == []
    assert np.isnan(r.margins["yaw_tilt"])


def test_yaw_tilt_must_stay_below_the_transition_tilt():
    with pytest.raises(ValueError, match="yaw_tilt_max_deg"):
        Project.template("tiltrotor").with_overrides({
            "mission.yaw_tilt": "front",
            "mission.transition_tilt_deg": 30.0,
            "mission.yaw_tilt_max_deg": 30.0,
        })
