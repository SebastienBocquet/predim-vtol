"""Drag coefficients of the PredimRC accessory shapes (``drag_shapes.yaml``, INC2-005/006)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.resources import files

import yaml


@dataclass(frozen=True)
class DragShape:
    """A shape label of PredimRC and its drag coefficient referred to the frontal area."""

    label: str
    cd: float
    source: str


@cache
def drag_shapes() -> dict[str, DragShape]:
    """The shapes by PredimRC label: "Profilé", "Mixte", "Non profilé"."""
    text = (
        files("predimrc_wrapper.data")
        .joinpath("drag_shapes.yaml")
        .read_text(encoding="utf-8")
    )
    return {
        d["label"]: DragShape(d["label"], float(d["cd"]), d["source"])
        for d in yaml.safe_load(text)
    }


def shape_cd(label: str) -> DragShape:
    """The shape of a label.

    Raises:
        KeyError: With the known labels.
    """
    shapes = drag_shapes()
    if label not in shapes:
        msg = f"Unknown drag shape '{label}'. Known: {list(shapes)}"
        raise KeyError(msg)
    return shapes[label]
