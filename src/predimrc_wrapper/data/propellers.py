"""Propeller database: loading and validation (REQ-DATA-002, REQ-DATA-003)."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path

import yaml

from predimrc_wrapper.data.database import DatabaseError
from predimrc_wrapper.data.user import user_data_dir

REQUIRED = (
    "id",
    "manufacturer",
    "name",
    "diameter_in",
    "pitch_in",
    "n_blades",
    "source",
    "retrieved",
    "status",
)


@dataclass(frozen=True)
class PropellerRecord:
    """A propeller of the database (user units of the file: inches, grams)."""

    id: str
    manufacturer: str
    name: str
    diameter_in: float
    pitch_in: float
    n_blades: int
    source: str
    retrieved: str
    status: str
    mass_g: float | None = None
    """Mass when published; never invented."""
    notes: str = ""


def _parse(raw: dict, origin: str) -> PropellerRecord:
    for key in REQUIRED:
        if raw.get(key) in (None, ""):
            msg = f"{origin}: {raw.get('id', '?')}: missing {key}"
            raise DatabaseError(msg)
    if raw["status"] not in ("verified", "estimated"):
        msg = f"{origin}: {raw['id']}: status must be verified or estimated"
        raise DatabaseError(msg)
    if not (float(raw["diameter_in"]) > 0 and float(raw["pitch_in"]) > 0):
        msg = f"{origin}: {raw['id']}: diameter and pitch must be positive"
        raise DatabaseError(msg)
    retrieved = raw["retrieved"]
    return PropellerRecord(
        id=raw["id"],
        manufacturer=raw["manufacturer"],
        name=raw["name"],
        diameter_in=float(raw["diameter_in"]),
        pitch_in=float(raw["pitch_in"]),
        n_blades=int(raw["n_blades"]),
        source=raw["source"],
        retrieved=retrieved.isoformat()
        if isinstance(retrieved, date)
        else str(retrieved),
        status=raw["status"],
        mass_g=None if raw.get("mass_g") is None else float(raw["mass_g"]),
        notes=raw.get("notes", ""),
    )


class PropellerDatabase:
    """The propellers available to the projects (shipped file merged with the user one)."""

    def __init__(self, records: dict[str, PropellerRecord]) -> None:
        self.records = records

    @classmethod
    def load(cls, paths: list[Path] | None = None) -> PropellerDatabase:
        """Load the shipped file then ``<user data>/propellers.yaml`` (or the given files, in order)."""
        texts = []
        if paths is None:
            texts.append((
                "propellers.yaml",
                files("predimrc_wrapper.data")
                .joinpath("propellers.yaml")
                .read_text(encoding="utf-8"),
            ))
            user = user_data_dir() / "propellers.yaml"
            if user.is_file():
                texts.append((str(user), user.read_text(encoding="utf-8")))
        else:
            texts = [(str(p), Path(p).read_text(encoding="utf-8")) for p in paths]
        records: dict[str, PropellerRecord] = {}
        for origin, text in texts:
            for raw in yaml.safe_load(text) or []:
                record = _parse(raw, origin)
                records[record.id] = record  # a later file overrides an earlier one
        return cls(records)

    def propeller(self, propeller_id: str) -> PropellerRecord:
        """Return a propeller by id.

        Raises:
            KeyError: With close matches when the id is unknown.
        """
        try:
            return self.records[propeller_id]
        except KeyError:
            close = difflib.get_close_matches(propeller_id, self.records, n=3)
            msg = f"Unknown propeller '{propeller_id}'. Did you mean {close}?"
            raise KeyError(msg) from None

    def ids(self, diameter_in: float | None = None) -> list[str]:
        """Sorted ids, optionally of one diameter."""
        return sorted(
            k
            for k, r in self.records.items()
            if diameter_in is None or abs(r.diameter_in - diameter_in) < 1e-9
        )


@cache
def default_propellers() -> PropellerDatabase:
    """The shipped and user propellers (cached)."""
    return PropellerDatabase.load()
