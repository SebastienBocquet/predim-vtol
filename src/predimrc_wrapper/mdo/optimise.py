"""Optimisation loop: outer loop over discrete choices, GEMSEO optimiser on the continuous
variables, inequality constraints on the margins (≥ 0)."""

from __future__ import annotations

import itertools
import logging
import time
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from gemseo import create_scenario
from gemseo import get_available_opt_algorithms
from gemseo.disciplines.linear_combination import LinearCombination

from predimrc_wrapper.mdo.discipline import PresizingDiscipline
from predimrc_wrapper.mdo.parameters import build_design_space

if TYPE_CHECKING:
    from collections.abc import Callable

    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.mdo.parameters import Parameter
    from predimrc_wrapper.predimrc_wrapper import AeroBackend

CONSTRAINTS = (
    "margin_motor_current",
    "margin_battery_c",
    "margin_thrust_to_weight",
    "margin_mass",
)
"""Default constraints (≥ 0) of the scenario mode."""

CONSTRAINTS_TWO_PHASE = (
    "margin_motor_power",
    "margin_motor_current",
    "margin_battery_c",
    "margin_thrust_to_weight",
    "margin_mass",
)
"""Default constraints (≥ 0) of the two-phase mode."""

OBJECTIVES = {
    "flight_time": True,
    "range": True,
    "mass_total": False,
    "flight_time_v1": True,
    "flight_time_v2": True,
    "range_v1": True,
    "range_v2": True,
    "cost_purchase": False,
    "cost_per_hour": False,
    "motor_out_tw": True,
}
"""Objectives offered, with whether they are maximised (``*_v1``, ``*_v2`` and the cost and
reliability outputs: two-phase mode)."""

TWO_PHASE_ONLY = ("cost_purchase", "cost_per_hour", "motor_out_tw")


def mode_of(objective: str) -> str:
    """The discipline mode giving an objective."""
    two_phase = objective.endswith(("_v1", "_v2")) or objective in TWO_PHASE_ONLY
    return "two_phase" if two_phase else "scenario"


ALGORITHMS = ("SLSQP", "NLOPT_COBYLA", "COBYQA", "NLOPT_SLSQP")
"""Algorithms offered, when installed (NLOPT_* need ``gemseo[all]``)."""

GRADIENT_FREE = ("NLOPT_COBYLA", "COBYQA")


def available_algorithms() -> list[str]:
    """The offered algorithms installed in this environment."""
    installed = set(get_available_opt_algorithms())
    return [a for a in ALGORITHMS if a in installed]


@dataclass
class OptimisationRun:
    """Result of one discrete choice."""

    choice: dict[str, Any]
    x: dict[str, float]
    outputs: dict[str, float]
    feasible: bool
    history: list[float] = field(default_factory=list)
    """Objective value at each evaluation (SI)."""
    error: str = ""
    constraints: list[str] = field(default_factory=list)
    """Constraints applied (the not applicable ones, NaN at the start, are dropped)."""


@dataclass
class OptimisationSummary:
    """All the runs and the best feasible one."""

    objective: str
    maximize: bool
    runs: list[OptimisationRun]
    seconds: float
    mode: str = "scenario"

    @property
    def best(self) -> OptimisationRun | None:
        candidates = [r for r in self.runs if r.feasible and not r.error] or [
            r for r in self.runs if not r.error
        ]
        if not candidates:
            return None
        key = (
            (lambda r: r.outputs[self.objective])
            if self.maximize
            else (lambda r: -r.outputs[self.objective])
        )
        return max(candidates, key=key)

    def best_overrides(self, continuous: list[Parameter]) -> dict[str, Any]:
        """Project overrides of the best design (discrete choice and continuous values)."""
        best = self.best
        if best is None:
            return {}
        by_name = {p.name: p for p in continuous}
        return {
            **best.choice,
            **{
                by_name[k].path: by_name[k].to_project_value(v)
                for k, v in best.x.items()
            },
        }

    def to_dict(self) -> dict[str, Any]:
        best = self.best
        return {
            "objective": self.objective,
            "maximize": self.maximize,
            "seconds": self.seconds,
            "mode": self.mode,
            "best": asdict(best) if best else None,
            "all": [asdict(r) for r in self.runs],
        }


