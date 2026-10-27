"""GEMSEO discipline of the complete pre-sizing evaluation (REQ-MDO-001, REQ-MDO-005).

Outputs (arrays of size 1):

| Name | Unit | Meaning |
|---|---|---|
| ``flight_time`` | s | flight time of the scenario |
| ``range`` | m | distance flown |
| ``v_endurance``, ``v_range`` | m/s | optimal cruise speeds |
| ``mass_total`` | kg | total mass |
| ``margin_motor_current``, ``margin_motor_power``, ``margin_voltage``, ``margin_battery_c`` | — | operating margins (≥ 0 is acceptable) |
| ``margin_thrust_to_weight`` | — | lift T/W / T/W_min − 1 |
| ``margin_mass`` | — | 1 − m / m_max (NaN without m_max) |
| ``feasible`` | — | 1 if the scenario is feasible, else 0 |

Two-phase mode: ``OUTPUTS_TWO_PHASE`` (flight times, ranges, powers, margins, and the cost and
reliability outputs ``cost_purchase``, ``cost_per_hour``, ``motor_out_tw``).

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
from predimrc_wrapper.api import _solve
from predimrc_wrapper.api import profiles_dir
from predimrc_wrapper.runs.summary import OUTPUTS_TWO_PHASE
from predimrc_wrapper.runs.summary import two_phase_outputs

if TYPE_CHECKING:
    from pathlib import Path

    from predimrc_wrapper.mdo.parameters import Parameter
    from predimrc_wrapper.predimrc_wrapper import AeroBackend

LOGGER = logging.getLogger(__name__)

OUTPUTS = (
    "flight_time",
    "range",
    "v_endurance",
    "v_range",
    "mass_total",
    "margin_motor_current",
    "margin_motor_power",
    "margin_voltage",
    "margin_battery_c",
    "margin_thrust_to_weight",
    "margin_mass",
    "feasible",
)
"""Outputs of the scenario mode (MVP solver)."""


def outputs_of(mode: str) -> tuple[str, ...]:
    return OUTPUTS_TWO_PHASE if mode == "two_phase" else OUTPUTS


def _get_path(project: Project, path: str) -> Any:
    def step(node, key):
        if isinstance(node, list):
            return node[int(key)]
        if isinstance(node, dict):
            return node[key]
        return getattr(node, key)

    return reduce(step, path.split("."), project)


class PresizingDiscipline(Discipline):
    """Evaluate one scenario of a base project with overridden parameters."""

    def __init__(
        self,
        base_project: Project | str | Path,
        parameters: list[Parameter],
        scenario: str | None = None,
        backend: AeroBackend | None = None,
        name: str = "Presizing",
        mode: str = "scenario",
    ) -> None:
        """
        Args:
            base_project: The base project or its file.
            parameters: The design parameters (inputs of the discipline).
            scenario: The scenario name; the first one of the project by default.
            backend: An aero backend; for a quadplane without backend, a PredimRC session
                is opened at the first evaluation and closed by ``close()``.
            name: The discipline name.
            mode: ``scenario`` (MVP solver, outputs ``OUTPUTS``) or ``two_phase``
                (designer's flight time, outputs ``OUTPUTS_TWO_PHASE``; the calibration
                block is not applied).
        """  # noqa: D205, D212
        super().__init__(name)
        self.mode = mode
        self.base_project = (
            base_project
            if isinstance(base_project, Project)
            else Project.load(base_project)
        )
        self.parameters = list(parameters)
        self.scenario = scenario or next(iter(self.base_project.scenarios))
        self._backend = backend
        self._owned_backend = None
        self.calibration_report = None
        if self.base_project.calibration is not None:
            # The measurements describe the base design: its factors apply to every variant.
            from predimrc_wrapper.calibration import calibrate  # noqa: PLC0415
            from predimrc_wrapper.calibration import calibrate_two_phase  # noqa: PLC0415

            run = calibrate_two_phase if mode == "two_phase" else calibrate
            self.base_project, self.calibration_report = run(
                self.base_project, self._get_backend()
            )
        self.input_grammar.update_from_names([p.name for p in self.parameters])
        self.output_grammar.update_from_names(list(outputs_of(mode)))
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
        if self.mode == "two_phase":
            return self._run_two_phase(input_data)
        try:
            result = _solve(
                self.project_for(input_data), self.scenario, self._get_backend()
            )
        except Exception as error:  # ruff: ignore[blind-except]  (a failed point must not stop a study)
            LOGGER.warning("Evaluation failed for %s: %s", dict(input_data), error)
            out = {k: np.array([np.nan]) for k in OUTPUTS}
            out["feasible"] = np.array([0.0])
            return out
        m = result.margins
        values = {
            "flight_time": result.flight_time_s,
            "range": result.range_m,
            "v_endurance": result.v_endurance,
            "v_range": result.v_range,
            "mass_total": result.mass_total_kg,
            "margin_motor_current": m["motor_current"],
            "margin_motor_power": m["motor_power"],
            "margin_voltage": m["voltage"],
            "margin_battery_c": m["battery_c"],
            "margin_thrust_to_weight": m["thrust_to_weight"],
            "margin_mass": m["mass"],
            "feasible": float(result.feasible),
        }
        return {k: np.array([float(v)]) for k, v in values.items()}

    def _run_two_phase(self, input_data):
        from predimrc_wrapper.api import evaluate_two_phase  # noqa: PLC0415

        try:
            project = self.project_for(input_data)
            r = evaluate_two_phase(project, backend=self._get_backend())
        except Exception as error:  # ruff: ignore[blind-except]  (a failed point must not stop a study)
            LOGGER.warning("Evaluation failed for %s: %s", dict(input_data), error)
            out = {k: np.array([np.nan]) for k in OUTPUTS_TWO_PHASE}
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
