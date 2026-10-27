"""Drag coefficients of boom sections (``boom_sections.yaml``), with their source."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.resources import files

import numpy as np
import yaml


@dataclass(frozen=True)
class BoomSection:
    """A boom cross-section."""

    name: str
    label: str
    cd: float
    """Drag coefficient of a member normal to the flow, referred to its frontal area t·L."""
    source: str

    def perimeter_and_area(
        self, thickness_m: float, chord_m: float
    ) -> tuple[float, float]:
        """Wetted perimeter and cross-section area (m, m²); chord used by the profiled section."""
        t = thickness_m
        if self.name == "round":
            return np.pi * t, np.pi * t**2 / 4.0
        if self.name == "square":
            return 4.0 * t, t**2
        # Profiled: symmetric airfoil of thickness t and chord c (perimeter ≈ 2.04 c, area ≈ 0.685 t c).
        return 2.04 * chord_m, 0.685 * t * chord_m


@cache
def boom_sections() -> dict[str, BoomSection]:
    """The sections by name."""
    data = yaml.safe_load(
        files("predimrc_wrapper.data")
        .joinpath("boom_sections.yaml")
        .read_text(encoding="utf-8")
    )
    return {
        name: BoomSection(name, d["label"], float(d["cd"]), d["source"])
        for name, d in data["sections"].items()
    }


def boom_section(name: str) -> BoomSection:
    """One section; unknown names rejected with the known ones."""
    sections = boom_sections()
    if name not in sections:
        msg = f"Unknown boom section '{name}'. Known: {list(sections)}"
        raise KeyError(msg)
    return sections[name]
