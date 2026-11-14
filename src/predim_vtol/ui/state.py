"""GUI state and the project logic behind the pages (no Streamlit import)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from predim_vtol.aircraft import Project
from predim_vtol.api import profiles_dir


@dataclass
class AppState:
    """What the GUI keeps between reruns.

    Attributes:
        data: The project as plain data, edited by the widgets.
        source_path: The file the project came from, if any.
        result_key: The ``project_key`` of the data evaluated for ``two_phase``.
        generation: Incremented when a new project is loaded, to reset the widgets.
    """

    data: dict[str, Any]
    source_path: Path | None = None
    two_phase: Any = None
    """Last two-phase flight time (``TwoPhaseResult``)."""
    result_key: str | None = None
    generation: int = 0

    def load(self, data: dict[str, Any], source_path: Path | None = None) -> None:
        self.data, self.source_path = data, source_path
        self.result_key = self.two_phase = None
        self.generation += 1

    @property
    def outdated(self) -> bool:
        return self.two_phase is not None and self.result_key != project_key(self.data)


@dataclass
class Check:
    """Validation of the edited data."""

    project: Project | None
    errors: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def load_template(architecture: str) -> dict[str, Any]:
    return Project.template(architecture).to_dict()


def load_file(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _path(loc: tuple) -> str:
    # Pydantic adds the validator / union member names to the location: keep the data keys.
    keys = [
        str(k)
        for k in loc
        if not (isinstance(k, str) and ("[" in k or k in ("float", "str", "int")))
    ]
    return ".".join(keys)


def check(data: dict[str, Any]) -> Check:
    """Validate the data; errors by dotted path, required fields left empty."""
    try:
        return Check(Project.model_validate(data))
    except ValidationError as error:
        errors: dict[str, str] = {}
        missing: list[str] = []
        for e in error.errors():
            path = _path(e["loc"])
            if e["type"] == "missing" or (
                e.get("input") is None and e["type"].endswith("_type")
            ):
                missing.append(path)
            errors.setdefault(path, e["msg"])
        return Check(None, errors, missing)


def run_enabled(result: Check) -> bool:
    return result.project is not None and not result.missing


def save_project(data: dict[str, Any], path: str | Path) -> Path:
    """Validate and save; the file reloads identically with ``Project.load``."""
    path = Path(path)
    Project.model_validate(data).save(path)
    return path


def project_key(data: dict[str, Any]) -> str:
    """Hash of the project data; empty top-level values (None, {}) do not count (the forms set
    them while a page is drawn, the page removes them at its end)."""
    kept = {k: v for k, v in data.items() if v is not None and v != {}}
    return hashlib.sha1(
        json.dumps(kept, sort_keys=True, default=str).encode()
    ).hexdigest()


def aero_status(aero: dict[str, Any] | None) -> tuple[str, str | None, bool]:
    """Aerodynamic backend of the project being edited.

    Returns:
        ``(backend, message, blocking)``: the backend that will run (``simple`` or
        ``predimrc``), the message to show (None when the requested backend runs) and
        whether the evaluation cannot run (airfoil unknown to the simple model).
    """
    from predim_vtol.aero import backend_status  # noqa: PLC0415
    from predim_vtol.aircraft.project import AeroSpec  # noqa: PLC0415

    aero = aero or {}
    spec = AeroSpec.model_construct(
        backend=aero.get("backend") or "simple", profile=aero.get("profile") or "SD7003"
    )
    from predim_vtol.aero.airfoils import airfoils  # noqa: PLC0415

    backend, message = backend_status(spec, profiles_dir())
    known = {name.casefold() for name in airfoils("wing")}
    blocking = backend == "simple" and spec.profile.casefold() not in known
    return backend, message, blocking


def rename_unit(data: dict[str, Any], old: str, new: str) -> None:
    """Rename a propulsion unit type, in place, and the motors using it.

    Raises:
        ValueError: The new name is empty or already used.
    """
    new = new.strip()
    units = data["propulsion_units"]
    if not new:
        msg = "The new name is empty."
        raise ValueError(msg)
    if new != old and new in units:
        msg = f"A propulsion unit type '{new}' exists already."
        raise ValueError(msg)
    data["propulsion_units"] = {
        (new if name == old else name): spec for name, spec in units.items()
    }
    for motor in data.get("motors") or []:
        if motor.get("unit") == old:
            motor["unit"] = new


def remove_unit(
    data: dict[str, Any], name: str, replacement: str | None = None
) -> None:
    """Remove a propulsion unit type, in place; its motors take the ``replacement`` type.

    Raises:
        ValueError: It is the last type, or motors use it and no other type replaces it.
    """
    units = data["propulsion_units"]
    if len(units) == 1:
        msg = "The last propulsion unit type cannot be removed."
        raise ValueError(msg)
    users = [m for m in data.get("motors") or [] if m.get("unit") == name]
    if users and (
        replacement is None or replacement == name or replacement not in units
    ):
        msg = f"{len(users)} motor(s) use '{name}': choose the type replacing it."
        raise ValueError(msg)
    for motor in users:
        motor["unit"] = replacement
    data["propulsion_units"] = {k: v for k, v in units.items() if k != name}
