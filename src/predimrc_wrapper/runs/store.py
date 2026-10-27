"""Stored runs: one two-phase evaluation of a project, saved on demand (Save run).

One unique dated folder per run under ``<studies root>/runs``:
``<YYYYMMDD-HHMMSS>-<slug>/`` with ``project.yaml`` (the project evaluated, as entered),
``summary.json`` (metadata, inputs and outputs), ``result.json`` (the detailed
``TwoPhaseResult``, for the curves) and ``metadata.json`` (reproducibility). A run is
written once (atomically); only its name can be changed.

Backward compatibility: the outputs are frozen, the inputs are recomputed from the
project migrated to the current format (:meth:`.Project.model_validate`), so that a
renamed project field gives one column for the old and the new runs. When a project no
longer loads, the inputs stored in ``summary.json`` are used and ``project_loadable`` is
``False``.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pandas import DataFrame

from predimrc_wrapper.provenance import data_changes
from predimrc_wrapper.provenance import data_hashes
from predimrc_wrapper.provenance import reproducibility_metadata
from predimrc_wrapper.provenance import slug
from predimrc_wrapper.runs.collection import PROVENANCE_PREFIX
from predimrc_wrapper.runs.collection import RunResults
from predimrc_wrapper.runs.operations import INPUT_PREFIX
from predimrc_wrapper.runs.operations import OUTPUT_PREFIX
from predimrc_wrapper.runs.summary import SUMMARY_VERSION
from predimrc_wrapper.runs.summary import flatten_inputs
from predimrc_wrapper.runs.summary import two_phase_outputs
from predimrc_wrapper.runs.summary import upgrade_outputs

LOGGER = logging.getLogger(__name__)

SUMMARY_FILE = "summary.json"

_INPUTS_CACHE: dict[tuple[str, float, int, str], tuple[dict[str, Any], bool]] = {}
"""Inputs recomputed from the migrated projects, by (folder, mtime, format, tool version)."""


@dataclass
class StoredRun:
    """A stored run."""

    summary: dict[str, Any]
    project_data: dict[str, Any]
    result: dict[str, Any]
    """``TwoPhaseResult.to_dict()``: plain data, read with ``.get`` (keys may be missing)."""
    metadata: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def id(self) -> str:
        return self.path.name if self.path else ""

    @property
    def name(self) -> str:
        return self.summary.get("run_name", "")

    def project(self):
        """The project of the run, migrated to the current format.

        Raises:
            ValidationError: When the project no longer loads.
        """
        from predimrc_wrapper.aircraft import Project  # noqa: PLC0415

        return Project.model_validate(self.project_data)

    def data_changes(self) -> list[str]:
        """The sources of reference data changed since the run."""
        return data_changes(self.metadata)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _current_inputs(
    folder: Path, summary: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """The inputs of a run from its migrated project, else the stored ones."""
    from predimrc_wrapper import __version__  # noqa: PLC0415
    from predimrc_wrapper.aircraft import Project  # noqa: PLC0415
    from predimrc_wrapper.aircraft.project import FORMAT_VERSION  # noqa: PLC0415

    file = folder / "project.yaml"
    key = (
        str(folder),
        file.stat().st_mtime if file.is_file() else 0.0,
        FORMAT_VERSION,
        __version__,
    )
    if key not in _INPUTS_CACHE:
        try:
            project = Project.model_validate(
                yaml.safe_load(file.read_text(encoding="utf-8"))
            )
            _INPUTS_CACHE[key] = (flatten_inputs(project.to_dict()), True)
        except Exception as error:  # ruff: ignore[blind-except]
            LOGGER.warning(
                "The project of the run %s no longer loads (%s): its stored inputs are used.",
                folder.name,
                error,
            )
            _INPUTS_CACHE[key] = (dict(summary.get("inputs", {})), False)
    return _INPUTS_CACHE[key]


class RunStore:
    """Runs under a root folder."""

    def __init__(self, root: str | Path | None = None) -> None:
        """
        Args:
            root: The folder of the runs; ``<studies root>/runs`` by default.
        """
        if root is None:
            from predimrc_wrapper.settings import Settings  # noqa: PLC0415

            root = Path(Settings.load().studies_root) / "runs"
        self.root = Path(root)

    def save(
        self,
        project: Any,
        result: Any,
        name: str = "",
        project_file: str | Path | None = None,
        seconds: float = float("nan"),
    ) -> Path:
        """Write a new run folder (never overwrites).

        Args:
            project: The ``Project`` evaluated.
            result: Its ``TwoPhaseResult``.
            name: The name of the run; the project name by default.
            project_file: The file the project came from, if any.
            seconds: The duration of the evaluation.

        Returns:
            The folder of the run.
        """
        name = name.strip() or project.name
        metadata = reproducibility_metadata(project, seconds)
        self.root.mkdir(parents=True, exist_ok=True)
        base = f"{datetime.now():%Y%m%d-%H%M%S}-{slug(name, 'run')}"
        target, k = self.root / base, 2
        while target.exists():
            target, k = self.root / f"{base}-{k}", k + 1
        data = project.to_dict()
        summary = {
            "summary_version": SUMMARY_VERSION,
            "run_name": name,
            "date": metadata["date"],
            "project_name": project.name,
            "project_file": str(project_file) if project_file else "",
            "architecture": project.architecture,
            "format_version": data.get("format_version"),
            "tool_version": metadata["tool_version"],
            "feasible": bool(result.feasible),
            "limiting": result.limiting,
            "inputs": flatten_inputs(data),
            "outputs": two_phase_outputs(project, result),
        }
        tmp = self.root / f".{target.name}.tmp"
        tmp.mkdir()
        (tmp / "project.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        for file, content in (
            (SUMMARY_FILE, summary),
            ("result.json", result.to_dict()),
            ("metadata.json", metadata),
        ):
            (tmp / file).write_text(
                json.dumps(content, indent=2, default=str), encoding="utf-8"
            )
        tmp.rename(target)
        return target

    def _folders(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return [
            folder
            for folder in sorted(self.root.iterdir(), reverse=True)
            if not folder.name.startswith(".") and (folder / SUMMARY_FILE).is_file()
        ]

    def list(self) -> list[dict[str, Any]]:
        """The runs of the root, newest first: id, name, project, architecture, date, path."""
        out = []
        for folder in self._folders():
            s = _read_json(folder / SUMMARY_FILE)
            out.append({
                "id": folder.name,
                "name": s.get("run_name", folder.name),
                "project_name": s.get("project_name", ""),
                "architecture": s.get("architecture", ""),
                "date": s.get("date"),
                "feasible": s.get("feasible"),
                "path": str(folder),
            })
        return out

    def load(self, run_id: str) -> StoredRun:
        folder = self.root / run_id
        if not (folder / SUMMARY_FILE).is_file():
            raise KeyError(run_id)
        return StoredRun(
            _read_json(folder / SUMMARY_FILE),
            yaml.safe_load((folder / "project.yaml").read_text(encoding="utf-8")),
            _read_json(folder / "result.json"),
            _read_json(folder / "metadata.json"),
            folder,
        )

    def rename(self, run_id: str, name: str) -> None:
        file = self.root / run_id / SUMMARY_FILE
        data = _read_json(file)
        data["run_name"] = name
        file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def delete(self, run_id: str) -> None:
        folder = self.root / run_id
        if (folder / SUMMARY_FILE).is_file():
            shutil.rmtree(folder)

    def rerun(self, run_id: str, backend: Any = None) -> Path:
        """Evaluate the project of a run again, with the current data, as a new run.

        Args:
            run_id: The run.
            backend: The PredimRC backend (quadplane); a session is opened otherwise.

        Returns:
            The folder of the new run, named ``<name> (re-run)``.
        """
        from time import perf_counter  # noqa: PLC0415

        from predimrc_wrapper.api import evaluate_two_phase  # noqa: PLC0415

        run = self.load(run_id)
        project = run.project()
        start = perf_counter()
        result = evaluate_two_phase(project, backend=backend)
        return self.save(
            project,
            result,
            f"{run.name} (re-run)",
            run.summary.get("project_file") or None,
            perf_counter() - start,
        )

    def _row(
        self, folder: Path, now: dict[str, str], workbooks: dict
    ) -> dict[str, Any]:
        summary = _read_json(folder / SUMMARY_FILE)
        metadata = _read_json(folder / "metadata.json")
        inputs, loadable = _current_inputs(folder, summary)
        outputs = upgrade_outputs(summary.get("outputs", {}))
        row = {
            "run_id": folder.name,
            "run_name": summary.get("run_name", folder.name),
            "date": summary.get("date") or metadata.get("date", ""),
            "project_name": summary.get("project_name", ""),
            "project_file": summary.get("project_file", ""),
            "architecture": summary.get("architecture", ""),
            "feasible": bool(summary.get("feasible", False)),
            "limiting": summary.get("limiting", ""),
            "tool_version": summary.get("tool_version") or metadata.get("tool_version"),
            "format_version": summary.get("format_version"),
            "project_loadable": loadable,
            "data_changed": ", ".join(data_changes(metadata, now, workbooks)),
            "path": str(folder),
        }
        for name, value in (metadata.get("data_hashes") or {}).items():
            row[f"{PROVENANCE_PREFIX}{name}"] = value
        if metadata.get("predimrc_workbook_hash"):
            row[f"{PROVENANCE_PREFIX}predimrc_workbook"] = metadata[
                "predimrc_workbook_hash"
            ]
        for name, value in inputs.items():
            row[f"{INPUT_PREFIX}{name}"] = value
        for name, value in outputs.items():
            row[f"{OUTPUT_PREFIX}{name}"] = math.nan if value is None else value
        return row

    def collection(self) -> RunResults:
        """All the runs of the root, as a collection (filter it with ``filter``)."""
        now, workbooks = data_hashes(), {}
        rows = [self._row(folder, now, workbooks) for folder in self._folders()]
        summaries = DataFrame(rows)
        if summaries.empty:
            summaries = DataFrame(
                columns=[
                    "run_id",
                    "run_name",
                    "date",
                    "project_name",
                    "architecture",
                    "feasible",
                ]
            )
        return RunResults(summaries, lambda row: self.load(row["run_id"]))


def load_runs(root: str | Path | None = None, **filters: Any) -> RunResults:
    """The stored runs, filtered (see :meth:`.RunResults.filter`).

    Args:
        root: The folder of the runs; ``<studies root>/runs`` by default.
        **filters: The arguments of :meth:`.RunResults.filter`.
    """
    runs = RunStore(root).collection()
    return runs.filter(**filters) if filters else runs
