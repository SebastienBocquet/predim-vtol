"""MVP-007: GUI helpers (geometry, form levels, save/load) and an app smoke test."""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.aircraft import layouts  # noqa: E402
from predimrc_wrapper.aircraft.project import BatterySpec  # noqa: E402
from predimrc_wrapper.aircraft.project import PropulsionSpec  # noqa: E402
from predimrc_wrapper.aircraft.project import WingSpec  # noqa: E402
from predimrc_wrapper.mission.scenario import Segment  # noqa: E402
from predimrc_wrapper.ui import charts  # noqa: E402
from predimrc_wrapper.ui import forms  # noqa: E402
from predimrc_wrapper.ui import geometry  # noqa: E402
from predimrc_wrapper.ui import state  # noqa: E402
from tests.conftest import ROOT  # noqa: E402

APP = ROOT / "src" / "predimrc_wrapper" / "ui" / "app.py"


# --- geometry -------------------------------------------------------------------


def test_reference_half_span():
    project = Project.template("quadplane")
    outline = geometry.wing_outline(
        project.aero.wing, project.aero.fuselage.width_mm / 2
    )
    assert outline.half_span_mm == pytest.approx(912.5)
    assert max(outline.y) == pytest.approx(912.5)
    # Absolute LE offset of the last panel (150 mm) and its tip chord (50 mm).
    assert outline.x[4] == 150
    assert outline.x[5] == 200


@pytest.mark.parametrize(
    ("name", "n_lift", "n_cruise"),
    [
        ("quadplane", 4, 1),
        ("multicopter", 4, 0),
        ("tricopter", 3, 0),
        ("tiltrotor", 3, 0),
    ],
)
def test_one_disc_per_motor(name, n_lift, n_cruise):
    project = Project.template(name)
    fig = geometry.top_view(project)
    lift = sum(t.name in ("lift rotor", "tilt rotor") for t in fig.data)
    assert lift == n_lift
    assert sum(t.name == "cruise rotor" for t in fig.data) == n_cruise
    assert geometry.front_view(project).data


def test_six_arms_layout():
    data = Project.template("multicopter").model_dump()
    data["motors"] = layouts.multirotor(6, 400)
    project = Project.model_validate(data)
    assert sum(t.name == "lift rotor" for t in geometry.top_view(project).data) == 6


def test_vtail_dihedral():
    stab = Project.template("quadplane").aero.stab
    assert geometry.stab_dihedral_deg(stab) == pytest.approx(30.0)
    assert (
        geometry.stab_dihedral_deg(stab.model_copy(update={"opening": "--- / 180"}))
        == 0.0
    )


# --- form levels ----------------------------------------------------------------


def test_badges():
    info = PropulsionSpec.model_fields["prop_mass_g"]
    assert forms.field_badge(info, info.default) == "default"
    assert forms.field_badge(info, 31.0) == "entered"
    assert forms.field_label("prop_mass_g", info, 31.0).endswith("— entered")
    required = PropulsionSpec.model_fields["motor_id"]
    assert forms.field_badge(required) == "required"
    assert forms.field_label("motor_id", required).endswith("*")
    assert (
        forms.field_badge(PropulsionSpec.model_fields["figure_of_merit"]) == "advanced"
    )


def test_missing_required_disables_run():
    data = state.load_template("multicopter")
    assert state.run_enabled(state.check(data))
    broken = copy.deepcopy(data)
    del broken["propulsion_units"]["lift"]["prop_diameter_in"]
    result = state.check(broken)
    assert "propulsion_units.lift.prop_diameter_in" in result.missing
    assert not state.run_enabled(result)
    broken = copy.deepcopy(data)
    broken["battery"]["n_series"] = None
    assert "battery.n_series" in state.check(broken).missing


def test_invalid_value_error_by_path():
    data = state.load_template("multicopter")
    data["battery"]["mass_g"] = -5
    result = state.check(data)
    assert "battery.mass_g" in result.errors
    assert not result.missing


def test_panel_rows_and_table_rows():
    assert forms.panel_fields(WingSpec) == [
        "tip_chord_mm",
        "length_mm",
        "le_offset_mm",
        "twist_deg",
        "dihedral_deg",
    ]
    assert forms.panels_to_rows({"length_mm": [1.0, 2.0]}, ["length_mm"], 3) == {
        "length_mm": [1.0, 2.0, 2.0]
    }
    rows = [
        {
            "kind": "cruise",
            "duration_s": float("nan"),
            "distance_m": None,
            "speed": "12.5",
            "until_reserve": True,
        },
        {"kind": "hover", "duration_s": 60.0, "speed": "optimal_range"},
    ]
    items = forms.rows_to_items(rows, Segment)
    assert items[0] == {"kind": "cruise", "speed": 12.5, "until_reserve": True}
    assert Segment(**items[1]).duration_s == 60
    assert forms.bounds(BatterySpec.model_fields["n_series"]) == (1, 14)


# --- save / load ------------------------------------------------------------------


def test_gui_save_api_load_round_trip(tmp_path):
    data = state.load_template("quadplane")
    data["battery"]["mass_g"] = 812.5
    path = state.save_project(data, tmp_path / "gui.yaml")
    assert Project.load(path) == Project.model_validate(data)


def test_outdated_flag():
    app = state.AppState(state.load_template("multicopter"))
    app.result, app.result_key = object(), state.project_key(app.data)
    assert not app.outdated
    app.data["battery"]["mass_g"] = 999
    assert app.outdated


# --- charts and app -----------------------------------------------------------------


