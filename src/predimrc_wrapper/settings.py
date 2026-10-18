"""User settings kept outside the project files (INC2-005, INC2-008).

File ``~/.predimrc_wrapper/settings.yaml`` (or ``$PREDIMRC_SETTINGS``); environment
variables override it: ``$PREDIMRC_PROFILES`` (PredimRC folder), ``$PREDIMRC_STUDIES``
(studies root), ``$PREDIMRC_USER_DATA`` (user data folder).
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
