"""Display units of the GUI (REQ-NFR-002): thrust in N with kg alongside, speeds in km/h.

SI inside; these helpers are used only where a value is shown or entered.
"""

from __future__ import annotations

import math

from predimrc_wrapper.core.units import GRAVITY

KMH_PER_M_S = 3.6


def kg(thrust_n: float) -> float:
    """Mass whose weight equals the thrust (kgf)."""
    return thrust_n / GRAVITY


def thrust_text(thrust_n: float | None, digits: int = 2) -> str:
    """``"12.30 N (1.25 kg)"``, or "—" when not finite."""
    if thrust_n is None or not math.isfinite(thrust_n):
        return "—"
    return f"{thrust_n:.{digits}f} N ({kg(thrust_n):.{max(digits, 2)}f} kg)"


def kmh(v_m_s: float | None) -> float | None:
    """Speed in km/h (None or NaN kept)."""
    if v_m_s is None:
        return None
    return KMH_PER_M_S * v_m_s


def m_s(v_kmh: float) -> float:
    """Speed entered in km/h, stored in m/s."""
    return v_kmh / KMH_PER_M_S


def speed_text(v_m_s: float | None, digits: int = 0) -> str:
    """``"54 km/h"``, or "—" when not finite."""
    if v_m_s is None or not math.isfinite(v_m_s):
        return "—"
    return f"{kmh(v_m_s):.{digits}f} km/h"
