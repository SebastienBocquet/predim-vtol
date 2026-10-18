"""Maximise the flight time of the quadplane template, PredimRC in the loop.

Outer loop over the lift motor, SLSQP on battery mass, lift propeller diameter and the
length of wing panel 2; n_series fixed to 4 (the AT2308 cruise motor is 2-4S) to keep the Excel budget small. Requires
Windows, Excel and profiles/PredimRC_SD7003.xls (or $PREDIMRC_PROFILES).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _optim import optimise  # noqa: E402

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.data import default_database  # noqa: E402
from predimrc_wrapper.mdo import Parameter  # noqa: E402
from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper  # noqa: E402

PROFILES = Path(__file__).resolve().parents[2] / "profiles"

if __name__ == "__main__":
    project = Project.template("quadplane")
    continuous = [
        Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 1200.0),
        Parameter("prop_diameter_in", "propulsion_units.lift.prop_diameter_in", "float", 10.0, 14.9),
        Parameter("span_t2_mm", "aero.wing.length_mm.1", "float", 250.0, 350.0),
    ]
    discrete = {"propulsion_units.lift.motor_id": default_database().ids("lift")}
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    with PredimRCWrapper(template_dir=PROFILES) as predimrc:
        optimise(project, continuous, discrete, "optim_quadplane", max_iter=max_iter, backend=predimrc)
