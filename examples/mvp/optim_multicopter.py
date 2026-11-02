"""Maximise the flight time of the quadcopter template (no Excel).

Outer loop over the lift motor and the cell count, SLSQP on battery mass and propeller
diameter, constraints on the margins. Arguments: maximum iterations (60), number of lift
motors of the database tried (all).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _optim import optimise  # noqa: E402

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.data import default_database  # noqa: E402
from predimrc_wrapper.mdo import Parameter  # noqa: E402

if __name__ == "__main__":
    project = Project.template("multicopter")
    continuous = [
        Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 1500.0),
        Parameter(
            "prop_diameter_in",
            "propulsion_units.lift.prop_diameter_in",
            "float",
            10.0,
            15.9,
        ),
    ]
    n_motors = int(sys.argv[2]) if len(sys.argv) > 2 else None
    discrete = {
        "propulsion_units.lift.motor_id": default_database().ids("lift")[:n_motors],
        "battery.n_series": [4, 6],
    }
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    optimise(project, continuous, discrete, "optim_multicopter", max_iter=max_iter)
