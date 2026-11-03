"""GEMSEO discipline of the complete pre-sizing evaluation (REQ-MDO-001, REQ-MDO-005).

Two-phase flight time of the designer's process (``evaluate_two_phase``); outputs
``OUTPUTS`` (arrays of size 1): flight times, ranges, powers, margins, and the cost and
reliability outputs ``cost_purchase``, ``cost_per_hour``, ``motor_out_tw``.

A failing evaluation gives NaN outputs and ``feasible = 0`` instead of stopping the study.
Evaluations are sequential, with one PredimRC session per discipline.
"""

from __future__ import annotations

import logging
from functools import reduce
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from gemseo.core.discipline import Discipline

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import profiles_dir
from predimrc_wrapper.runs.summary import OUTPUTS_TWO_PHASE
from predimrc_wrapper.runs.summary import two_phase_outputs

if TYPE_CHECKING:
    from pathlib import Path

    from predimrc_wrapper.mdo.parameters import Parameter
    from predimrc_wrapper.predimrc_wrapper import AeroBackend

LOGGER = logging.getLogger(__name__)

OUTPUTS = OUTPUTS_TWO_PHASE
"""Outputs of the discipline."""


def _get_path(project: Project, path: str) -> Any:
    def step(node, key):
        if isinstance(node, list):
            return node[int(key)]
        if isinstance(node, dict):
            return node[key]
        return getattr(node, key)

    return reduce(step, path.split("."), project)


class PresizingDiscipline(Discipline):
    """Evaluate the two-phase flight time of a base project with overridden parameters."""

    def __init__(
        self,
        base_project: Project | str | Path,
        parameters: list[Parameter],
        backend: AeroBackend | None = None,
        name: str = "Presizing",
    ) -> None:
        """
        Args:
            base_project: The base project or its file.
            parameters: The design parameters (inputs of the discipline).
            backend: An aero backend; for a quadplane without backend, a PredimRC session
                is opened at the first evaluation and closed by ``close()``.
            name: The discipline name.
        """  # noqa: D205, D212
        super().__init__(name)
        self.base_project = (
            base_project
            if isinstance(base_project, Project)
            else Project.load(base_project)
        )
        self.parameters = list(parameters)
        self._backend = backend
        self._owned_backend = None
        self.calibration_report = None
        if self.base_project.calibration is not None:
            # The measurements describe the base design: its factors apply to every variant.
            from predimrc_wrapper.calibration import calibrate_two_phase  # noqa: PLC0415

            self.base_project, self.calibration_report = calibrate_two_phase(
                self.base_project, self._get_backend()
            )
        self.input_grammar.update_from_names([p.name for p in self.parameters])
        self.output_grammar.update_from_names(list(OUTPUTS))
        self.default_input_data = {
            p.name: np.array([p.to_design_value(_get_path(self.base_project, p.path))])
            for p in self.parameters
        }

    def initial_values(self) -> dict[str, float]:
        """Design values of the base project."""
        return {k: float(v[0]) for k, v in self.default_input_data.items()}

    def _get_backend(self) -> AeroBackend | None:
        if self.base_project.architecture != "quadplane":
            return None
        if self._backend is None:
            from predimrc_wrapper.aero_cache import open_backend  # noqa: PLC0415

            self._owned_backend = open_backend(
                self.base_project.aero.profile, profiles_dir()
            )
            self._backend = self._owned_backend
        return self._backend

    def project_for(self, input_data: dict[str, Any]) -> Project:
        """The project corresponding to design values."""
        from predimrc_wrapper.mdo.parameters import expand_overrides  # noqa: PLC0415

        overrides = {
            p.path: p.to_project_value(input_data[p.name]) for p in self.parameters
        }
        return self.base_project.with_overrides(expand_overrides(overrides))

    def _run(self, input_data):
        from predimrc_wrapper.api import evaluate_two_phase  # noqa: PLC0415

        try:
            project = self.project_for(input_data)
            r = evaluate_two_phase(project, backend=self._get_backend())
        except Exception as error:  # ruff: ignore[blind-except]  (a failed point must not stop a study)
            LOGGER.warning("Evaluation failed for %s: %s", dict(input_data), error)
            out = {k: np.array([np.nan]) for k in OUTPUTS}
            out["feasible"] = np.array([0.0])
            return out
        self.last_result = r
        values = two_phase_outputs(project, r)
        return {k: np.array([float(v)]) for k, v in values.items()}

    def close(self) -> None:
        """Close the PredimRC session opened by the discipline, if any."""
        if self._owned_backend is not None:
            self._owned_backend.close()
            self._owned_backend = None
            self._backend = None
