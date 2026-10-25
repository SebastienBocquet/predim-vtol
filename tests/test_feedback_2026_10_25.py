"""Feedback of 2026-10-25: margins with the safety factor, templates, mass table edits, 4-in-1 ESC."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate_two_phase
from tests.conftest import ROOT

APP = ROOT / "src" / "predimrc_wrapper" / "ui" / "app.py"


def test_hover_margins_with_the_safety_factor():
    """Per motor, T/W min applied; the worst hover motor is the thrust-to-weight margin."""
    p = Project.template("tricopter").with_overrides({
        "test_data": [{"kind": "hover", "battery_power_w": 280.0}]
    })
    r = evaluate_two_phase(p)
    n = p.mission.min_thrust_to_weight
    download = AircraftModel(p).download_factor
    for m in r.hover.motors:
        assert m.safety_thrust_n == pytest.approx(n * m.thrust_n / download)
        if np.isfinite(m.test_max_thrust_n):
            assert m.safety_test_margin < m.thrust_margin
        assert m.safety_current_a > m.motor_current_a
        assert m.safety_current_margin < m.current_margin
    worst = min(m.safety_margin for m in r.hover.motors)
    assert worst == pytest.approx(r.margins["thrust_to_weight"], rel=1e-6)


def test_hover_rows_show_the_safety_columns():
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui import two_phase_view as tpv  # noqa: PLC0415

    p = Project.template("tricopter").with_overrides({
        "test_data": [{"kind": "hover", "battery_power_w": 280.0}]
    })
    row = tpv.hover_rows(evaluate_two_phase(p))[0]
    assert {
        "thrust with T/W min",
        "margin with T/W min (motor limits)",
        "margin with T/W min (test data)",
        "motor current with T/W min (A)",
        "current margin with T/W min",
    } <= set(row)


def test_editor_base_is_the_same_table_at_every_rerun():
    """The data editor gets back the table it was first given, not the edited rows."""
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui import forms  # noqa: PLC0415

    st = SimpleNamespace(session_state={})
    first = forms.editor_base(st, "3:mass_items", 3, lambda: ["initial"])
    again = forms.editor_base(st, "3:mass_items", 3, lambda: ["edited"])
    assert again is first
    forms.editor_base(st, "4:mass_items", 4, lambda: ["new project"])
    assert list(st.session_state["_editor_bases"]) == ["4:mass_items"]


def test_template_name_is_prefilled_and_save_project_is_named():
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=300).run()
    assert not at.exception, at.exception
    name = next(t for t in at.text_input if t.label == "Template name")
    assert name.value == at.session_state["app"].data["name"]
    labels = {b.label for b in at.button}
    assert "Save as new template" in labels or any(
        lb.startswith("Update template") for lb in labels
    )
    assert "Save project file" in labels


def _four_in_one(cruise_on_board: bool, efficiency: float = 0.95) -> Project:
    """Winged tricopter (3 lift motors) plus a pusher: 4 motors at most on the board."""
    data = Project.template("tiltrotor").model_dump()
    for m in data["motors"]:
        m["role"] = "lift"
    data["propulsion_units"]["cruise"] = dict(data["propulsion_units"]["rear"])
    data["motors"].append({"unit": "cruise", "role": "cruise", "x_mm": 900.0, "y_mm": 0.0})
    data["wiring"] = {
        "lift_esc": "four_in_one",
        "four_in_one_mass_g": 40.0,
        "cruise_on_four_in_one": cruise_on_board,
        "four_in_one_efficiency": efficiency,
    }
    return Project.model_validate(data)


def test_separate_esc_needs_its_mass():
    data = Project.template("tricopter").model_dump()
    for spec in data["propulsion_units"].values():
        spec["esc_mass_g"] = None
    with pytest.raises(ValueError, match="esc_mass_g"):
        Project.model_validate(data)
    data["wiring"] = {"lift_esc": "four_in_one", "four_in_one_mass_g": 20.0}
    Project.model_validate(data)  # every motor on the board: no ESC mass needed


def test_four_in_one_needs_its_board_mass():
    with pytest.raises(ValueError, match="four_in_one_mass_g"):
        Project.template("tricopter").with_overrides({
            "wiring": {"lift_esc": "four_in_one"}
        })


@pytest.mark.parametrize("cruise_on_board", [False, True])
def test_four_in_one_mass_replaces_the_board_escs(cruise_on_board):
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui.mass_view import mass_rows  # noqa: PLC0415

    board = _four_in_one(cruise_on_board)
    separate = board.with_overrides({"wiring": {"lift_esc": "separate"}})
    on_board = [m for m in board.motors if board.on_four_in_one(m)]
    removed = sum(board.propulsion_units[m.unit].esc_mass_g for m in on_board)
    from predimrc_wrapper.propulsion.wiring import wiring_mass_kg  # noqa: PLC0415

    delta = AircraftModel(board).total_mass_kg - AircraftModel(separate).total_mass_kg
    cables = wiring_mass_kg(board) - wiring_mass_kg(separate)  # no DC cable on the board
    assert delta == pytest.approx((40.0 - removed) / 1000.0 + cables)
    rows = mass_rows(AircraftModel(board))
    assert sum(r["mass (g)"] for r in rows) == pytest.approx(
        1000.0 * AircraftModel(board).total_mass_kg, abs=0.5
    )
    escs = [r for r in rows if r["component"] == "ESC"]
    assert sum(r["count"] for r in escs if "separate" in r["item"]) == (
        len(board.motors) - len(on_board)
    )
    assert any("4-in-1" in r["item"] for r in escs)


@pytest.mark.parametrize("cruise_on_board", [False, True])
def test_four_in_one_loss_bar(cruise_on_board):
    from predimrc_wrapper.mission.power_budget import power_budget  # noqa: PLC0415

    p = _four_in_one(cruise_on_board)
    budgets = power_budget(AircraftModel(p), evaluate_two_phase(p))
    for b in budgets:
        if "motors, ESC and cables" in b.sinks:
            continue
        assert b.sinks["4-in-1 ESC"] >= 0.0
        assert b.closure_w == pytest.approx(0.0, abs=1e-6)
    cruise = [b for b in budgets if b.phase.startswith("V")]
    if cruise_on_board:  # the cruise ESC loss goes to the board
        assert all("ESC" not in b.sinks for b in budgets)
        assert all(b.sinks["4-in-1 ESC"] > 0 for b in cruise)
    else:
        assert all(b.sinks["ESC"] > 0 for b in cruise)


def test_cruise_on_four_in_one_wiring_and_cost():
    from predimrc_wrapper.cost.model import cost  # noqa: PLC0415
    from predimrc_wrapper.propulsion.wiring import default_layout  # noqa: PLC0415

    p = _four_in_one(True)
    layout = default_layout(p)
    assert all(b.dc_length_mm == 0.0 for b in layout.branches)
    escs = [i for i in cost(AircraftModel(p), 1200.0).items if i.category == "ESCs"]
    assert [e.quantity for e in escs] == [1]  # the board alone


def test_mt2216_motors_propellers_and_tests_are_shipped():
    from predimrc_wrapper.data import default_database  # noqa: PLC0415
    from predimrc_wrapper.data import default_propellers  # noqa: PLC0415
    from predimrc_wrapper.data.tests import default_tests  # noqa: PLC0415

    for motor in ("tmotor-mt2216-1100kv", "tmotor-mt2216-900kv"):
        assert default_database().motor(motor).mass_kg == pytest.approx(0.075)
        assert default_tests().tests(motor_id=motor)
    for prop in ("8x2.7", "9x3", "10x3.3", "11x3.7", "12x4"):
        default_propellers().propeller(f"tmotor-{prop}cf")
    assert len(default_tests().tests(motor_id="tmotor-mt2216-1100kv")) == 7
    assert len(default_tests().tests(motor_id="tmotor-mt2216-900kv")) == 5


def test_motor_mass_of_the_unit_type_overrides_the_database():
    p = Project.template("tricopter")
    name = next(iter(p.propulsion_units))
    base = AircraftModel(p).units[name].motor.p.mass_kg
    heavier = p.with_overrides({f"propulsion_units.{name}.motor_mass_g": 1000 * base + 10})
    assert AircraftModel(heavier).units[name].motor.p.mass_kg == pytest.approx(base + 0.01)
    assert AircraftModel(heavier).total_mass_kg > AircraftModel(p).total_mass_kg
    # Another motor in a study: its database mass, not the entered one.
    other = heavier.with_overrides({f"propulsion_units.{name}.motor_id": "tmotor-mt2216-900kv"})
    assert other.propulsion_units[name].motor_mass_g is None
    assert AircraftModel(other).units[name].motor.p.mass_kg == pytest.approx(0.075)


def test_unit_type_form_prefills_the_motor_mass():
    text = APP.read_text(encoding="utf-8")
    assert '"motor_mass_g": round(1000 * db.motor(motor_before).mass_kg, 1)' in text


def test_four_in_one_channels():
    """A 4-in-1 board drives 4 motors at most: 4 lift motors and the pusher do not fit."""
    project = Project.template("quadplane")
    wiring = {"lift_esc": "four_in_one", "four_in_one_mass_g": 40.0}
    project.with_overrides({"wiring": wiring})  # the 4 lift motors fit
    with pytest.raises(ValueError, match="4 channels"):
        project.with_overrides({"wiring": {**wiring, "cruise_on_four_in_one": True}})


def test_four_in_one_efficiency():
    """The board channels use the board efficiency (constant-efficiency ESC model)."""
    p = _four_in_one(True, efficiency=0.90)
    assert all(p.esc_efficiency(m) == 0.90 for m in p.motors)
    aircraft = AircraftModel(p)
    assert all(aircraft.unit_of(m).p.esc_efficiency == 0.90 for m in p.motors)
    hover = evaluate_two_phase(p).hover.chain
    boards = [s for s in hover.segments if s.name.endswith(": 4-in-1 ESC")]
    assert len(boards) == len(p.motors)
    assert all(s.loss_w == pytest.approx(0.10 * s.power_in_w) for s in boards)
    separate = _four_in_one(False, efficiency=0.90)
    pusher = next(m for m in separate.motors if m.role == "cruise")
    assert separate.esc_efficiency(pusher) == separate.propulsion_units["cruise"].esc_efficiency


def test_hover_calibration_out_of_the_model_range_is_a_clear_error():
    """A mass in g typed as kg: the hover power is NaN, the error names the mass."""
    p = Project.template("tricopter").with_overrides({
        "calibration": {"hover": {"battery_power_w": 280.0, "mass_kg": 1870.0}}
    })
    with pytest.raises(ValueError, match=r"1870 kg.*check the mass, in kg"):
        evaluate_two_phase(p)
