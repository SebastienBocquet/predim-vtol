"""Single entry point used by GEMSEO and the GUI: ``evaluate_two_phase(project)``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project

if TYPE_CHECKING:
    from pathlib import Path

    from predimrc_wrapper.predimrc_wrapper import AeroBackend


def profiles_dir() -> Path:
    """Folder of the PredimRC workbooks: user settings, overridden by $PREDIMRC_PROFILES."""
    from predimrc_wrapper.settings import predimrc_folder  # noqa: PLC0415

    return predimrc_folder()


def evaluate_two_phase(
    project: Project | str | Path,
    backend: AeroBackend | None = None,
    hover_time_s: float | None = None,
    target_speeds_m_s: tuple[float, float] | None = None,
):
    """Two-phase flight time of the designer's process (INC2-007).

    Args:
        project: The project, or the path of a project file.
        backend: The PredimRC backend; for a quadplane without backend, a PredimRC session
            is opened for this call and closed afterwards.
        hover_time_s: The hover time; ``project.mission.hover_time_s`` by default.
        target_speeds_m_s: The cruise speeds V1, V2; the project ones, else minimum power
            and maximum L/D.

    Returns:
        The ``TwoPhaseResult``; a project with a ``calibration`` block is calibrated first
        (``calibrate_two_phase``), the report in ``metadata["calibration"]``.
    """
    from predimrc_wrapper.mission.two_phase import TwoPhaseEvaluation  # noqa: PLC0415

    if not isinstance(project, Project):
        project = Project.load(project)
    mission = project.mission
    t_h = mission.hover_time_s if hover_time_s is None else hover_time_s
    speeds = target_speeds_m_s or (
        tuple(mission.target_speeds_m_s) if mission.target_speeds_m_s else None
    )

    def solve(backend):
        calibrated, report = project, None
        if project.calibration is not None:
            from predimrc_wrapper.calibration import calibrate_two_phase  # noqa: PLC0415

            calibrated, report = calibrate_two_phase(project, backend)
        result = TwoPhaseEvaluation(
            AircraftModel(calibrated, aero_backend=backend)
        ).solve(t_h, speeds)
        if report is not None:
            result.metadata["calibration"] = report.to_dict()
        return result

    if project.architecture == "quadplane" and backend is None:
        from predimrc_wrapper.aero_cache import open_backend  # noqa: PLC0415

        with open_backend(project.aero.profile, profiles_dir()) as session:
            return solve(session)
    return solve(backend)
