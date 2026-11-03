"""Shipped and user templates (REQ-CFG-013).

A template is a complete project file: geometry, propulsion unit types, motors with their
positions and roles (tilt mask), booms, battery, masses, drag sources, wiring, mission,
sizing and test data. The shipped templates come with the tool; the user ones are
saved from the GUI in the templates folder of the settings and named ``user:<file stem>``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any

import yaml

from predimrc_wrapper.settings import templates_folder

if TYPE_CHECKING:
    from pathlib import Path

USER = "user:"


def _slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip()).strip("_.")
    if not slug:
        msg = f"Invalid template name {name!r}."
        raise ValueError(msg)
    return slug


def user_path(name: str) -> Path:
    """File of a user template (``user:`` prefix optional)."""
    return templates_folder() / f"{_slug(name.removeprefix(USER))}.yaml"


def user_templates() -> dict[str, str]:
    """User templates: key ``user:<stem>`` → label."""
    folder = templates_folder()
    if not folder.is_dir():
        return {}
    out = {}
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        out[USER + path.stem] = (
            f"{path.stem} (user template, {data.get('architecture', '?')})"
        )
    return out


def all_templates() -> dict[str, str]:
    """Shipped then user templates: key → label."""
    from predimrc_wrapper.aircraft.project import TEMPLATES  # noqa: PLC0415

    return {**TEMPLATES, **user_templates()}


def load_user(name: str) -> dict[str, Any]:
    """Data of a user template."""
    path = user_path(name)
    if not path.is_file():
        msg = f"No user template {name!r} in {templates_folder()}."
        raise KeyError(msg)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_user(data: dict[str, Any], name: str, overwrite: bool = False) -> Path:
    """Save project data (validated first) as a user template."""
    from predimrc_wrapper.aircraft.project import Project  # noqa: PLC0415

    project = Project.model_validate(data)
    path = user_path(name)
    if path.exists() and not overwrite:
        msg = f"The user template {path.stem!r} exists."
        raise FileExistsError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    project.save(path)
    return path


def rename_user(name: str, new_name: str) -> Path:
    """Rename a user template."""
    source, target = user_path(name), user_path(new_name)
    if target.exists():
        msg = f"The user template {target.stem!r} exists."
        raise FileExistsError(msg)
    return source.rename(target)


def delete_user(name: str) -> None:
    """Delete a user template."""
    user_path(name).unlink()
