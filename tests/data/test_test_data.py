"""Propeller database, thrust–power tests and flight points (INC2-002)."""

from __future__ import annotations

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.data import DatabaseError
from predimrc_wrapper.data import PropellerDatabase
from predimrc_wrapper.data import TestDatabase
from predimrc_wrapper.data import default_database
from predimrc_wrapper.data import default_propellers
from predimrc_wrapper.data import default_tests
from predimrc_wrapper.data.importers import import_csv
from predimrc_wrapper.data.importers import write_user_test
from predimrc_wrapper.data.tests import parse_test

HEADER = {"id": "my-test", "motor_id": "tmotor-mn2806-650kv", "propeller_id": "tmotor-p12x4", "voltage_v": 15.0,
          "bench": "home", "source": "my bench", "retrieved": "2026-10-14", "status": "verified"}


def test_shipped_tests_are_consistent():
    tests, motors, props = default_tests(), default_database(), default_propellers()
    assert len(tests.pairs()) == 8 and not tests.warnings
    for t in tests.records.values():
        motors.motor(t.motor_id)
        props.propeller(t.propeller_id)
        assert t.source.startswith("http") and t.measured_at == "motor_input" and t.esc is None
        assert np.all(np.diff(t.thrust_n) > 0)
        # Power column equals voltage × current within the rounding of the tables.
        assert np.allclose(t.power_w, t.voltage * t.current_a, rtol=0.02)


def test_grams_converted_to_newtons():
    t = default_tests().records["tmotor-mn2806-650kv__tmotor-p12x4__15.3v"]
    assert t.thrust_n[0] == pytest.approx(237 * 9.81 / 1000)
    assert t.throttle[0] == pytest.approx(0.40)


def test_measured_at_follows_the_esc():
    raw = {**HEADER, "columns": ["thrust_g", "current_a", "power_w"], "rows": [[100, 1.0, 15.0]]}
    assert parse_test(raw, "x").measured_at == "motor_input"
    assert parse_test({**raw, "esc": "AIR 20A"}, "x").measured_at == "esc_input"
    with pytest.raises(DatabaseError, match="measured_at"):
        parse_test({**raw, "measured_at": "battery"}, "x")


def test_missing_provenance_or_column_rejected():
    raw = {**HEADER, "columns": ["thrust_g", "current_a", "power_w"], "rows": [[100, 1.0, 15.0]]}
    with pytest.raises(DatabaseError, match="missing source"):
        parse_test({**raw, "source": ""}, "x")
    with pytest.raises(DatabaseError, match="missing"):
        parse_test({**raw, "columns": ["thrust_g", "power_w"], "rows": [[100, 15.0]]}, "x")
    with pytest.raises(DatabaseError, match="positive"):
        parse_test({**raw, "rows": [[0, 1.0, 15.0]]}, "x")


def test_csv_import_round_trip_and_override(tmp_path):
    csv = tmp_path / "bench.csv"
    csv.write_text("throttle,thrust_n,current_a,power_w,rpm\n50,3.0,2.0,30.0,4000\n100,9.0,9.0,135.0,6500\n",
                   encoding="utf-8")
    test, raw = import_csv(csv, {**HEADER, "id": "tmotor-mn2806-650kv__tmotor-p12x4__15.3v"})
    assert test.thrust_n.tolist() == pytest.approx([3.0, 9.0], rel=1e-3)
    folder = tmp_path / "user"
    path = write_user_test(raw, folder)
    shipped = default_tests()
    merged = TestDatabase.load([path.parent])
    assert merged.records[test.id].bench == "home"
    reloaded = parse_test(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))
    assert reloaded.power_w.tolist() == test.power_w.tolist()
    assert merged.hash() != shipped.hash()


def test_propeller_database_and_project_reference(tmp_path):
    assert default_propellers().ids(12.0) == ["tmotor-p12x4"]
    assert default_propellers().propeller("apc-8x6").mass_g is None
    extra = tmp_path / "p.yaml"
    extra.write_text(yaml.safe_dump([{"id": "x", "manufacturer": "m", "name": "x", "diameter_in": 5, "pitch_in": 0,
                                      "n_blades": 2, "source": "s", "retrieved": "2026", "status": "verified"}]))
    with pytest.raises(DatabaseError, match="positive"):
        PropellerDatabase.load([extra])
    p = Project.template("tricopter").with_overrides({"propulsion_units.front.propeller_id": "tmotor-p12x4",
                                                       "propulsion_units.front.prop_pitch_in": None})
    assert p.propulsion_units["front"].prop_pitch_in == 4.0
    with pytest.raises(ValidationError, match="diameter"):
        Project.template("tricopter").with_overrides({"propulsion_units.rear.propeller_id": "tmotor-p12x4"})


def test_flight_points_saved_with_the_project(tmp_path):
    p = Project.template("tricopter").with_overrides({"test_data": [
        {"kind": "hover", "battery_power_w": 280.0, "mass_kg": 1.87, "date": "2026-10-01"},
        {"kind": "cruise", "battery_power_w": 120.0, "speed_m_s": 14.0}]})
    p.save(tmp_path / "p.yaml")
    assert Project.load(tmp_path / "p.yaml").test_data == p.test_data
    with pytest.raises(ValidationError, match="speed_m_s"):
        Project.template("tricopter").with_overrides({"test_data": [{"kind": "cruise", "battery_power_w": 1.0}]})
