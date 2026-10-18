"""Tests of the MVP motor database (MVP-003)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.data import DatabaseError
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import default_database


def test_shipped_database_complete():
    db = default_database()
    assert len(db.records) >= 5
    assert db.ids("lift")
    assert db.ids("cruise")
    for record in db.records.values():
        assert record.source.startswith("http")
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
