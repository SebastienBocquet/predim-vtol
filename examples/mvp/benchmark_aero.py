"""Measure the cost of one PredimRC evaluation (REQ-AERO-007).

20 evaluations of tricoptere_short_2 with a varying length of wing panel 2, in one
Excel session.
"""

from __future__ import annotations

import copy
import statistics
from pathlib import Path

from predimrc_wrapper.predimrc_wrapper import FuselageGeometry
from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import StabGeometry
from predimrc_wrapper.predimrc_wrapper import WingGeometry

PROFILES = Path(__file__).resolve().parents[2] / "profiles"

wing = WingGeometry(
    root_chord=200.0,
    tip_chord=[200.0, 185.0, 140.0, 50.0],
    length=[285.0, 300.0, 180.0, 105.0],
    le_offset=[0.0, 7.0, 40.0, 150.0],
    twist=[0.0, 0.0, 0.0, 0.0],
    dihedral=[0.0, 1.0, 1.0, 20.0],
)
stab = StabGeometry(140.0, [100.0], [320.0], [170.0], 360.0, 0.0, "Biconvexe fin", "120", 20.0)
fus = FuselageGeometry(760.0, 85.0, 115.0, 270.0, "Profilée", "Normale", "médiane", "aile", 0.6, "Non profilé")
settings = Settings(mass=1920.0, static_margin=5.0, cz_reg=0.30)

times = []
with PredimRCWrapper(template_dir=PROFILES) as predimrc:
    for i in range(20):
        w = copy.deepcopy(wing)
        w.length[1] = 250.0 + 5.0 * i
        result = predimrc.run(w, stab, fus, settings)
        times.append(predimrc.last_eval_seconds)
        print(f"panel 2 = {w.length[1]:.0f} mm  S = {result.total_surface:.2f} dm²  "
              f"P_min = {result.power_required_w.min():.1f} W  t = {times[-1]:.3f} s")

print(f"mean {statistics.mean(times):.3f} s, max {max(times):.3f} s")
