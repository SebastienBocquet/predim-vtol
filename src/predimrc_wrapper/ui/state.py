"""GUI state and the project logic behind the pages (no Streamlit import)."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import yaml
from pydantic import ValidationError

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import profiles_dir
from predimrc_wrapper.mission.scenario import Scenario

if TYPE_CHECKING:
    from predimrc_wrapper.mission.solver import MissionResult


@dataclass
class AppState:
    """What the GUI keeps between reruns.

    Attributes:
        data: The project as plain data, edited by the widgets.
        source_path: The file the project came from, if any.
        result: The last evaluation.
        result_key: The ``project_key`` of the data evaluated for ``result``.
        generation: Incremented when a new project is loaded, to reset the widgets.
    """

    data: dict[str, Any]
    source_path: Path | None = None
    result: MissionResult | None = None
    two_phase: Any = None
    """Last two-phase flight time (``TwoPhaseResult``)."""
    result_key: str | None = None
    generation: int = 0

    def load(self, data: dict[str, Any], source_path: Path | None = None) -> None:
        self.data, self.source_path = data, source_path
        self.result = self.result_key = self.two_phase = None
        self.generation += 1

    @property
    def outdated(self) -> bool:
        return self.result is not None and self.result_key != project_key(self.data)


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


def hover_scenario(architecture: str, hover_s: float = 90.0) -> Scenario:
    """Starter scenario offered by "Add scenario"."""
    return Scenario.hover_time(hover_s, wing_borne=architecture == "quadplane")


def _path(loc: tuple) -> str:
    # Pydantic adds the validator / union member names to the location: keep the data keys.
    keys = [str(k) for k in loc if not (isinstance(k, str) and ("[" in k or k in ("float", "str", "int")))]
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
            if e["type"] == "missing" or (e.get("input") is None and e["type"].endswith("_type")):
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
    return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def excel_available(profile: str = "SD7003") -> str | None:
    """None when PredimRC can run, else the reason to show."""
    if sys.platform != "win32":
        return "PredimRC needs Windows and Excel: the quadplane cannot be evaluated here."
    try:
        import winreg  # noqa: PLC0415

        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application")
    except OSError:
        return "Excel is not installed: the quadplane cannot be evaluated."
    from predimrc_wrapper.predimrc_wrapper import workbook_path  # noqa: PLC0415

    try:
        workbook_path(profiles_dir(), profile)
    except FileNotFoundError as error:
        return f"{error} Set the PredimRC folder in the settings."
    return None
