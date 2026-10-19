"""CG entered versus the CG given by PredimRC for the static margin entered (no Streamlit)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from predimrc_wrapper.predimrc_wrapper import AeroResults

TOLERANCE_MAC = 0.02
"""Warning above this distance between both CGs, as a fraction of the MAC (2 points of static margin)."""


def cg_check(
    aero: AeroResults | None, cg_x_mm: float | None, static_margin_pct: float | None
) -> tuple[str, str]:
    """(level, text): level ``none`` (no PredimRC result), ``unset``, ``ok`` or ``warning``.

    PredimRC places the CG ahead of its neutral point by the static margin entered:
    x_CG = x_NP − SM·MAC. With the CG entered instead, the static margin would be
    SM' = (x_NP − x_CG,entered) / MAC.
    """
    if aero is None or not math.isfinite(getattr(aero, "cg_mm", math.nan)):
        return (
            "none",
            (
                "PredimRC gives the CG for the static margin entered with the wing: press Run to "
                "compare it with the CG entered."
            ),
        )
    mac = aero.mac_mm
    margin = "" if static_margin_pct is None else f" of {static_margin_pct:g} %"
    text = (
        f"PredimRC CG for the static margin{margin}: **{aero.cg_mm:.1f} mm** from the wing "
        f"root leading edge (neutral point {aero.neutral_point_mm:.1f} mm, MAC {mac:.1f} mm)."
    )
    if cg_x_mm is None:
        return (
            "unset",
            text + " No CG entered: the hover thrust is shared by disc area.",
        )
    delta = cg_x_mm - aero.cg_mm
    implied = 100.0 * (aero.neutral_point_mm - cg_x_mm) / mac
    if abs(delta) > TOLERANCE_MAC * mac:
        return (
            "warning",
            text + f" The CG entered ({cg_x_mm:g} mm) is {delta:+.1f} mm away "
            f"({100 * delta / mac:+.1f} % of the MAC): with it, the static margin would be "
            f"{implied:.1f} %. Check the CG (masses and their positions) or the static margin.",
        )
    return (
        "ok",
        text + f" The CG entered ({cg_x_mm:g} mm) agrees within {abs(delta):.1f} mm.",
    )
