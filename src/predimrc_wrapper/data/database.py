"""MVP motor database: loading and validation (REQ-DATA-001, REQ-DATA-003)."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path

import yaml

REQUIRED = (
    "id", "manufacturer", "range", "role", "kv", "rm_mohm", "i0_a", "i_max_a",
    "p_max_w", "mass_g", "source", "retrieved", "status",
)


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
        return {"kv": self.kv, "r_m": self.r_m, "i0": self.i0, "i_max": self.i_max,
                "p_max": self.p_max, "mass_kg": self.mass_kg}


def _parse(raw: dict, origin: str) -> MotorRecord:
    for key in REQUIRED:
        if raw.get(key) in (None, ""):
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
        retrieved=retrieved.isoformat() if isinstance(retrieved, date) else str(retrieved),
        status=raw["status"],
        notes=raw.get("notes", ""),
    )


class MotorDatabase:
    """The motors available to the projects.

    Args:
        records: The motors, by id.
    """

    def __init__(self, records: dict[str, MotorRecord]) -> None:
        self.records = records

    @classmethod
    def load(cls, path: Path | None = None) -> MotorDatabase:
        """Load the shipped database, or another YAML file."""
        if path is None:
            text = files("predimrc_wrapper.data").joinpath("motors_mvp.yaml").read_text(
                encoding="utf-8"
            )
            origin = "motors_mvp.yaml"
        else:
            text = Path(path).read_text(encoding="utf-8")
            origin = str(path)
        records = {}
        for raw in yaml.safe_load(text) or []:
            record = _parse(raw, origin)
            if record.id in records:
                msg = f"{origin}: duplicate id {record.id}"
                raise DatabaseError(msg)
            records[record.id] = record
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
        return sorted(k for k, r in self.records.items() if role is None or r.role == role)


@cache
def default_database() -> MotorDatabase:
    """Return the shipped database (cached)."""
    return MotorDatabase.load()
