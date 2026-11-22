"""User settings kept outside the project files (INC2-005, INC2-008).

File ``settings.yaml`` of the tool folder (``$PREDIM_VTOL_HOME``, else ``~/.predim_vtol``)
or ``$PREDIM_VTOL_SETTINGS``; environment
variables override it: ``$PREDIMRC_PROFILES`` (PredimRC folder), ``$PREDIM_VTOL_STUDIES``
(studies root), ``$PREDIM_VTOL_USER_DATA`` (user data folder), ``$PREDIM_VTOL_TEMPLATES`` (user
templates folder), ``$PREDIMRC_CACHE`` (cache folder of the PredimRC evaluations).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

import yaml

LEGACY_HOME = ".predimrc_wrapper"
"""Folder of the tool before its renaming to predim-vtol (0.x)."""

LEGACY_SKIPPED = ("*.h5",)
"""Not copied from the legacy folder: the PredimRC cache, which a former version still
running may be writing; it is rebuilt."""


def home_dir() -> Path:
    """The tool folder: ``$PREDIM_VTOL_HOME``, else ``~/.predim_vtol``.

    When ``~/.predim_vtol`` does not exist yet, the folder of the former name
    ``~/.predimrc_wrapper`` is copied to it (settings, user data, templates), so that they
    are kept. The legacy folder is left as is: a former version may still be installed and
    running.
    """
    if "PREDIM_VTOL_HOME" in os.environ:
        return Path(os.environ["PREDIM_VTOL_HOME"])
    home = Path.home() / ".predim_vtol"
    legacy = Path.home() / LEGACY_HOME
    if not home.exists() and legacy.is_dir():
        try:
            shutil.copytree(
                legacy, home, ignore=shutil.ignore_patterns(*LEGACY_SKIPPED)
            )
        except OSError:  # A file being written: use the new folder from scratch.
            shutil.rmtree(home, ignore_errors=True)
    return home


def settings_path() -> Path:
    return Path(os.environ.get("PREDIM_VTOL_SETTINGS", home_dir() / "settings.yaml"))


@dataclass
class Settings:
    """Folders used by the tool."""

    predimrc_folder: str = "profiles"
    """Folder of the PredimRC workbooks ``PredimRC_<profile>.xls``."""
    studies_root: str = "."
    """Root folder of the stored studies (default: current working directory)."""
    templates_folder: str = ""
    """Folder of the user templates (default ``~/.predim_vtol/templates``)."""
    predimrc_cache: str = ""
    """Cache folder of the PredimRC evaluations (default ``~/.predim_vtol/predimrc_cache``)."""

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
        if "PREDIM_VTOL_STUDIES" in os.environ:
            settings.studies_root = os.environ["PREDIM_VTOL_STUDIES"]
        if "PREDIM_VTOL_TEMPLATES" in os.environ:
            settings.templates_folder = os.environ["PREDIM_VTOL_TEMPLATES"]
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


def templates_folder() -> Path:
    """Folder of the user templates of the settings."""
    folder = Settings.load().templates_folder
    return Path(folder) if folder else home_dir() / "templates"
