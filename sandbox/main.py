"""Evaluate the reference case tricoptere_short_2 with PredimRC (visible Excel)."""

from predimrc_wrapper import SRC_DIR
from predimrc_wrapper.predimrc_wrapper import FuselageGeometry
from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import StabGeometry
from predimrc_wrapper.predimrc_wrapper import WingGeometry

with PredimRCWrapper(
    profile="SD7003", template_dir=SRC_DIR / "../../profiles", visible=True
) as w:
    result = w.run(
        WingGeometry(
            root_chord=200.0,
            tip_chord=[200.0, 185.0, 140.0, 50.0],
            length=[285.0, 300.0, 180.0, 105.0],
            le_offset=[0.0, 7.0, 40.0, 150.0],
            twist=[0.0, 0.0, 0.0, 0.0],
            dihedral=[0.0, 1.0, 1.0, 20.0],
        ),
        StabGeometry(
            root_chord=140.0,
            tip_chord=[100.0],
            length=[320.0],
            le_offset=[170.0],
            lever=360.0,
            stab_height=0.0,
            profile="Biconvexe fin",
            opening="120",
            lateral_gap=20.0,
        ),
        FuselageGeometry(
            length=760.0,
            width=85.0,
            height=115.0,
            nose_lever=270.0,
            shape="Profilée",
            beam="Normale",
            wing_pos="médiane",
            incidence="aile",
            accessory_surface=0.6,
            accessory_shape="Non profilé",
        ),
        Settings(mass=1920.0, static_margin=5.0, cz_reg=0.30),
    )
    print(result)
    print(f"evaluation: {w.last_eval_seconds:.3f} s")
