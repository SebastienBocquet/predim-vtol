"""Stored studies: explorations and optimisations (INC2-008, REQ-MDO-009).

One unique dated folder per study under a root chosen in the GUI (default: the current
working directory): ``<root>/<YYYYMMDD-HHMMSS>-<kind>-<slug>/`` with ``study.yaml``
(definition, name, base project), ``points.csv`` (one row per evaluated point),
``summary.json`` and ``metadata.json`` (reproducibility). A study is written once
(atomically); only its name can be changed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

STUDY_FILE = "study.yaml"


@dataclass
class StudyDefinition:
    """What was run."""

    kind: str
    """``exploration`` or ``optimisation``."""
    name: str
    mode: str = "two_phase"
    variables: list[dict[str, Any]] = field(default_factory=list)
    """Continuous variables: name, path, lower, upper."""
    choices: dict[str, list] = field(default_factory=dict)
    """Categorical choices by project path."""
    objective: str | None = None
    constraints: list[str] = field(default_factory=list)
    algorithm: str | None = None
    max_iter: int | None = None
    doe: str | None = None
    """``lhs`` or ``full_factorial`` (exploration)."""
    n_samples: int | None = None
    seed: int = 0
    max_sd_rel: float | None = None


@dataclass
class Study:
    """A stored study."""

    definition: StudyDefinition
    base_project: dict[str, Any]
    points: list[dict[str, Any]]
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def id(self) -> str:
        return self.path.name if self.path else ""

    @property
    def name(self) -> str:
        return self.definition.name


def reproducibility_metadata(
    project: Any, seconds: float = float("nan")
) -> dict[str, Any]:
    """Tool version, data hashes, PredimRC profile and workbook hash, date."""
    from importlib.resources import files  # noqa: PLC0415

    from predimrc_wrapper import __version__  # noqa: PLC0415
    from predimrc_wrapper.data import default_tests  # noqa: PLC0415

    motors = files("predimrc_wrapper.data").joinpath("motors_mvp.yaml").read_bytes()
    meta = {
        "tool_version": __version__,
        "date": datetime.now().isoformat(timespec="seconds"),
        "seconds": seconds,
        "test_data_hash": default_tests().hash(),
        "motor_database_hash": hashlib.sha256(motors).hexdigest()[:16],
    }
    if getattr(project, "aero", None) is not None:
        from predimrc_wrapper.api import profiles_dir  # noqa: PLC0415
        from predimrc_wrapper.predimrc_wrapper import workbook_path  # noqa: PLC0415

        meta["predimrc_profile"] = project.aero.profile
        try:
            meta["predimrc_workbook_hash"] = hashlib.sha256(
                workbook_path(profiles_dir(), project.aero.profile).read_bytes()
            ).hexdigest()[:16]
        except FileNotFoundError:
            meta["predimrc_workbook_hash"] = None
    return meta


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "study"


def _write_points(path: Path, points: list[dict[str, Any]]) -> None:
    columns = list(dict.fromkeys(k for p in points for k in p))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for p in points:
            writer.writerow({
                k: json.dumps(v) if isinstance(v, (dict, list)) else v
                for k, v in p.items()
            })


def _parse(value: str) -> Any:
    if value == "":
        return None
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    if value in ("True", "False"):
        return value == "True"
    if value[:1] in "[{":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _read_points(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return [
            {k: _parse(v) for k, v in row.items()} for row in csv.DictReader(stream)
        ]


class StudyStore:
    """Studies under a root folder."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            from predimrc_wrapper.settings import Settings  # noqa: PLC0415

            root = Settings.load().studies_root
        self.root = Path(root)

    def save(self, study: Study) -> Path:
        """Write a new study folder (never overwrites)."""
        self.root.mkdir(parents=True, exist_ok=True)
        base = f"{datetime.now():%Y%m%d-%H%M%S}-{study.definition.kind}-{_slug(study.name)}"
        target, k = self.root / base, 2
        while target.exists():
            target, k = self.root / f"{base}-{k}", k + 1
        tmp = self.root / f".{target.name}.tmp"
        tmp.mkdir()
        (tmp / STUDY_FILE).write_text(
            yaml.safe_dump(
                {
                    "definition": asdict(study.definition),
                    "base_project": study.base_project,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        _write_points(tmp / "points.csv", study.points)
        (tmp / "summary.json").write_text(
            json.dumps(study.summary, indent=2, default=str), encoding="utf-8"
        )
        (tmp / "metadata.json").write_text(
            json.dumps(study.metadata, indent=2, default=str), encoding="utf-8"
        )
        tmp.rename(target)
        study.path = target
        return target

    def list(self) -> list[dict[str, Any]]:
        """The studies of the root, newest first: id, name, kind, date, points, path."""
        out = []
        if not self.root.is_dir():
            return out
        for folder in sorted(self.root.iterdir(), reverse=True):
            file = folder / STUDY_FILE
            if folder.name.startswith(".") or not file.is_file():
                continue
            data = yaml.safe_load(file.read_text(encoding="utf-8"))
            meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            with (folder / "points.csv").open(encoding="utf-8") as stream:
                n = max(0, sum(1 for _ in stream) - 1)
            out.append({
                "id": folder.name,
                "name": data["definition"]["name"],
                "kind": data["definition"]["kind"],
                "mode": data["definition"].get("mode"),
                "date": meta.get("date"),
                "points": n,
                "path": str(folder),
            })
        return out

    def load(self, study_id: str) -> Study:
        folder = self.root / study_id
        data = yaml.safe_load((folder / STUDY_FILE).read_text(encoding="utf-8"))
        return Study(
            StudyDefinition(**data["definition"]),
            data["base_project"],
            _read_points(folder / "points.csv"),
            json.loads((folder / "summary.json").read_text(encoding="utf-8")),
            json.loads((folder / "metadata.json").read_text(encoding="utf-8")),
            folder,
        )

    def rename(self, study_id: str, name: str) -> None:
        file = self.root / study_id / STUDY_FILE
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
        data["definition"]["name"] = name
        file.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    def delete(self, study_id: str) -> None:
        folder = self.root / study_id
        if (folder / STUDY_FILE).is_file():
            shutil.rmtree(folder)

    @staticmethod
    def data_changed(study: Study) -> bool:
        """The test data or the motor database changed since the study."""
        now = reproducibility_metadata(None)
        return any(
            study.metadata.get(k) not in (None, now[k])
            for k in ("test_data_hash", "motor_database_hash")
        )
