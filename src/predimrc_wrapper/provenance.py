"""Provenance of the stored results: tool version and hashes of the reference data.

Recorded with every stored study and run (``metadata.json``) so that a result computed
with other reference data (motors, propellers, thrust tests, prices, user data, PredimRC
workbook) can be flagged: :func:`data_changes` names the sources changed since.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from importlib.resources import files
from typing import Any

DATA_FILES = {
    "motors": "motors_mvp.yaml",
    "propellers": "propellers.yaml",
    "prices": "prices.yaml",
    "drag_shapes": "drag_shapes.yaml",
    "boom_sections": "boom_sections.yaml",
}
"""Shipped reference files of ``predimrc_wrapper.data``, by source name."""


def slug(text: str, default: str = "study") -> str:
    """A folder-safe lower-case name of at most 40 characters."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or default


def _digest(chunks) -> str:
    sha = hashlib.sha256()
    for chunk in chunks:
        sha.update(chunk)
    return sha.hexdigest()[:16]


def _folder_digest(folder) -> str:
    """Hash of the names and contents of the files of a folder (recursive)."""
    entries = sorted(
        (str(p.relative_to(folder)).replace("\\", "/"), p)
        for p in folder.rglob("*")
        if p.is_file()
    )
    return _digest(
        chunk for name, p in entries for chunk in (name.encode(), p.read_bytes())
    )


def data_hashes() -> dict[str, str]:
    """Hash of each source of reference data, as of now."""
    from pathlib import Path  # noqa: PLC0415

    from predimrc_wrapper.data.user import user_data_dir  # noqa: PLC0415

    data = files("predimrc_wrapper.data")
    hashes = {
        name: _digest([data.joinpath(file).read_bytes()])
        for name, file in DATA_FILES.items()
    }
    hashes["thrust_tests"] = _folder_digest(Path(str(data.joinpath("thrust_tests"))))
    user = user_data_dir()
    hashes["user_data"] = _folder_digest(user) if user.is_dir() else _digest([])
    return hashes


def _workbook_hash(profile: str) -> str | None:
    from predimrc_wrapper.api import profiles_dir  # noqa: PLC0415
    from predimrc_wrapper.predimrc_wrapper import workbook_path  # noqa: PLC0415

    try:
        return _digest([workbook_path(profiles_dir(), profile).read_bytes()])
    except FileNotFoundError:
        return None


def reproducibility_metadata(
    project: Any, seconds: float = float("nan")
) -> dict[str, Any]:
    """Tool version, data hashes, PredimRC profile and workbook hash, date."""
    from predimrc_wrapper import __version__  # noqa: PLC0415
    from predimrc_wrapper.aircraft.project import FORMAT_VERSION  # noqa: PLC0415
    from predimrc_wrapper.data import default_tests  # noqa: PLC0415

    hashes = data_hashes()
    meta = {
        "tool_version": __version__,
        "format_version": FORMAT_VERSION,
        "date": datetime.now().isoformat(timespec="seconds"),
        "seconds": seconds,
        "test_data_hash": default_tests().hash(),
        "motor_database_hash": hashes["motors"],
        "data_hashes": hashes,
    }
    if getattr(project, "aero", None) is not None:
        meta["predimrc_profile"] = project.aero.profile
        meta["predimrc_workbook_hash"] = _workbook_hash(project.aero.profile)
    return meta


def data_changes(
    metadata: dict[str, Any],
    now: dict[str, str] | None = None,
    workbooks: dict[str, str | None] | None = None,
) -> list[str]:
    """The sources of reference data changed since the metadata was recorded.

    A source missing from the metadata (recorded by an older version) is not reported.

    Args:
        metadata: The metadata of a study or a run.
        now: The current :func:`data_hashes`, computed when not given.
        workbooks: The current hashes of the PredimRC workbooks by profile, filled as
            they are computed (to share them between several calls).
    """
    now = data_hashes() if now is None else now
    workbooks = {} if workbooks is None else workbooks
    recorded = metadata.get("data_hashes")
    if recorded is None:  # metadata of an older version: motors and thrust tests only
        from predimrc_wrapper.data import default_tests  # noqa: PLC0415

        recorded = {"motors": metadata.get("motor_database_hash")}
        now = {**now, "thrust_tests": default_tests().hash()}
        recorded["thrust_tests"] = metadata.get("test_data_hash")
    changed = [
        name
        for name, value in recorded.items()
        if value is not None and name in now and value != now[name]
    ]
    profile = metadata.get("predimrc_profile")
    if profile and profile not in workbooks:
        workbooks[profile] = _workbook_hash(profile)
    if profile and metadata.get("predimrc_workbook_hash") not in (
        None,
        workbooks[profile],
    ):
        changed.append("predimrc_workbook")
    return changed
