"""User settings kept outside the project files (INC2-005, INC2-008).

File ``~/.predimrc_wrapper/settings.yaml`` (or ``$PREDIMRC_SETTINGS``); environment
variables override it: ``$PREDIMRC_PROFILES`` (PredimRC folder), ``$PREDIMRC_STUDIES``
(studies root), ``$PREDIMRC_USER_DATA`` (user data folder), ``$PREDIMRC_TEMPLATES`` (user
templates folder), ``$PREDIMRC_CACHE`` (cache file of the PredimRC evaluations).
"""

from __future__ import annotations

import os
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

import yaml


def settings_path() -> Path:
    return Path(
        os.environ.get(
            "PREDIMRC_SETTINGS", Path.home() / ".predimrc_wrapper" / "settings.yaml"
        )
    )


@dataclass
class Settings:
    """Folders used by the tool."""

    predimrc_folder: str = "profiles"
    """Folder of the PredimRC workbooks ``PredimRC_<profile>.xls``."""
    studies_root: str = "."
    """Root folder of the stored studies (default: current working directory)."""
    templates_folder: str = ""
    """Folder of the user templates (default ``~/.predimrc_wrapper/templates``)."""
    predimrc_cache: str = ""
    """HDF5 cache of the PredimRC evaluations (default ``~/.predimrc_wrapper/predimrc_cache.h5``)."""

    @classmethod
    def load(cls) -> Settings:
        path = settings_path()
        data = (
            yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
        )
        known = {k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__}
        settings = cls(**known)
        if "PREDIMRC_PROFILES" in os.environ:
            settings.predimrc_folder = os.environ["PREDIMRC_PROFILES"]
        if "PREDIMRC_STUDIES" in os.environ:
            settings.studies_root = os.environ["PREDIMRC_STUDIES"]
        if "PREDIMRC_TEMPLATES" in os.environ:
            settings.templates_folder = os.environ["PREDIMRC_TEMPLATES"]
        if "PREDIMRC_CACHE" in os.environ:
            settings.predimrc_cache = os.environ["PREDIMRC_CACHE"]
        return settings

    def save(self) -> Path:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(asdict(self), sort_keys=False), encoding="utf-8")
        return path


def predimrc_folder() -> Path:
    """The PredimRC folder of the settings."""
    return Path(Settings.load().predimrc_folder)


def available_profiles() -> list[str]:
    """Profiles found in the PredimRC folder."""
    from predimrc_wrapper.predimrc_wrapper import discover_profiles  # noqa: PLC0415

    return sorted(discover_profiles(predimrc_folder()))


def templates_folder() -> Path:
    """Folder of the user templates of the settings."""
    folder = Settings.load().templates_folder
    return Path(folder) if folder else Path.home() / ".predimrc_wrapper" / "templates"
