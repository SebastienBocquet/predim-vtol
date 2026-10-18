"""Help on every quantity, MIC page, workflow views (INC2-009)."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from predimrc_wrapper.aircraft import AircraftModel  # noqa: E402
from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.api import evaluate  # noqa: E402
from predimrc_wrapper.api import evaluate_two_phase  # noqa: E402
from predimrc_wrapper.data import default_database  # noqa: E402
from predimrc_wrapper.sizing import motor_power_ranges  # noqa: E402
from predimrc_wrapper.ui import charts  # noqa: E402
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
        for pair, motors in hv.pairs(r).items():
            fig = hv.pair_figure(r, pair)
            labels.update({fig.layout.xaxis.title.text, fig.layout.yaxis.title.text})
            rows(hv.points_near_rows(motors[0]))
        summary, per_pair = hv.validation_rows()
        labels.update(summary), rows(per_pair)
        rows(tdv.compare_points(p, backend))
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
    at.radio(key="page").set_value("Model cards (MIC)").run()
    assert not at.exception, at.exception
    at.radio(key="page").set_value("Glossary").run()
    assert not at.exception
    assert at.dataframe
