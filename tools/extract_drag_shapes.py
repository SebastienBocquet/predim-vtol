"""One-off extraction of the PredimRC accessory shape drag coefficients (INC2-005, step 7).

For each accessory shape label (Calculs1!D169:D171), evaluate the reference case with a
known accessory surface S_acc, read Calculs1!AD3 (Cx acc., referred to the wing area
S_ref = 3-Geometrie!L5) and record C_d = Cx_acc · S_ref / S_acc into
``src/predimrc_wrapper/data/drag_shapes.yaml``. The workbook is opened read-only and never
saved. Usage: ``python tools/extract_drag_shapes.py [profiles_dir]``.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

import yaml

from predimrc_wrapper.predimrc_wrapper import FuselageGeometry
from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import StabGeometry
from predimrc_wrapper.predimrc_wrapper import WingGeometry

OUT = Path(__file__).resolve().parents[1] / "src" / "predimrc_wrapper" / "data" / "drag_shapes.yaml"
S_ACC_DM2 = 1.0


def main(profiles: Path) -> None:
    wing = WingGeometry(200.0, [200.0, 185.0, 140.0, 50.0], [285.0, 300.0, 180.0, 105.0], [0.0, 7.0, 40.0, 150.0],
                        [0.0] * 4, [0.0, 1.0, 1.0, 20.0])
    stab = StabGeometry(140.0, [100.0], [320.0], [170.0], 360.0, 0.0, "Biconvexe fin", "120", 20.0)
    settings = Settings(mass=1870.0, static_margin=5.0, cz_reg=0.30)
    with PredimRCWrapper(profile="SD7003", template_dir=profiles) as w:
        workbook = w.template_path
        shapes = []
        for label in w.labels("fuselage.accessory_shape"):
            fus = FuselageGeometry(760.0, 85.0, 115.0, 270.0, "Profilée", "Normale", "médiane", "aile", S_ACC_DM2, label)
            w.run(wing, stab, fus, settings)
            cx_acc = float(w._calc["AD3"].value)  # noqa: SLF001
            s_ref = float(w._geom["L5"].value)  # noqa: SLF001
            shapes.append({"label": label, "cd": round(cx_acc * s_ref / S_ACC_DM2, 6),
                           "source": f"{workbook.name} Calculs1!AD3 with S_acc = {S_ACC_DM2} dm², S_ref = {s_ref:.2f} dm²"})
            print(label, shapes[-1]["cd"])
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()[:16]
    header = ("# Drag coefficients of the PredimRC accessory shapes, referred to the frontal area\n"
              f"# (extracted by tools/extract_drag_shapes.py on {date.today()}, workbook sha256 {digest}).\n")
    OUT.write_text(header + yaml.safe_dump(shapes, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("profiles"))
