"""Tests of the MVP motor database (MVP-003)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.data import DatabaseError
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import add_user_motor
from predimrc_wrapper.data import default_database


def test_shipped_database_complete():
    db = default_database()
    assert len(db.records) >= 5
    assert db.ids("lift")
    assert db.ids("cruise")
    for record in db.records.values():
        # A web page, or a data sheet supplied by the user (data/README.md).
        assert (
            record.source.startswith("http") or "supplied by the user" in record.source
        )
        assert record.retrieved
        assert record.status in ("verified", "estimated")
        assert record.kv > 0
        assert record.r_m > 0
        assert record.mass_kg > 0


def test_unknown_motor_suggests():
    with pytest.raises(KeyError, match="Did you mean"):
        default_database().motor("tmotor-mn2212-92kv")


def test_entry_without_source_rejected(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(
        "- {id: x, manufacturer: a, range: b, role: lift, kv: 1, rm_mohm: 1, i0_a: 1,"
        " i_max_a: 1, p_max_w: 1, mass_g: 1, retrieved: 2026-01-01, status: verified}\n",
        encoding="utf-8",
    )
    with pytest.raises(DatabaseError, match="missing source"):
        MotorDatabase.load(path)


CUSTOM = {
    "id": "custom-2216-880kv",
    "manufacturer": "Me",
    "range": "custom",
    "role": "lift",
    "kv": 880,
    "rm_mohm": 90,
    "i0_a": 0.4,
    "i_max_a": 20,
    "p_max_w": 240,
    "mass_g": 70,
    "source": "own measurement",
    "retrieved": "2026-10-25",
    "status": "estimated",
}


@pytest.fixture
def user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDIMRC_USER_DATA", str(tmp_path))
    default_database.cache_clear()
    yield tmp_path
    default_database.cache_clear()


def test_user_motor_added_and_merged(user_data):
    record = add_user_motor(CUSTOM)
    assert record.r_m == pytest.approx(0.09)
    assert (user_data / "motors.yaml").is_file()
    db = default_database()
    assert db.motor("custom-2216-880kv").mass_kg == pytest.approx(0.07)
    assert "custom-2216-880kv" in db.ids("lift")
    assert "tmotor-mn2212-780kv" in db.records


def test_user_motor_duplicate_or_incomplete_rejected(user_data):
    add_user_motor(CUSTOM)
    with pytest.raises(DatabaseError, match="already exists"):
        add_user_motor(CUSTOM)
    with pytest.raises(DatabaseError, match="already exists"):
        add_user_motor({**CUSTOM, "id": "tmotor-mn2212-780kv"})
    with pytest.raises(DatabaseError, match="missing kv"):
        add_user_motor({**CUSTOM, "id": "other", "kv": None})


def test_user_motor_provenance_optional(user_data):
    computed = ("id", "role", "kv", "rm_mohm", "i0_a", "i_max_a", "p_max_w", "mass_g")
    record = add_user_motor({k: CUSTOM[k] for k in computed})
    assert (record.source, record.status) == ("user entry", "estimated")
    assert default_database().motor(CUSTOM["id"]).kv == 880
