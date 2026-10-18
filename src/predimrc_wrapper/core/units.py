"""Unit conversions used at the project, PredimRC and GUI boundaries."""

MM = 1e-3
"""One millimetre in metres."""

G = 1e-3
"""One gram in kilograms."""

DM2 = 1e-2
"""One square decimetre in square metres."""

INCH = 0.0254
"""One inch in metres."""

MAH = 1e-3
"""One milliampere-hour in ampere-hours."""

KMH = 1 / 3.6
"""One kilometre per hour in metres per second."""

GRAVITY = 9.81
"""Standard gravity (m/s²), the value used by PredimRC."""


def mm_to_m(value: float) -> float:
    """Convert millimetres to metres."""
    return value * MM


def g_to_kg(value: float) -> float:
    """Convert grams to kilograms."""
    return value * G


def dm2_to_m2(value: float) -> float:
    """Convert square decimetres to square metres."""
    return value * DM2


def in_to_m(value: float) -> float:
    """Convert inches to metres."""
    return value * INCH


def mah_to_ah(value: float) -> float:
    """Convert milliampere-hours to ampere-hours."""
    return value * MAH


def kmh_to_ms(value: float) -> float:
    """Convert km/h to m/s."""
    return value * KMH