def optimise(
    project: Project,
    continuous: list[Parameter],
    discrete: dict[str, list] | None = None,
    objective: str = "flight_time",
    constraints: tuple[str, ...] | None = None,
    algo: str = "SLSQP",
    max_iter: int = 60,
    backend: AeroBackend | None = None,
    progress: Callable[[int, int, dict], None] | None = None,
    max_sd_rel: float | None = None,
    mode: str | None = None,
) -> OptimisationSummary:
    """Optimise the objective for every combination of the discrete choices.

    Args:
        project: The base project (calibrated once by the discipline if it has measurements).
        continuous: The continuous design parameters.
        discrete: Values by project path; every combination is optimised.
        objective: A discipline output, see ``OBJECTIVES``.
        constraints: Discipline outputs constrained to be ≥ 0; the defaults of the mode when None.
        algo: A GEMSEO optimisation algorithm.
        max_iter: The maximum number of iterations per combination.
        backend: The aero backend (quadplane).
        progress: Called with (index, number of combinations, choice) before each one.
        max_sd_rel: Two-phase mode: constrain the largest relative σ of the hover power.
        mode: ``scenario`` or ``two_phase``; from the objective by default.
    """
    from predimrc_wrapper.mdo.parameters import expand_overrides  # noqa: PLC0415

    mode = mode or mode_of(objective)
    if constraints is None:
        constraints = CONSTRAINTS_TWO_PHASE if mode == "two_phase" else CONSTRAINTS
    logging.getLogger("gemseo").setLevel(logging.WARNING)
    maximize = OBJECTIVES[objective]
    discrete = discrete or {}
    combos = list(itertools.product(*discrete.values())) or [()]
    runs = []
    start = time.perf_counter()
    for i, combo in enumerate(combos):
        choice = dict(zip(discrete, combo, strict=False))
        if progress is not None:
            progress(i, len(combos), choice)
        disc = None
        try:
            disc = PresizingDiscipline(
                project.with_overrides(expand_overrides(choice)),
                continuous,
                backend=backend,
                mode=mode,
            )
            runs.append(
                _run_one(
                    disc,
                    choice,
                    continuous,
                    objective,
                    maximize,
                    constraints,
                    algo,
                    max_iter,
                    max_sd_rel,
                )
            )
        except Exception as error:  # ruff: ignore[blind-except]  (an invalid combination must not stop the study)
            runs.append(OptimisationRun(choice, {}, {}, False, error=str(error)))
        finally:
            if disc is not None:
                disc.close()
    return OptimisationSummary(
        objective, maximize, runs, time.perf_counter() - start, mode
    )


def _run_one(
    disc: PresizingDiscipline,
    choice: dict,
    continuous: list[Parameter],
    objective: str,
    maximize: bool,
    constraints: tuple[str, ...],
    algo: str,
    max_iter: int,
    max_sd_rel: float | None = None,
) -> OptimisationRun:
    initial = disc.execute()
    names = set(initial)
    ref = float(initial[objective][0])
    ref = abs(ref) if np.isfinite(ref) and ref != 0 else 1.0
    # A NaN margin is not applicable (e.g. no maximum take-off mass): it would stop the optimiser.
    constraints = tuple(
        c for c in constraints if c in names and np.isfinite(initial[c][0])
    )
    if not continuous:
        out = {k: float(v[0]) for k, v in disc.execute().items()}
        feasible = all(out[c] >= 0 for c in constraints) and out["feasible"] > 0
        return OptimisationRun(
            choice, {}, out, feasible, [out[objective]], constraints=list(constraints)
        )
    space = build_design_space(continuous, disc.initial_values())
    # Objective of order 1, like the margins, so that the optimiser weighs the constraints.
    name = f"{objective}_ratio"
    ratio = LinearCombination([objective], name, {objective: 1.0 / ref})
    disciplines = [disc, ratio]
    if max_sd_rel is not None and "max_sd_rel" in names:
        disciplines.append(
            LinearCombination(
                ["max_sd_rel"], "margin_sd", {"max_sd_rel": -1.0}, offset=max_sd_rel
            )
        )
        constraints = (*constraints, "margin_sd")
    scenario = create_scenario(
        disciplines, name, space, formulation_name="MDF", maximize_objective=maximize
    )
    for c in constraints:
        scenario.add_constraint(c, constraint_type="ineq", positive=True)
    if algo not in GRADIENT_FREE:
        scenario.set_differentiation_method(
            "finite_differences", 1e-3
        )  # above the speed-sweep noise
    scenario.execute(algo_name=algo, max_iter=max_iter)
    best = scenario.optimization_result
    x = {p.name: float(v) for p, v in zip(continuous, best.x_opt, strict=False)}
    outputs = {
        k: float(v[0])
        for k, v in disc.execute({k: np.array([v]) for k, v in x.items()}).items()
        if k not in x
    }
    history = _history(scenario, name, ref)
    return OptimisationRun(
        choice,
        x,
        outputs,
        bool(best.is_feasible),
        history,
        constraints=list(constraints),
    )


def _history(scenario, name: str, ref: float) -> list[float]:
    """Objective values in evaluation order (a maximised objective is stored as '-name')."""
    database = scenario.formulation.optimization_problem.database
    for key in (name, f"-{name}"):
        if key in database.get_function_names():
            return [
                abs(float(np.ravel(v)[0])) * ref
                for v in database.get_function_history(key)
            ]
    return []
