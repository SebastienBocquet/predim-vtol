"""Airfoil polars of the simple aerodynamic model (MIC-AERO-SIMPLE).

The shipped polars (``airfoils.yaml``) are computed by NeuralFoil, see
``tools/airfoil_polars.py``. A user file ``<user data>/airfoils.yaml`` with the same layout
adds airfoils or overrides shipped ones (same name). Per Reynolds number, a polar gives the
drag coefficient on a regular lift coefficient grid, up to the maximum lift coefficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import yaml

from predim_vtol.data.user import user_data_dir

SHIPPED = Path(__file__).with_name("airfoils.yaml")
USER_FILE = "airfoils.yaml"

REFERENCE_RE = 200_000
"""Reynolds number of the lift slope, zero-lift angle and pitching moment."""

LOW_RE_EXPONENT = 0.5
"""Drag scaling ``cd ∝ Re^-n`` below the lowest tabulated Reynolds number (laminar)."""

HIGH_RE_EXPONENT = 0.2
"""Drag scaling above the highest tabulated Reynolds number (turbulent)."""


@dataclass(frozen=True)
class Polar:
    """A polar at one Reynolds number."""

    re: float
    cl_max: float
    alpha0_deg: float
    cl_alpha: float
    """Lift slope (per rad)."""
    cm0: float
    cl: np.ndarray
    cd: np.ndarray

    def drag(self, cl: np.ndarray) -> np.ndarray:
        """Drag coefficient at lift coefficients, quadratic beyond the tabulated range."""
        cl = np.atleast_1d(np.asarray(cl, dtype=float))
        cd = np.interp(cl, self.cl, self.cd)
        for end, sign in ((0, -1.0), (-1, 1.0)):
            out = sign * (cl - self.cl[end]) > 0
            if not out.any():
                continue
            # Continuation of the parabola through the three end points (convex only).
            idx = slice(0, 3) if end == 0 else slice(-3, None)
            coeffs = np.polyfit(self.cl[idx], self.cd[idx], 2)
            slope = np.polyval(np.polyder(coeffs), self.cl[end])
            d = cl[out] - self.cl[end]
            cd[out] = self.cd[end] + slope * d + max(coeffs[0], 0.0) * d**2
        return cd


@dataclass(frozen=True)
class Airfoil:
    """An airfoil: polars at several Reynolds numbers."""

    name: str
    thickness: float
    polars: tuple[Polar, ...]

    @property
    def reference(self) -> Polar:
        """The polar closest to ``REFERENCE_RE``."""
        return min(self.polars, key=lambda p: abs(np.log(p.re / REFERENCE_RE)))

    @property
    def alpha0_deg(self) -> float:
        return self.reference.alpha0_deg

    @property
    def cl_alpha(self) -> float:
        return self.reference.cl_alpha

    @property
    def cm0(self) -> float:
        return self.reference.cm0

    def _bracket(self, re: float) -> tuple[Polar, Polar, float]:
        """The two polars around a Reynolds number and the weight of the second (log Re)."""
        res = np.array([p.re for p in self.polars])
        if re <= res[0]:
            return self.polars[0], self.polars[0], 0.0
        if re >= res[-1]:
            return self.polars[-1], self.polars[-1], 0.0
        i = int(np.searchsorted(res, re)) - 1
        w = np.log(re / res[i]) / np.log(res[i + 1] / res[i])
        return self.polars[i], self.polars[i + 1], float(w)

    def cl_max(self, re: float) -> float:
        """Maximum lift coefficient, interpolated in log Re (clamped outside the table)."""
        low, high, w = self._bracket(re)
        return (1.0 - w) * low.cl_max + w * high.cl_max

    def drag(self, cl: np.ndarray, re: np.ndarray | float) -> np.ndarray:
        """Section drag coefficient at lift coefficients and Reynolds numbers.

        Linear interpolation in log Re between the tabulated polars; outside the table, the
        nearest polar scaled by ``Re^-n`` (``LOW_RE_EXPONENT``, ``HIGH_RE_EXPONENT``).
        """
        cl = np.atleast_1d(np.asarray(cl, dtype=float))
        re = np.broadcast_to(np.asarray(re, dtype=float), cl.shape)
        log_res = np.log([p.re for p in self.polars])
        table = np.stack([p.drag(cl) for p in self.polars])
        log_re = np.clip(np.log(re), log_res[0], log_res[-1])
        i = np.clip(np.searchsorted(log_res, log_re) - 1, 0, max(len(log_res) - 2, 0))
        if len(log_res) == 1:
            cd = table[0]
        else:
            w = (log_re - log_res[i]) / (log_res[i + 1] - log_res[i])
            cols = np.arange(cl.size)
            cd = (1.0 - w) * table[i, cols] + w * table[i + 1, cols]
        low, high = self.polars[0].re, self.polars[-1].re
        cd = np.where(re < low, cd * (re / low) ** -LOW_RE_EXPONENT, cd)
        return np.where(re > high, cd * (re / high) ** -HIGH_RE_EXPONENT, cd)


def _parse(name: str, raw: dict) -> Airfoil:
    polars = tuple(
        sorted(
            (
                Polar(
                    re=float(p["re"]),
                    cl_max=float(p["cl_max"]),
                    alpha0_deg=float(p["alpha0_deg"]),
                    cl_alpha=float(p["cl_alpha"]),
                    cm0=float(p["cm0"]),
                    cl=np.asarray(p["cl"], dtype=float),
                    cd=np.asarray(p["cd"], dtype=float),
                )
                for p in raw["polars"]
            ),
            key=lambda p: p.re,
        )
    )
    for p in polars:
        if len(p.cl) < 3 or len(p.cl) != len(p.cd) or np.any(np.diff(p.cl) <= 0):
            msg = f"Airfoil {name}, Re {p.re:g}: cl must increase, with one cd per cl (≥ 3)."
            raise ValueError(msg)
    return Airfoil(name, float(raw.get("thickness", float("nan"))), polars)


def _load(path: Path) -> dict[str, dict[str, Airfoil]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        group: {name: _parse(name, a) for name, a in (raw.get(group) or {}).items()}
        for group in ("wing", "stab")
    }


@cache
def _shipped() -> dict[str, dict[str, Airfoil]]:
    return _load(SHIPPED)


def airfoils(group: str = "wing") -> dict[str, Airfoil]:
    """The airfoils of a group (``wing`` or ``stab``): shipped, then the user ones."""
    out = dict(_shipped()[group])
    user = user_data_dir() / USER_FILE
    if user.is_file():
        out.update(_load(user)[group])
    return out


def airfoil(name: str, group: str = "wing") -> Airfoil:
    """An airfoil by name, case-insensitive.

    Raises:
        KeyError: With the available names when the airfoil is unknown.
    """
    known = airfoils(group)
    by_key = {k.casefold(): a for k, a in known.items()}
    if name.casefold() not in by_key:
        msg = (
            f"Unknown {group} airfoil '{name}'. Available: {sorted(known)} "
            f"(add yours in {user_data_dir() / USER_FILE})."
        )
        raise KeyError(msg)
    return by_key[name.casefold()]
