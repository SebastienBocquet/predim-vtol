"""Reproducer: COBYQA vs SLSQP on the quadplane (MVP-006), analytic aero backend, no Excel.

Same problem as ``examples/mvp/optim_quadplane.py`` for one lift motor: maximise the
flight time over battery mass, lift propeller diameter and wing panel 2 length, with the
margins ≥ 0. Mirrors ``mdo.optimise._run_one`` but lets the algorithm settings vary and
prints the margins of every evaluation.

    .venv/Scripts/python.exe sandbox/repro_cobyqa_vs_slsqp.py [-v]
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
from gemseo import create_scenario
from gemseo.disciplines.linear_combination import LinearCombination

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.mdo import Parameter  # noqa: E402
from predimrc_wrapper.mdo import PresizingDiscipline  # noqa: E402
from predimrc_wrapper.mdo.optimise import CONSTRAINTS  # noqa: E402
from predimrc_wrapper.mdo.parameters import build_design_space  # noqa: E402
from tests.helpers import ParabolicAero  # noqa: E402

CONTINUOUS = [
    Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 1200.0),
    Parameter("prop_diameter_in", "propulsion_units.lift.prop_diameter_in", "float", 10.0, 14.9),
    Parameter("span_t2_mm", "aero.wing.length_mm.1", "float", 250.0, 350.0),
]

MOTOR = "tmotor-mn2806-400kv"
"""Lift motor for which COBYQA fails (the template's mn2806-650kv does not show it)."""

CASES = [
    ("SLSQP", {}),
    ("COBYQA", {}),  # GEMSEO defaults: initial_tr_radius=1 on the [0, 1] normalised box
    ("COBYQA", {"max_iter": 300}),
    ("COBYQA", {"initial_tr_radius": 0.1}),
    ("NLOPT_COBYLA", {}),
]


def run(algo: str, settings: dict, verbose: bool, motor: str = MOTOR) -> dict:
    project = Project.template("quadplane").with_overrides({"propulsion_units.lift.motor_id": motor})
    disc = PresizingDiscipline(project, CONTINUOUS, backend=ParabolicAero())
    initial = disc.execute()
    ref = float(initial["flight_time"][0])
    constraints = [c for c in CONSTRAINTS if np.isfinite(initial[c][0])]
    space = build_design_space(CONTINUOUS, disc.initial_values())
    ratio = LinearCombination(["flight_time"], "flight_time_ratio", {"flight_time": 1.0 / ref})
    scenario = create_scenario([disc, ratio], "flight_time_ratio", space, formulation_name="MDF",
                               maximize_objective=True)
    for c in constraints:
        scenario.add_constraint(c, constraint_type="ineq", positive=True)
    if algo == "SLSQP":
        scenario.set_differentiation_method("finite_differences", 1e-3)
    settings = {"max_iter": 60, **settings}
    scenario.execute(algo_name=algo, **settings)
    best = scenario.optimization_result
    db = scenario.formulation.optimization_problem.database
    xs = [np.asarray(x.unwrap()) for x in db]
    # GEMSEO stores the ≥ 0 constraints as -c ≤ 0 under "-name"
    hist = {c: [-float(np.ravel(v)[0]) for v in db.get_function_history(f"-{c}")] for c in constraints}
    obj = [-float(np.ravel(v)[0]) * ref for v in db.get_function_history("-flight_time_ratio")]
    if verbose:
        print(f"  {'#':>3} {'bat_g':>7} {'D_in':>6} {'span':>6} {'t_min':>6} " + " ".join(f"{c[7:]:>9}" for c in constraints))
        for i, (x, t) in enumerate(zip(xs, obj)):
            m = " ".join(f"{hist[c][i]:+9.3f}" for c in constraints)
            print(f"  {i:3d} {x[0]:7.1f} {x[1]:6.2f} {x[2]:6.1f} {t / 60:6.2f} {m}")
    x = dict(zip([p.name for p in CONTINUOUS], best.x_opt))
    out = disc.execute({k: np.array([v]) for k, v in x.items()})
    disc.close()
    return {"x": x, "t": float(out["flight_time"][0]) / 60, "n": len(db), "feasible": bool(best.is_feasible),
            "margins": {c: float(out[c][0]) for c in constraints}, "msg": best.message}


def main() -> None:
    logging.getLogger("gemseo").setLevel(logging.ERROR)
    verbose = "-v" in sys.argv
    print(f"lift motor {MOTOR}; start: bat 600 g, D 12 in, span 300 mm; m_max {Project.template('quadplane').max_takeoff_mass_kg} kg\n")
    for algo, settings in CASES:
        label = algo + (" " + ", ".join(f"{k}={v}" for k, v in settings.items()) if settings else "")
        print(f"== {label}")
        try:
            r = run(algo, settings, verbose)
        except Exception as error:  # noqa: BLE001
            print(f"  failed: {error}\n")
            continue
        x = r["x"]
        print(f"  x = bat {x['battery_mass_g']:.1f} g, D {x['prop_diameter_in']:.2f} in, span {x['span_t2_mm']:.1f} mm"
              f" | flight {r['t']:.2f} min | {r['n']} evals | feasible={r['feasible']}")
        print("  margins: " + ", ".join(f"{k[7:]} {v:+.4f}" for k, v in r["margins"].items()))
        print(f"  stop: {r['msg']}\n")


if __name__ == "__main__":
    main()
