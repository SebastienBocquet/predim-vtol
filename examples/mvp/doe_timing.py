"""20-point LHS DOE to measure the evaluation time (REQ-MDO-004, budget of REQ-MDO-006).

Usage: ``python doe_timing.py [quadplane|multicopter]`` (quadplane needs Excel).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from gemseo import create_scenario

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.mdo import Parameter
from predimrc_wrapper.mdo import PresizingDiscipline
from predimrc_wrapper.mdo import build_design_space
from predimrc_wrapper.mdo import from_database

PROFILES = Path(__file__).resolve().parents[2] / "profiles"
OUT = Path(__file__).parent / "outputs"

if __name__ == "__main__":
    logging.getLogger("gemseo").setLevel(logging.WARNING)
    architecture = sys.argv[1] if len(sys.argv) > 1 else "multicopter"
    project = Project.template(architecture)
    parameters = [
        Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 1200.0),
        Parameter("n_series", "battery.n_series", "integer", 4, 6),
        from_database("lift_motor", "propulsion_units.lift.motor_id", role="lift"),
    ]
    if architecture == "quadplane":
        parameters.append(
            Parameter("span_t2_mm", "aero.wing.length_mm.1", "float", 250.0, 350.0)
        )
        from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper

        context = PredimRCWrapper(template_dir=PROFILES)
        backend = context.__enter__()
    else:
        context = backend = None
    try:
        disc = PresizingDiscipline(project, parameters, backend=backend)
        scenario = create_scenario(
            [disc],
            "flight_time_v1",
            build_design_space(parameters),
            formulation_name="DisciplinaryOpt",
            scenario_type="DOE",
        )
        start = time.perf_counter()
        scenario.execute(algo_name="LHS", n_samples=20)
        elapsed = time.perf_counter() - start
        print(
            f"{architecture}: 20 evaluations in {elapsed:.1f} s, {elapsed / 20:.3f} s per evaluation"
        )
        print(
            f"100 configurations would take about {5 * elapsed:.0f} s (budget 20 s, measured not required)"
        )
        dataset = scenario.to_dataset()
        OUT.mkdir(exist_ok=True)
        study = {
            "seconds": elapsed,
            "mappings": {
                p.name: list(p.mapping.labels) for p in parameters if p.mapping
            },
            "samples": [
                {k: float(v) for k, v in row.items()}
                for row in dataset
                .get_view()
                .droplevel([0, 2], axis=1)
                .to_dict("records")
            ],
        }
        (OUT / f"doe_timing_{architecture}.json").write_text(
            json.dumps(study, indent=2), encoding="utf-8"
        )
    finally:
        if context is not None:
            context.close()
