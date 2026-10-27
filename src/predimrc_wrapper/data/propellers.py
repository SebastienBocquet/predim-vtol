"""Propeller database: loading and validation (REQ-DATA-002, REQ-DATA-003)."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

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

USER_FILE = "propellers.yaml"
"""File of the user propellers in the user data folder."""

USER_DEFAULTS = {
    "manufacturer": "",
    "source": "user entry",
    "retrieved": "",
    "status": "estimated",
}
"""Values of the fields a user propeller may leave out (the name defaults to the id)."""


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


def _parse(raw: dict, origin: str, user: bool = False) -> PropellerRecord:
    if user:
        raw = {
            **USER_DEFAULTS,
            "name": raw.get("id"),
            **{k: v for k, v in raw.items() if v not in (None, "")},
        }
    for key in REQUIRED:
        if raw.get(key) in (None, "") and not (user and key in USER_DEFAULTS):
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
        texts = []  # (origin, text, user file)
        if paths is None:
            texts.append((
                "propellers.yaml",
                files("predimrc_wrapper.data")
                .joinpath("propellers.yaml")
                .read_text(encoding="utf-8"),
                False,
            ))
            user = user_data_dir() / USER_FILE
            if user.is_file():
                texts.append((str(user), user.read_text(encoding="utf-8"), True))
        else:
            texts = [
                (str(p), Path(p).read_text(encoding="utf-8"), False) for p in paths
            ]
        records: dict[str, PropellerRecord] = {}
        for origin, text, is_user in texts:
            for raw in yaml.safe_load(text) or []:
                record = _parse(raw, origin, user=is_user)
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


def add_user_propeller(
    raw: dict[str, Any], path: Path | None = None
) -> PropellerRecord:
    """Append a propeller to the user file (``<user data>/propellers.yaml`` by default).

    Args:
        raw: The propeller in the units of the YAML files (inches); the fields of
            ``USER_DEFAULTS`` and the name may be left out.
        path: The user file.

    Raises:
        DatabaseError: When the propeller is incomplete or its id already exists.
    """
    target = Path(path) if path is not None else user_data_dir() / USER_FILE
    raw = {k: v for k, v in raw.items() if v not in (None, "")}
    record = _parse(raw, "new propeller", user=True)
    existing = (
        yaml.safe_load(target.read_text(encoding="utf-8")) or []
        if target.is_file()
        else []
    )
    if record.id in default_propellers().records or any(
        p.get("id") == record.id for p in existing
    ):
        msg = f"The propeller id '{record.id}' already exists"
        raise DatabaseError(msg)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump([*existing, raw], sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    default_propellers.cache_clear()
    return record