def test_charts_on_multicopter():
    from predimrc_wrapper.api import evaluate  # noqa: PLC0415

    result = evaluate(Project.template("multicopter"))
    tiles = charts.kpis(result)
    assert tiles[0].label == "Flight time"
    assert tiles[0].value == pytest.approx(result.flight_time_min)
    assert charts.power_figure(result).data
    assert len(charts.segment_rows(result)) == len(result.segments)
    assert charts.mass_figure(result).data


def test_app_smoke_multicopter():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    run = next(b for b in at.button if b.label == "Run")
    assert not run.disabled
    run.click().run()
    assert not at.exception, at.exception
    labels = [m.label for m in at.metric]
    assert "Flight time" in labels
    assert all("Outdated" not in w.value for w in at.warning)
    result = at.session_state["app"].result
    # Editing a field keeps the result (no re-run) and flags it as outdated.
    gen = at.session_state["app"].generation
    at.number_input(key=f"{gen}:battery.mass_g").set_value(900.0).run()
    assert not at.exception, at.exception
    assert at.session_state["app"].data["battery"]["mass_g"] == 900.0
    assert at.session_state["app"].result is result
    assert any("Outdated" in w.value for w in at.warning)


def test_cli_argv():
    from predimrc_wrapper.ui.cli import streamlit_argv  # noqa: PLC0415

    argv = streamlit_argv(["p.yaml", "--server.port", "8599", "--server.headless=true"])
    assert argv[:2] == ["streamlit", "run"]
    assert argv[2].endswith("app.py")
    assert argv[3:] == [
        "--server.port",
        "8599",
        "--server.headless=true",
        "--",
        "p.yaml",
    ]


def test_configuration_switch_updates_the_tabs():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=120).run()
    labels = [t.label for t in at.tabs]
    assert (
        labels[0] == "quadcopter"
    )  # the configuration tab carries the configuration name
    assert labels[1:] == [
        "Masses and battery",
        "Mission",
        "Hover",
        "Cruise",
        "Drag",
        "Power chain",
        "Propeller sizing",
        "Test data",
        "Results",
        "Exploration",
        "Optimisation",
        "Studies",
    ]
    assert any("does not use PredimRC" in i.value for i in at.info)
    at.selectbox(key="configuration").set_value("quadplane").run()
    assert not at.exception, at.exception
    assert at.session_state["app"].data["architecture"] == "quadplane"
    assert at.tabs[0].label == "quadplane_4p1"
    assert not any("does not use PredimRC" in i.value for i in at.info)
    at.selectbox(key="configuration").set_value("tricopter").run()
    assert len(at.session_state["app"].data["motors"]) == 3


def test_pitch_study_and_tables():
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.data import default_database  # noqa: PLC0415
    from predimrc_wrapper.sizing import motor_power_ranges  # noqa: PLC0415
    from predimrc_wrapper.ui import propulsion_charts as pc  # noqa: PLC0415

    project = Project.template("quadplane")
    aircraft = AircraftModel(project)
    unit, v0 = aircraft.units["cruise"], aircraft.battery.open_circuit_voltage
    import numpy as np  # noqa: PLC0415

    v = np.array([8.0, 14.0, 20.0])
    study = pc.pitch_study(
        unit, 8, [4.0, 6.0, 8.0], v, np.array([2.5, 2.0, 2.5]), aircraft.rho, v0
    )
    assert study["efficiency"].shape == (3, 3)
    best = study["best_pitch_in"]
    assert np.all(np.diff(best[np.isfinite(best)]) >= 0)  # higher speed, higher pitch
    assert pc.pitch_figure("cruise", 8, [4.0, 6.0, 8.0], v, study, 6.0, 14.0).data
    rows = pc.hover_pitch_rows(
        aircraft.units["lift"], 12, [3.0, 5.0, 10.0], 6.0, aircraft.rho, v0
    )
    powers = [r["shaft power (W)"] for r in rows]
    assert powers[1] < powers[0]
    assert powers[1] < powers[2]
    assert pc.thrust_figure(aircraft).data
    ranges = motor_power_ranges(project)
    assert len(pc.motor_rows(default_database(), ranges)) == len(
        default_database().records
    )
    assert pc.range_rows(ranges)[0]["unit type"] == "lift"
    assert pc.propeller_rows(aircraft)[1]["BEM CT0"] > 0


def test_optimisation_helpers():
    pytest.importorskip("gemseo")
    from predimrc_wrapper.mdo.optimise import OptimisationRun  # noqa: PLC0415
    from predimrc_wrapper.mdo.optimise import OptimisationSummary  # noqa: PLC0415
    from predimrc_wrapper.ui import optimisation as opt  # noqa: PLC0415

    rows = opt.default_variables(Project.template("quadplane"))
    paths = [r["path"] for r in rows]
    assert "battery.mass_g" in paths
    assert "propulsion_units.cruise.prop_diameter_in" in paths
    assert "aero.wing.length_mm.1" in paths
    params = opt.to_parameters(rows)
    assert [p.path for p in params] == [r["path"] for r in rows if r["use"]]
    with pytest.raises(ValueError, match="lower bound"):
        opt.to_parameters([
            {"use": True, "name": "x", "path": "battery.mass_g", "lower": 5, "upper": 5}
        ])
    runs = [
        OptimisationRun(
            {"battery.n_series": 4},
            {"battery_mass_g": 800.0},
            {"flight_time": 1200.0},
            True,
            [1000.0, 1200.0],
        ),
        OptimisationRun({"battery.n_series": 6}, {}, {}, False, error="boom"),
    ]
    summary = OptimisationSummary("flight_time", True, runs, 1.0)
    table = opt.run_rows(summary)
    assert table[0]["best"]
    assert table[0]["flight_time (min)"] == 20.0
    assert table[1]["error"] == "boom"
    assert len(opt.history_figure(summary).data) == 1
