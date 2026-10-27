"""Help on every quantity, MIC page, workflow views (INC2-009)."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from predimrc_wrapper.aircraft import AircraftModel  # noqa: E402
from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.api import evaluate  # noqa: E402
from predimrc_wrapper.api import evaluate_two_phase  # noqa: E402
from predimrc_wrapper.cost import cost  # noqa: E402
from predimrc_wrapper.data import default_database  # noqa: E402
from predimrc_wrapper.mission.power_budget import budget_rows  # noqa: E402
from predimrc_wrapper.mission.power_budget import power_budget  # noqa: E402
from predimrc_wrapper.reliability import motor_out  # noqa: E402
from predimrc_wrapper.sizing import motor_power_ranges  # noqa: E402
from predimrc_wrapper.ui import charts  # noqa: E402
from predimrc_wrapper.ui import cost_view as cov  # noqa: E402
from predimrc_wrapper.ui import drag_view as dv  # noqa: E402
from predimrc_wrapper.ui import hover_view as hv  # noqa: E402
from predimrc_wrapper.ui import mic_page  # noqa: E402
from predimrc_wrapper.ui import prop_sizing as ps  # noqa: E402
from predimrc_wrapper.ui import propulsion_charts as pc  # noqa: E402
from predimrc_wrapper.ui import test_data_view as tdv  # noqa: E402
from predimrc_wrapper.ui import two_phase_view as tpv  # noqa: E402
from predimrc_wrapper.ui.help import HelpRegistry  # noqa: E402
from predimrc_wrapper.ui.help import model_entries  # noqa: E402
from predimrc_wrapper.ui.help import schema_entries  # noqa: E402
from tests.conftest import ROOT  # noqa: E402
from tests.conftest import requires_excel  # noqa: E402
from tests.helpers import ParabolicAero  # noqa: E402

APP = ROOT / "src" / "predimrc_wrapper" / "ui" / "app.py"


def _displayed_labels() -> set[str]:
    labels: set[str] = set()

    def rows(rs):
        for r in rs:
            labels.update(r)

    for name in ("tricopter", "quadplane", "tiltrotor"):
        p = Project.template(name).with_overrides({
            "test_data": [{"kind": "hover", "battery_power_w": 280.0}]
        })
        backend = ParabolicAero() if p.architecture == "quadplane" else None
        r = evaluate_two_phase(p, backend=backend)
        for row in tpv.kpi_rows(r):
            labels.update(x[0] for x in row)
        rows(tpv.hover_rows(r)), rows(tpv.cruise_rows(r)), rows(tpv.chain_rows(r))
        tilting = {i for i, m in enumerate(p.motors) if m.role == "tilt"}
        rows(tpv.hover_tilt_rows(r, tilting, p.mission.transition_tilt_deg))
        for pair, motors in hv.pairs(r).items():
            fig = hv.pair_figure(r, pair)
            labels.update({fig.layout.xaxis.title.text, fig.layout.yaxis.title.text})
            rows(hv.points_near_rows(motors[0]))
        summary, per_pair = hv.validation_rows()
        labels.update(summary), rows(per_pair)
        rows(tdv.compare_points(p, backend))
        rows(tdv.calibration_rows(r.metadata.get("calibration") or []))
        rows(budget_rows(power_budget(AircraftModel(p, aero_backend=backend), r)))
        c_res = cost(AircraftModel(p), r.cruise[0].flight_time_s)
        rel = motor_out(AircraftModel(p))
        rows(cov.purchase_rows(c_res)), rows(cov.use_rows(c_res))
        rows(cov.reliability_rows(rel, p))
        labels.update({
            "Purchase cost",
            "Cost per flight hour",
            "Motor-out T/W (worst)",
        })
        rows(
            dv.boom_rows(
                p.with_overrides({"booms": {"layout": "diagonal"}}),
                r,
            )
        )
        aircraft = AircraftModel(p, aero_backend=backend)
        for unit in p.propulsion_units:
            table, rec = ps.cruise_pitch_rows(aircraft, r, unit)
            rows(table), labels.update(rec)
        (
            rows(pc.range_rows(motor_power_ranges(p))),
            rows(pc.motor_rows(default_database(), motor_power_ranges(p))),
        )
        result = evaluate(p, backend=backend)
        (
            labels.update(k.label for k in charts.kpis(result)),
            rows(charts.segment_rows(result)),
        )
    return labels


def test_every_quantity_has_a_help_entry():
    registry = HelpRegistry.default()
    assert not [k for k, e in schema_entries(Project).items() if not e.definition], (
        "project fields without description"
    )
    assert not [k for k, e in model_entries().items() if not e.definition], (
        "model ports / parameters without description"
    )
    missing = registry.missing(sorted(_displayed_labels()))
    assert not missing, f"displayed quantities without a glossary entry: {missing}"


def test_tooltip_content():
    registry = HelpRegistry.default()
    text = registry.tooltip("propulsion_units.front.prop_diameter_in")
    assert "Propeller diameter" in text
    assert "Unit: in" in text
    assert "MIC-PROP-UNIT" in text
    assert registry.entry("motors.2.x_mm") is not None
    assert "MIC-PROP-BEM" in registry.tooltip("MIC-PROP-BEM.cd_stall")
    assert registry.search("thrust")


def test_mic_cards_listed():
    cards = mic_page.cards()
    ids = {c["id"] for c in cards}
    assert {
        "MIC-PROP-SUR",
        "MIC-PROP-CHAIN",
        "MIC-MIS-TWO",
        "MIC-CFG-SIZ",
        "MIC-CAL-REF",
    } <= ids
    assert "Interface" in mic_page.render_text("MIC-MIS-TWO")


def test_pages_and_run():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.selectbox(key="configuration").set_value("tricopter").run()
    next(b for b in at.button if b.label == "Run").click().run()
    assert not at.exception, at.exception
    assert at.session_state["app"].two_phase.hover.front_rear_ratio == pytest.approx(
        2.0
    )
    labels = {m.label for m in at.metric}
    assert {"Flight time", "Hover power (battery)", "Margin motor power"} <= labels
    assert {"Purchase cost", "Cost per flight hour", "Motor-out T/W (worst)"} <= labels
    assert any("Purchase cost:" in h.value for h in at.subheader)
    assert any("one motor stopped" in h.value for h in at.subheader)
    assert any("Where the battery power goes" in h.value for h in at.subheader), (
        "power budget in Results"
    )
    at.radio(key="page").set_value("Studies").run()
    assert not at.exception, at.exception
    assert [t.label for t in at.tabs] == ["Exploration", "Optimisation", "Studies"]
    at.radio(key="page").set_value("Model cards (MIC)").run()
    assert not at.exception, at.exception
    at.radio(key="page").set_value("Glossary").run()
    assert not at.exception
    assert at.dataframe


def test_save_run_and_runs_page(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    monkeypatch.setenv("PREDIMRC_STUDIES", str(tmp_path))
    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.selectbox(key="configuration").set_value("tricopter").run()
    next(b for b in at.button if b.label == "Run").click().run()
    next(b for b in at.button if b.label == "Save run").click().run()
    assert not at.exception, at.exception
    assert len(list((tmp_path / "runs").iterdir())) == 1
    assert next(b for b in at.button if b.label == "Save run").disabled
    at.radio(key="page").set_value("Runs").run()
    assert not at.exception, at.exception
    assert any("1 / 1 runs" in m.value for m in at.markdown)
    at.radio(key="runs.mode").set_value("Families along an input").run()
    assert not at.exception, at.exception
    assert any("No input varies" in i.value for i in at.info)


def test_power_chain_after_motors_removed():
    """Regression (2026-10-17): IndexError in the Power chain tab once a Run result is outdated."""
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.selectbox(key="configuration").set_value("multicopter").run()
    next(b for b in at.button if b.label == "Run").click().run()
    app = at.session_state["app"]
    app.data["motors"] = app.data["motors"][:3]
    app.data.setdefault("wiring", {}).update(
        lift_esc="four_in_one", four_in_one_mass_g=15.0
    )
    app.generation += 1
    at.run()
    assert not at.exception, at.exception


def test_mission_speeds_in_kmh():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    next(
        c for c in at.checkbox if c.key.endswith("mission.speeds_auto")
    ).uncheck().run()
    v1 = next(n for n in at.number_input if n.key.endswith("mission.v1"))
    assert v1.label == "V1 (km/h)"
    v1.set_value(54.0).run()
    assert not at.exception, at.exception
    speeds = at.session_state["app"].data["mission"]["target_speeds_m_s"]
    assert speeds[0] == pytest.approx(15.0)


def test_positions_figure_dimensions():
    from predimrc_wrapper.ui.positions_view import overlapping  # noqa: PLC0415
    from predimrc_wrapper.ui.positions_view import positions_figure  # noqa: PLC0415

    data = Project.template("quadplane").to_dict()
    fig = positions_figure(data["motors"], data["propulsion_units"], True)
    texts = [a.text for a in fig.layout.annotations]
    n_x = sum(1 for m in data["motors"] if abs(m["x_mm"]) > 0.5)
    n_y = sum(1 for m in data["motors"] if abs(m["y_mm"]) > 0.5)
    assert sum(t.startswith("x = ") for t in texts) == n_x
    assert sum(t.startswith("y = ") for t in texts) == n_y
    assert any("wing root leading edge" in (t.name or "") for t in fig.data)
    data["motors"][1]["x_mm"] = -100.0  # motor 2 onto motor 1
    assert overlapping(data["motors"], data["propulsion_units"]) == {0, 1}


def test_tilt_mask_quick_choice_updates_the_roles():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.selectbox(key="configuration").set_value("tiltrotor").run()
    next(s for s in at.selectbox if "tiltquick" in str(s.key)).set_value("rear").run()
    assert not at.exception, at.exception
    roles = [m["role"] for m in at.session_state["app"].data["motors"]]
    assert roles == ["lift", "lift", "tilt"]
    mask = next(m for m in at.multiselect if "tiltmask" in str(m.key))
    assert mask.value == [3]


def test_first_tab_mission_and_battery_after_feedback_2026_10_19():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    at.selectbox(key="configuration").set_value("quadplane").run()
    assert not at.exception, at.exception
    labels = [e.label for e in at.expander]
    assert not any("Generate the motor positions" in label for label in labels)
    wing = next(
        i for i, label in enumerate(labels) if label.startswith("Wing, stabiliser")
    )
    layout = next(
        i for i, label in enumerate(labels) if label.startswith("Motor layout")
    )
    booms = next(i for i, label in enumerate(labels) if label.startswith("Booms"))
    assert wing < layout < booms
    assert not any("Scenario mode" in label for label in labels)
    assert not any(b.label.startswith("Add scenario") for b in at.button)
    # Battery defined by its capacity: the mass field disappears.
    mode = next(s for s in at.selectbox if str(s.key).endswith("battery.mode"))
    mode.set_value("capacity").run()
    assert not at.exception, at.exception
    keys = [str(n.key) for n in at.number_input]
    assert any(k.endswith("battery.capacity_mah") for k in keys)
    assert not any(k.endswith("battery.mass_g") for k in keys)


@requires_excel
def test_hover_tilt_rows_add_the_tilting_motors_in_transition():
    """Results hover table: every lift motor in hover, then only the tilting ones tilted."""
    p = Project.template("tiltrotor").with_overrides({
        "test_data": [{"kind": "hover", "battery_power_w": 280.0}]
    })
    r = evaluate_two_phase(p)
    assert r.transition is not None
    tilting = {i for i, m in enumerate(p.motors) if m.role == "tilt"}
    rows = tpv.hover_tilt_rows(r, tilting, p.mission.transition_tilt_deg)
    hover = [row for row in rows if row["phase"] == "hover"]
    tilted = [row for row in rows if row["phase"] != "hover"]
    assert len(hover) == len(r.hover.motors)
    assert {row["motor"] - 1 for row in tilted} == tilting
    by_motor = {row["motor"]: row for row in hover}
    for row in tilted:
        assert row["power (W)"] > by_motor[row["motor"]]["power (W)"]


def test_custom_motor_added_and_chosen_for_a_unit_type(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    monkeypatch.setenv("PREDIMRC_USER_DATA", str(tmp_path))
    default_database.cache_clear()
    try:
        at = AppTest.from_file(str(APP), default_timeout=300).run()
        app = at.session_state["app"]
        unit = next(iter(app.data["propulsion_units"]))

        def widget(kind, name):
            return next(
                w
                for w in getattr(at, kind)
                if str(w.key).endswith(f"custom_motor.{name}")
            )

        widget("text_input", "id").set_value("custom-2216-880kv")
        widget("text_input", "manufacturer").set_value("Me")
        widget("text_input", "range").set_value("custom")
        widget("text_input", "source").set_value("own measurement")
        widget("selectbox", "use_for").set_value(unit)
        next(b for b in at.button if b.label == "Add the motor").click().run()
        assert not at.exception, at.exception
        assert "custom-2216-880kv" in default_database().records
        assert (tmp_path / "motors.yaml").is_file()
        data = at.session_state["app"].data
        assert data["propulsion_units"][unit]["motor_id"] == "custom-2216-880kv"
    finally:
        default_database.cache_clear()


def test_typed_test_rows_drop_empty_and_fill_power():
    import pandas as pd  # noqa: PLC0415

    nan = float("nan")
    frame = pd.DataFrame(
        [[50, nan, 2.0, nan, 300, nan], [nan] * 6, [100, 14.0, 8.0, 115.0, 800, nan]],
        columns=[
            "throttle_pct",
            "voltage_v",
            "current_a",
            "power_w",
            "thrust_g",
            "rpm",
        ],
    )
    columns, rows = hv.typed_test_rows(frame, 15.0)
    assert columns == ["throttle_pct", "voltage_v", "current_a", "power_w", "thrust_g"]
    assert rows == [[50.0, None, 2.0, 30.0, 300.0], [100.0, 14.0, 8.0, 115.0, 800.0]]


def test_propeller_and_test_forms_of_the_hover_tab(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    from predimrc_wrapper.data import default_propellers  # noqa: PLC0415
    from predimrc_wrapper.data import default_tests  # noqa: PLC0415

    monkeypatch.setenv("PREDIMRC_USER_DATA", str(tmp_path))
    caches = (default_database, default_propellers, default_tests)
    for c in caches:
        c.cache_clear()
    try:
        at = AppTest.from_file(str(APP), default_timeout=300).run()
        at.text_input(key="propeller_add.id").set_value("my-10x5")
        at.number_input(key="propeller_add.p").set_value(5.0)
        next(b for b in at.button if b.label == "Add the propeller").click().run()
        assert not at.exception, at.exception
        assert default_propellers().propeller("my-10x5").pitch_in == 5.0
        assert "my-10x5" in at.selectbox(key="test_add.propeller").options
        # The table is empty: the test is refused with a message, nothing is written.
        at.button(key="test_add.go").click().run()
        assert not at.exception, at.exception
        assert any("missing" in e.value for e in at.error)
        assert not (tmp_path / "thrust_tests").exists()
    finally:
        for c in caches:
            c.cache_clear()
