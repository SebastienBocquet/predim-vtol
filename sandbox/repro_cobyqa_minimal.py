"""Minimal reproducer: GEMSEO COBYQA ends infeasible where SLSQP finds the optimum.

Standalone (GEMSEO + SciPy only). Toy model of a quadplane lift system:
    bat in [300, 1200] g, D in [10, 14.9] in, empty mass M0 = 1850 g
    flight_time = K * bat / (M0 + bat)**1.5        (maximised)
    margin_tw   = c * D**2 / (M0 + bat) / 1.5 - 1  (>= 0, active at the optimum)
The start point (600 g, 12 in) is infeasible; the optimum is near (337 g, 14.9 in).

GEMSEO normalises the design space to [0, 1] but passes COBYQA its default
initial_tr_radius = 1: COBYQA recentres x0 at the middle of the box, samples the bounds,
heads for the corner where the objective is largest and stops on the minimal trust-region
radius, infeasible. initial_tr_radius = 0.1 fixes it.

    python sandbox/repro_cobyqa_minimal.py
"""

from __future__ import annotations

import logging

import numpy as np
from gemseo import create_design_space
from gemseo import create_discipline
from gemseo import create_scenario
from scipy.optimize import Bounds
from scipy.optimize import NonlinearConstraint
from scipy.optimize import minimize

M0, K, C = 1850.0, 2.0e5, 14.78
LOWER, UPPER, X0 = np.array([300.0, 10.0]), np.array([1200.0, 14.9]), np.array([600.0, 12.0])


def gemseo_run(algo: str, **settings) -> None:
    disc = create_discipline("AnalyticDiscipline", expressions={
        "flight_time": f"{K} * bat / ({M0} + bat)**1.5",
        "margin_tw": f"{C} * D**2 / ({M0} + bat) / 1.5 - 1",
    })
    space = create_design_space()
    space.add_variable("bat", lower_bound=LOWER[0], upper_bound=UPPER[0], value=X0[0])
    space.add_variable("D", lower_bound=LOWER[1], upper_bound=UPPER[1], value=X0[1])
    scenario = create_scenario([disc], "flight_time", space, formulation_name="MDF", maximize_objective=True)
    scenario.add_constraint("margin_tw", constraint_type="ineq", positive=True)
    if algo == "SLSQP":
        scenario.set_differentiation_method("finite_differences", 1e-3)
    scenario.execute(algo_name=algo, max_iter=60, **settings)
    r = scenario.optimization_result
    out = disc.execute({"bat": r.x_opt[:1], "D": r.x_opt[1:]})
    label = algo + "".join(f" {k}={v}" for k, v in settings.items())
    print(f"GEMSEO {label:30s} bat {r.x_opt[0]:7.1f} g  D {r.x_opt[1]:5.2f} in  "
          f"t {out['flight_time'][0]:6.2f}  margin_tw {out['margin_tw'][0]:+.4f}  feasible={r.is_feasible}")


def scipy_run(radius: float) -> None:
    """Same problem straight in SciPy, on the [0, 1] normalised variables as GEMSEO does."""
    def phys(u):
        return LOWER + u * (UPPER - LOWER)

    def margin(u):
        bat, d = phys(u)
        return C * d**2 / (M0 + bat) / 1.5 - 1

    def neg_time(u):
        bat = phys(u)[0]
        return -K * bat / (M0 + bat) ** 1.5

    u0 = (X0 - LOWER) / (UPPER - LOWER)
    r = minimize(neg_time, u0, method="COBYQA", bounds=Bounds([0, 0], [1, 1]),
                 constraints=NonlinearConstraint(margin, 0, np.inf),
                 options={"initial_tr_radius": radius, "maxfev": 200})
    bat, d = phys(r.x)
    print(f"SciPy  COBYQA initial_tr_radius={radius:<4} bat {bat:7.1f} g  D {d:5.2f} in  "
          f"t {-r.fun:6.2f}  margin_tw {margin(r.x):+.4f}  success={r.success} ({r.message})")


if __name__ == "__main__":
    logging.getLogger("gemseo").setLevel(logging.ERROR)
    gemseo_run("SLSQP")
    gemseo_run("COBYQA")
    gemseo_run("COBYQA", initial_tr_radius=0.1)
    scipy_run(1.0)
    scipy_run(0.1)
