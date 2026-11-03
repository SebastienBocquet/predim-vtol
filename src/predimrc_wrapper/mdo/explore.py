"""Exploration of configurations: design of experiments × categorical choices (INC2-008, REQ-MDO-007)."""

from __future__ import annotations

import itertools
import time
from dataclasses import asdict
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from predimrc_wrapper.mdo.discipline import PresizingDiscipline
from predimrc_wrapper.mdo.parameters import Parameter
from predimrc_wrapper.mdo.parameters import expand_overrides
from predimrc_wrapper.mdo.studies import Study
from predimrc_wrapper.mdo.studies import StudyDefinition
from predimrc_wrapper.mdo.studies import reproducibility_metadata

if TYPE_CHECKING:
    from collections.abc import Callable

    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.predimrc_wrapper import AeroBackend


def samples(
    variables: list[Parameter], method: str, n: int, seed: int = 0
) -> np.ndarray:
    """Design points in the variable bounds, shape (n_points, n_variables)."""
    d = len(variables)
    if d == 0:
        return np.zeros((1, 0))
    low = np.array([v.lower for v in variables])
    high = np.array([v.upper for v in variables])
    if method == "full_factorial":
        levels = max(2, round(n ** (1.0 / d)))
        grid = np.array(list(itertools.product(*[np.linspace(0.0, 1.0, levels)] * d)))
    elif method == "lhs":
        from scipy.stats import qmc  # noqa: PLC0415

        grid = qmc.LatinHypercube(d=d, seed=seed).random(n)
    else:
        msg = f"Unknown design of experiments '{method}' (lhs or full_factorial)."
        raise ValueError(msg)
    return low + grid * (high - low)


def pareto_mask(
    points: list[dict[str, Any]], objectives: list[tuple[str, bool]]
) -> np.ndarray:
    """Non-dominated feasible points for objectives given as (output, maximised)."""
    values = np.array(
        [
            [
                (p.get(k) if p.get(k) is not None else np.nan) * (1 if maximise else -1)
                for k, maximise in objectives
            ]
            for p in points
        ],
        dtype=float,
    )
    ok = np.array([bool(p.get("feasible")) for p in points]) & np.all(
        np.isfinite(values), axis=1
    )
    mask = np.zeros(len(points), dtype=bool)
    for i in np.flatnonzero(ok):
        others = values[ok]
        dominated = np.any(
            np.all(others >= values[i], axis=1) & np.any(others > values[i], axis=1)
        )
        mask[i] = not dominated
    return mask


def explore(
    project: Project,
    variables: list[Parameter],
    choices: dict[str, list] | None = None,
    method: str = "lhs",
    n_samples: int = 20,
    seed: int = 0,
    backend: AeroBackend | None = None,
    name: str = "exploration",
    progress: Callable[[int, int], None] | None = None,
) -> Study:
    """Evaluate every design point for every combination of the categorical choices.

    Returns:
        The study (not saved): one point per evaluation with the choice, the variables, the
        discipline outputs and the error message of a failed point.
    """
    choices = choices or {}
    combos = list(itertools.product(*choices.values())) or [()]
    design = samples(variables, method, n_samples, seed)
    total, done = len(combos) * len(design), 0
    points = []
    start = time.perf_counter()
    for combo in combos:
        choice = dict(zip(choices, combo, strict=False))
        disc = None
        try:
            disc = PresizingDiscipline(
                project.with_overrides(expand_overrides(choice)),
                variables,
                backend=backend,
            )
            for x in design:
                if progress is not None:
                    progress(done, total)
                values = {
                    v.name: float(xi) for v, xi in zip(variables, x, strict=False)
                }
                out = disc.execute({k: np.array([v]) for k, v in values.items()})
                points.append({
                    **choice,
                    **values,
                    **{k: float(v[0]) for k, v in out.items() if k not in values},
                    "error": "",
                })
                done += 1
        except Exception as error:  # ruff: ignore[blind-except]  (an invalid combination must not stop the study)
            for x in design[
                len([
                    p for p in points if all(p.get(k) == v for k, v in choice.items())
                ]) :
            ]:
                points.append({
                    **choice,
                    **{v.name: float(xi) for v, xi in zip(variables, x, strict=False)},
                    "feasible": 0.0,
                    "error": str(error),
                })
                done += 1
        finally:
            if disc is not None:
                disc.close()
    definition = StudyDefinition(
        "exploration",
        name,
        "two_phase",
        [asdict(v) | {"mapping": None} for v in variables],
        choices,
        doe=method,
        n_samples=n_samples,
        seed=seed,
    )
    feasible = sum(bool(p.get("feasible")) for p in points)
    seconds = time.perf_counter() - start
    return Study(
        definition,
        project.to_dict(),
        points,
        {"points": len(points), "feasible": feasible},
        reproducibility_metadata(project, seconds),
    )


def study_from_optimisation(
    summary: Any,
    project: Project,
    variables: list[Parameter],
    choices: dict[str, list],
    constraints: list[str],
    algorithm: str,
    max_iter: int,
    name: str = "optimisation",
    max_sd_rel: float | None = None,
) -> Study:
    """Turn an ``OptimisationSummary`` into a study: one point per discrete choice (its optimum)."""
    points = [
        {
            **r.choice,
            **r.x,
            **r.outputs,
            "feasible": float(r.feasible),
            "evaluations": len(r.history),
            "history": r.history,
            "constraints_applied": r.constraints,
            "error": r.error,
        }
        for r in summary.runs
    ]
    best = summary.best
    definition = StudyDefinition(
        "optimisation",
        name,
        "two_phase",
        [asdict(v) | {"mapping": None} for v in variables],
        choices,
        summary.objective,
        list(constraints),
        algorithm,
        max_iter,
        max_sd_rel=max_sd_rel,
    )
    return Study(
        definition,
        project.to_dict(),
        points,
        {
            "objective": summary.objective,
            "maximize": summary.maximize,
            "best_choice": best.choice if best else None,
            "best_x": best.x if best else None,
            "best_overrides": summary.best_overrides(variables) if best else None,
        },
        reproducibility_metadata(project, summary.seconds),
    )
