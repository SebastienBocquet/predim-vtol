"""Motor database: loading and validation (REQ-DATA-001, REQ-DATA-003).

The shipped motors are merged with the user ones of ``<user data>/motors.yaml``.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from predimrc_wrapper.data.user import user_data_dir

USER_FILE = "motors.yaml"
"""File of the user motors in the user data folder."""

REQUIRED = (
    "id",
    "manufacturer",
    "range",
    "role",
    "kv",
    "rm_mohm",
    "i0_a",
    "i_max_a",
    "p_max_w",
    "mass_g",
    "source",
    "retrieved",
    "status",
)

USER_DEFAULTS = {
    "manufacturer": "",
    "range": "",
    "source": "user entry",
    "retrieved": "",
    "status": "estimated",
}
"""Values of the fields a user motor may leave out: no computation uses them."""


class DatabaseError(ValueError):
    """An invalid or incomplete database entry."""


@dataclass(frozen=True)
class MotorRecord:
    """A motor of the database, converted to SI units."""

    id: str
    manufacturer: str
    range: str
    role: str
    """``lift`` or ``cruise``."""
    kv: float
    """Speed constant (rpm/V)."""
    r_m: float
    """Winding resistance (Ω)."""
    i0: float
    """No-load current (A)."""
    i_max: float
    """Maximum current (A)."""
    p_max: float
    """Maximum power (W)."""
    mass_kg: float
    """Mass (kg)."""
    source: str
    retrieved: str
    status: str
    notes: str = ""

    def model_parameters(self) -> dict[str, float]:
        """Return the parameter values of ``MotorModel``."""
        return {
            "kv": self.kv,
            "r_m": self.r_m,
            "i0": self.i0,
            "i_max": self.i_max,
            "p_max": self.p_max,
            "mass_kg": self.mass_kg,
        }


def _parse(raw: dict, origin: str, user: bool = False) -> MotorRecord:
    if user:
        raw = {**USER_DEFAULTS, **{k: v for k, v in raw.items() if v not in (None, "")}}
    for key in REQUIRED:
        if raw.get(key) in (None, "") and not (user and key in USER_DEFAULTS):
            msg = f"{origin}: {raw.get('id', '?')}: missing {key}"
            raise DatabaseError(msg)
    if raw["status"] not in ("verified", "estimated"):
        msg = f"{origin}: {raw['id']}: status must be verified or estimated"
        raise DatabaseError(msg)
    retrieved = raw["retrieved"]
    return MotorRecord(
        id=raw["id"],
        manufacturer=raw["manufacturer"],
        range=raw["range"],
        role=raw["role"],
        kv=float(raw["kv"]),
        r_m=float(raw["rm_mohm"]) / 1000.0,
        i0=float(raw["i0_a"]),
        i_max=float(raw["i_max_a"]),
        p_max=float(raw["p_max_w"]),
        mass_kg=float(raw["mass_g"]) / 1000.0,
        source=raw["source"],
        retrieved=retrieved.isoformat()
        if isinstance(retrieved, date)
        else str(retrieved),
        status=raw["status"],
        notes=raw.get("notes", ""),
    )


class MotorDatabase:
    """The motors available to the projects (shipped file merged with the user one).

    Args:
        records: The motors, by id.
    """

    def __init__(self, records: dict[str, MotorRecord]) -> None:
        self.records = records

    @classmethod
    def load(cls, path: Path | None = None) -> MotorDatabase:
        """Load the shipped file then ``<user data>/motors.yaml``, or another YAML file."""
        texts = []  # (origin, text, user file)
        if path is None:
            texts.append((
                "motors_mvp.yaml",
                files("predimrc_wrapper.data")
                .joinpath("motors_mvp.yaml")
                .read_text(encoding="utf-8"),
                False,
            ))
            user = user_data_dir() / USER_FILE
            if user.is_file():
                texts.append((str(user), user.read_text(encoding="utf-8"), True))
        else:
            texts.append((str(path), Path(path).read_text(encoding="utf-8"), False))
        records: dict[str, MotorRecord] = {}
        for origin, text, is_user in texts:
            seen = set()
            for raw in yaml.safe_load(text) or []:
                record = _parse(raw, origin, user=is_user)
                if record.id in seen:
                    msg = f"{origin}: duplicate id {record.id}"
                    raise DatabaseError(msg)
                seen.add(record.id)
                records[record.id] = record  # a user motor overrides a shipped one
        return cls(records)

    def motor(self, motor_id: str) -> MotorRecord:
        """Return a motor by id.

        Raises:
            KeyError: With close matches when the id is unknown.
        """
        try:
            return self.records[motor_id]
        except KeyError:
            close = difflib.get_close_matches(motor_id, self.records, n=3)
            msg = f"Unknown motor '{motor_id}'. Did you mean {close}?"
            raise KeyError(msg) from None

    def ids(self, role: str | None = None) -> list[str]:
        """Return the sorted motor ids, optionally of one role."""
        return sorted(
            k for k, r in self.records.items() if role is None or r.role == role
        )


@cache
def default_database() -> MotorDatabase:
    """Return the shipped and user motors (cached)."""
    return MotorDatabase.load()


def add_user_motor(raw: dict[str, Any], path: Path | None = None) -> MotorRecord:
    """Append a motor to the user file (``<user data>/motors.yaml`` by default).

    Args:
        raw: The motor in the units of the YAML files (``rm_mohm``, ``mass_g``...); the
            fields of ``USER_DEFAULTS`` may be left out.
        path: The user file.

    Raises:
        DatabaseError: When the motor is incomplete or its id already exists.
    """
    target = Path(path) if path is not None else user_data_dir() / USER_FILE
    raw = {k: v for k, v in raw.items() if v not in (None, "")}
    record = _parse(raw, "new motor", user=True)
    existing = (
        yaml.safe_load(target.read_text(encoding="utf-8")) or []
        if target.is_file()
        else []
    )
    if record.id in default_database().records or any(
        m.get("id") == record.id for m in existing
    ):
        msg = f"The motor id '{record.id}' already exists"
        raise DatabaseError(msg)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump([*existing, raw], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    default_database.cache_clear()
    return record
