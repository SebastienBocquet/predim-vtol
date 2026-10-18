"""Motor layout presets: lists of ``MotorSlot`` data (x aft-positive, y right, mm).

Numbering follows the list order, like the ArduPilot motor outputs; one motor per arm or
boom end (no coaxial pairs).
"""

from __future__ import annotations

import numpy as np


def _slot(unit: str, role: str, x: float, y: float) -> dict:
    return {
        "unit": unit,
        "role": role,
        "x_mm": round(float(x), 1),
        "y_mm": round(float(y), 1),
    }


def multirotor(n: int, arm_mm: float, unit: str = "lift") -> list[dict]:
    """N arms evenly spread, X orientation (no arm on the forward axis)."""
    angles = (
        np.pi / n + 2 * np.pi * np.arange(n) / n
    )  # from the nose, clockwise seen from above
    return [
        _slot(unit, "lift", -arm_mm * np.cos(a), arm_mm * np.sin(a)) for a in angles
    ]


def tricopter(
    front_arm_mm: float,
    rear_arm_mm: float,
    front_unit: str = "front",
    rear_unit: str = "rear",
    front_angle_deg: float = 60.0,
) -> list[dict]:
    """Two front arms at ±``front_angle_deg`` from the nose, one rear arm on the centreline."""
    a = np.radians(front_angle_deg)
    return [
        _slot(front_unit, "lift", -front_arm_mm * np.cos(a), front_arm_mm * np.sin(a)),
        _slot(front_unit, "lift", -front_arm_mm * np.cos(a), -front_arm_mm * np.sin(a)),
        _slot(rear_unit, "lift", rear_arm_mm, 0.0),
    ]


def quadplane(
    boom_span_mm: float,
    x_front_mm: float,
    x_rear_mm: float,
    x_pusher_mm: float,
    per_boom: int = 2,
    lift_unit: str = "lift",
    cruise_unit: str = "cruise",
) -> list[dict]:
    """Two booms of ``per_boom`` lift motors, plus one cruise motor on the centreline (4+1)."""
    xs = np.linspace(x_front_mm, x_rear_mm, per_boom) if per_boom > 1 else [x_front_mm]
    motors = [
        _slot(lift_unit, "lift", x, s * boom_span_mm / 2) for s in (1, -1) for x in xs
    ]
    return [*motors, _slot(cruise_unit, "cruise", x_pusher_mm, 0.0)]


def tiltrotor(
    span_mm: float,
    x_front_mm: float,
    x_rear_mm: float,
    tilt_unit: str = "tilt",
    rear_unit: str = "rear",
) -> list[dict]:
    """Two tilting front motors (lift and cruise) and one rear lift motor on the centreline."""
    return [
        _slot(tilt_unit, "tilt", x_front_mm, span_mm / 2),
        _slot(tilt_unit, "tilt", x_front_mm, -span_mm / 2),
        _slot(rear_unit, "lift", x_rear_mm, 0.0),
    ]


def presets_for(architecture: str, n_lift: int) -> dict:
    """Layout generators matching a configuration: a tricopter only offers the tricopter layout, etc."""
    if architecture == "quadplane":
        return {
            "quadplane 4+1 (two booms + pusher)": quadplane,
            "tricopter with wing (2 tilting front + 1 rear)": tiltrotor,
        }
    if n_lift == 3:
        return {"tricopter (2 front arms + 1 rear arm)": tricopter}
    return {"multirotor X (N evenly spread arms)": multirotor}


PRESETS = {
    "multirotor": multirotor,
    "tricopter": tricopter,
    "quadplane": quadplane,
    "tiltrotor": tiltrotor,
}
"""Layout functions offered by the GUI."""
