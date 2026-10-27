"""Propeller, momentum theory with figure of merit (MIC-PROP-PRP, MVP variant)."""

from __future__ import annotations

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports

_EXAMPLE = {"diameter_m": 0.381, "mass_kg": 0.025}


def _ideal_power(model: MomentumPropeller) -> bool:
    ideal = MomentumPropeller(**{**_EXAMPLE, "figure_of_merit": 1.0})
    t, rho = 10.0, 1.225
    area = np.pi * _EXAMPLE["diameter_m"] ** 2 / 4.0
    expected = t**1.5 / np.sqrt(2.0 * rho * area)
    got = float(
        ideal.evaluate({"thrust_n": t, "v_m_s": 0.0, "rho": rho})["shaft_power_w"]
    )
    return abs(got - expected) <= 1e-9 * expected


def _diameter_law(model: MomentumPropeller) -> bool:
    x = {"thrust_n": 10.0, "v_m_s": 0.0, "rho": 1.225}
    p1 = float(
        MomentumPropeller(diameter_m=0.3, mass_kg=0.02).evaluate(x)["shaft_power_w"]
    )
    p2 = float(
        MomentumPropeller(diameter_m=0.6, mass_kg=0.02).evaluate(x)["shaft_power_w"]
    )
    return abs(p1 / p2 - 2.0) <= 1e-9


class MomentumPropeller(Model):
    """Fixed-pitch propeller in axial flow.

    Hover: A = πD²/4; P = T^1.5 / (FM·√(2ρA)); n = √(T / (CT₀·ρ·D⁴)).
    Cruise (V > 0): P = T·V / η_c, n from the hover formula. Q = P / (2πn).
    """

    mic_id = "MIC-PROP-PRP"
    inputs = ports(
        Port("thrust_n", "T", "N", "required thrust", (0, None)),
        Port("v_m_s", "V", "m/s", "axial inflow speed (0 in hover)", (0, None)),
        Port("rho", "ρ", "kg/m³", "air density", (0, None)),
    )
    outputs = ports(
        Port("n_rev_s", "n", "rev/s", "rotation speed", (0, None)),
        Port("shaft_power_w", "P", "W", "shaft power", (0, None)),
        Port("torque_nm", "Q", "N·m", "P / (2πn)", (0, None)),
    )
    parameters = params(
        Param(
            "diameter_m",
            "D",
            "m",
            "propeller diameter",
            origin="project (inches)",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "mass_kg",
            "m_p",
            "kg",
            "propeller mass",
            origin="project",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "figure_of_merit",
            "FM",
            "—",
            "hover figure of merit",
            default=0.65,
            bounds=(0, 1),
            source="RC propeller literature",
        ),
        Param(
            "static_ct",
            "CT₀",
            "—",
            "static thrust coefficient (speed estimate)",
            default=0.10,
            bounds=(0, None),
            source="generic",
        ),
        Param(
            "cruise_efficiency",
            "η_c",
            "—",
            "propulsive efficiency in cruise",
            default=0.70,
            bounds=(0, 1),
            source="generic",
        ),
    )
    expected_forms = [
        ScalingLaw(
            "shaft_power_w",
            "thrust_n",
            1.5,
            fixed={"v_m_s": 0.0, "rho": 1.225},
            params=_EXAMPLE,
        ),
        ScalingLaw(
            "shaft_power_w",
            "rho",
            -0.5,
            fixed={"v_m_s": 0.0, "thrust_n": 10.0},
            lower=0.8,
            upper=1.3,
            params=_EXAMPLE,
        ),
        Invariant("FM = 1 ⇒ ideal momentum power", _ideal_power, params=_EXAMPLE),
        Invariant("hover power ∝ 1/D at fixed thrust", _diameter_law, params=_EXAMPLE),
    ]

    @property
    def disc_area_m2(self) -> float:
        """Disc area πD²/4 (m²)."""
        return np.pi * self.p.diameter_m**2 / 4.0

    def evaluate(self, x):
        t = np.asarray(x["thrust_n"], dtype=float)
        v = np.asarray(x.get("v_m_s", 0.0), dtype=float)
        rho = np.asarray(x["rho"], dtype=float)
        d = self.p.diameter_m
        n = np.sqrt(t / (self.p.static_ct * rho * d**4))
        hover = t**1.5 / (
            self.p.figure_of_merit * np.sqrt(2.0 * rho * self.disc_area_m2)
        )
        power = np.where(v > 0.0, t * v / self.p.cruise_efficiency, hover)
        with np.errstate(divide="ignore", invalid="ignore"):
            torque = np.where(n > 0.0, power / (2.0 * np.pi * n), 0.0)
        return {"n_rev_s": n, "shaft_power_w": power, "torque_nm": torque}


_BEM_EXAMPLE = {"diameter_m": 0.254, "pitch_m": 0.1143}
_HALVINGS = 12
"""Halvings of n_max bracketing the rotation speed (n_max / 4096 ≈ 0 for an RC propeller)."""


def _bracketed_root(f, lo, hi, f_lo, f_hi, xtol, max_iter: int = 100) -> np.ndarray:
    """Root of ``f`` in [lo, hi] where ``f_lo`` and ``f_hi`` have opposite signs, vectorised.

    Regula falsi with the Illinois modification: the root stays bracketed as with a
    bisection, but the convergence is superlinear (a few iterations instead of ~50).
    Elements without a sign change are returned at an end of their interval.
    """
    lo, hi, f_lo, f_hi = (
        np.array(a, dtype=float) for a in np.broadcast_arrays(lo, hi, f_lo, f_hi)
    )
    side = np.zeros(lo.shape, dtype=np.int8)
    x = 0.5 * (lo + hi)
    for _ in range(max_iter):
        denom = f_hi - f_lo
        with np.errstate(divide="ignore", invalid="ignore"):
            secant = (lo * f_hi - hi * f_lo) / denom
        new = np.where(np.isfinite(secant), secant, 0.5 * (lo + hi))
        new = np.clip(new, np.minimum(lo, hi), np.maximum(lo, hi))
        done = np.max(np.abs(new - x), initial=0.0) <= xtol
        x = new
        if done:
            break
        fx = f(x)
        same = np.sign(fx) == np.sign(f_lo)
        lo, f_lo = np.where(same, x, lo), np.where(same, fx, f_lo)
        hi, f_hi = np.where(same, hi, x), np.where(same, f_hi, fx)
        # Illinois: the end kept twice in a row has its value halved.
        f_hi = np.where(same & (side == 1), 0.5 * f_hi, f_hi)
        f_lo = np.where(~same & (side == -1), 0.5 * f_lo, f_lo)
        side = np.where(same, np.int8(1), np.int8(-1))
    return x


def _static_coefficients(model: BladeElementPropeller) -> bool:
    y = model.evaluate({"n_rev_s": 100.0, "v_m_s": 0.0, "rho": 1.225})
    return 0.07 < float(y["ct"]) < 0.15 and 0.025 < float(y["cp"]) < 0.08


def _zero_thrust_near_pitch_speed(model: BladeElementPropeller) -> bool:
    """Thrust vanishes between 0.9 and 1.6 times the pitch speed n·P (cambered blades: beyond n·P)."""
    n = 100.0
    v = n * model.p.pitch_m * np.array([0.9, 1.6])
    t = model.evaluate({"n_rev_s": n, "v_m_s": v, "rho": 1.225})["thrust_n"]
    return bool(t[0] > 0.0 > t[1])


class BladeElementPropeller(Model):
    """Fixed-pitch propeller, blade elements with momentum inflow (axial flow).

    Stations r ∈ [r_h, R]: θ = atan(P / 2πr); φ = atan((V + v_i) / ωr); α = θ − φ;
    c_l = clip(a·(α − α₀), c_l,min, c_l,max); c_d = c_d0 + k·c_l² + c_d,s·Δα_stall; local induced velocity
    v_i from ½ρW²Bc(c_l·cos φ − c_d·sin φ) = 4πρr(V + v_i)·v_i·F (Prandtl tip loss F);
    T = ∫dT, Q = ∫½ρW²Bc(c_l·sin φ + c_d·cos φ)·r dr, P = Q·ω, η = T·V / P.
    Chord c/R = c₇₅·(1 + s·(0.75 − r/R)). A generic RC propeller, to calibrate on data.
    """

    mic_id = "MIC-PROP-BEM"
    inputs = ports(
        Port("n_rev_s", "n", "rev/s", "rotation speed", (0, None)),
        Port("v_m_s", "V", "m/s", "axial inflow speed", (0, None)),
        Port("rho", "ρ", "kg/m³", "air density", (0, None)),
    )
    outputs = ports(
        Port("thrust_n", "T", "N", "thrust (negative when windmilling)"),
        Port("shaft_power_w", "P", "W", "shaft power"),
        Port("torque_nm", "Q", "N·m", "shaft torque"),
        Port("ct", "C_T", "—", "T / (ρn²D⁴)"),
        Port("cp", "C_P", "—", "P / (ρn³D⁵)"),
        Port("efficiency", "η", "—", "T·V / P (0 in hover)"),
    )
    parameters = params(
        Param(
            "diameter_m",
            "D",
            "m",
            "propeller diameter",
            origin="project (inches)",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "pitch_m",
            "P",
            "m",
            "geometric pitch (constant along the blade)",
            origin="project (inches)",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "n_blades",
            "B",
            "—",
            "number of blades",
            default=2,
            bounds=(1, 8),
            source="project",
        ),
        Param(
            "chord_ratio_75",
            "c₇₅",
            "—",
            "chord / radius at 0.75 R",
            default=0.14,
            bounds=(0, 1),
            source="typical RC propellers",
        ),
        Param(
            "chord_slope",
            "s",
            "—",
            "chord taper: c/R = c₇₅·(1 + s·(0.75 − r/R))",
            default=1.0,
            bounds=(0, None),
            source="typical RC propellers",
        ),
        Param(
            "hub_ratio",
            "r_h/R",
            "—",
            "hub radius / radius",
            default=0.15,
            bounds=(0, 1),
            source="generic",
        ),
        Param(
            "cl_alpha",
            "a",
            "1/rad",
            "section lift slope (low Reynolds)",
            default=5.7,
            bounds=(0, None),
            source="thin aerofoil, Reynolds-reduced",
        ),
        Param(
            "alpha_zero_lift",
            "α₀",
            "rad",
            "zero-lift angle (cambered section)",
            default=-0.10,
            source="set to match UIUC APC 10x4.7SF static data",
        ),
        Param(
            "cl_max",
            "c_l,max",
            "—",
            "section stall lift coefficient",
            default=1.1,
            source="low-Reynolds aerofoils",
        ),
        Param(
            "cl_min",
            "c_l,min",
            "—",
            "section negative stall lift coefficient",
            default=-0.5,
            source="low-Reynolds aerofoils",
        ),
        Param(
            "cd0",
            "c_d0",
            "—",
            "section profile drag at zero lift",
            default=0.025,
            bounds=(0, None),
            source="low-Reynolds aerofoils",
        ),
        Param(
            "cd_k",
            "k",
            "—",
            "section drag rise with c_l²",
            default=0.02,
            bounds=(0, None),
            source="low-Reynolds aerofoils",
        ),
        Param(
            "cd_stall",
            "c_d,s",
            "1/rad",
            "drag rise per radian beyond stall",
            default=0.5,
            bounds=(0, None),
            source="fitted on the 8 shipped manufacturer thrust tables (2026-10-14)",
        ),
        Param(
            "n_stations",
            "N_r",
            "—",
            "number of radial stations",
            default=24,
            bounds=(4, None),
            source="numerical",
        ),
    )
    expected_forms = [
        ScalingLaw(
            "thrust_n",
            "n_rev_s",
            2.0,
            fixed={"v_m_s": 0.0, "rho": 1.225},
            lower=30.0,
            upper=200.0,
            tol=1e-6,
            params=_BEM_EXAMPLE,
        ),
        ScalingLaw(
            "shaft_power_w",
            "rho",
            1.0,
            fixed={"v_m_s": 0.0, "n_rev_s": 100.0},
            lower=0.8,
            upper=1.3,
            tol=1e-6,
            params=_BEM_EXAMPLE,
        ),
        Invariant(
            "static C_T and C_P of a 10x4.5 in the RC range",
            _static_coefficients,
            params=_BEM_EXAMPLE,
        ),
        Invariant(
            "zero thrust near the pitch speed n·P",
            _zero_thrust_near_pitch_speed,
            params=_BEM_EXAMPLE,
        ),
    ]

    def _sections(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        radius = self.p.diameter_m / 2.0
        edges = np.linspace(self.p.hub_ratio, 1.0, int(self.p.n_stations) + 1)
        x = 0.5 * (edges[1:] + edges[:-1])
        chord = radius * self.p.chord_ratio_75 * (1.0 + self.p.chord_slope * (0.75 - x))
        return x * radius, np.diff(edges) * radius, np.clip(chord, 0.0, None)

    def evaluate(self, x):
        n = np.asarray(x["n_rev_s"], dtype=float)
        v = np.asarray(x.get("v_m_s", 0.0), dtype=float)
        rho = np.asarray(x["rho"], dtype=float)
        n, v, rho = np.broadcast_arrays(n, v, rho)
        r, dr, c = self._sections()
        radius, b = self.p.diameter_m / 2.0, self.p.n_blades
        omega = (2.0 * np.pi * n)[..., None]
        vv, rr = v[..., None], rho[..., None]
        theta = np.arctan(self.p.pitch_m / (2.0 * np.pi * r))

        def loads(vi):
            axial = vv + vi
            tangential = omega * r
            phi = np.arctan2(axial, tangential)
            linear = self.p.cl_alpha * (theta - phi - self.p.alpha_zero_lift)
            cl = np.clip(linear, self.p.cl_min, self.p.cl_max)
            beyond = np.abs(linear - cl) / self.p.cl_alpha
            cd = self.p.cd0 + self.p.cd_k * cl**2 + self.p.cd_stall * beyond
            q = 0.5 * rr * (axial**2 + tangential**2) * b * c
            d_thrust = q * (cl * np.cos(phi) - cd * np.sin(phi))
            d_torque = q * (cl * np.sin(phi) + cd * np.cos(phi)) * r
            f = b / 2.0 * (radius - r) / np.maximum(r * np.abs(np.sin(phi)), 1e-9)
            tip = 2.0 / np.pi * np.arccos(np.clip(np.exp(-f), 0.0, 1.0))
            d_momentum = 4.0 * np.pi * rr * r * axial * vi * np.maximum(tip, 1e-3)
            return d_thrust, d_torque, d_momentum

        def excess(vi):
            dt, _, dm = loads(vi)
            return dt - dm

        zero = np.zeros(omega.shape[:-1] + r.shape)
        t0, _, _ = loads(zero)
        hi = np.broadcast_to(omega * radius + np.abs(vv) + 1.0, zero.shape)
        # Induced velocity where the blade-element thrust equals the momentum thrust.
        vi = _bracketed_root(
            excess,
            zero,
            hi,
            t0,
            excess(hi),
            xtol=1e-12 * max(float(hi.max(initial=1.0)), 1.0),
        )
        vi = np.where(t0 > 0.0, vi, 0.0)
        dt, dq, _ = loads(vi)
        thrust = np.sum(dt * dr, axis=-1)
        torque = np.sum(dq * dr, axis=-1)
        power = torque * omega[..., 0]
        d = self.p.diameter_m
        with np.errstate(divide="ignore", invalid="ignore"):
            ct = np.where(n > 0, thrust / (rho * n**2 * d**4), 0.0)
            cp = np.where(n > 0, power / (rho * n**3 * d**5), 0.0)
            eta = np.where((v > 0) & (power > 0), thrust * v / power, 0.0)
        return {
            "thrust_n": thrust,
            "shaft_power_w": power,
            "torque_nm": torque,
            "ct": ct,
            "cp": cp,
            "efficiency": eta,
        }

    def n_for_thrust(
        self, thrust_n, v_m_s, rho: float, n_max: float = 600.0
    ) -> np.ndarray:
        """Rotation speed (rev/s) giving a thrust at a speed (NaN above ``n_max``).

        Propulsive branch: the upper bound n_max is halved while the thrust stays above the
        target (at most ``_HALVINGS`` times), then the root is refined in the bracket by a
        regula falsi (Illinois). In forward flight the thrust dips below its n = 0 value
        (windmilling) before rising; this keeps the rising branch, as the former bisection.
        A target already reached below n_max / 2^_HALVINGS and at n = 0 gives 0.
        """
        t, v = np.broadcast_arrays(
            np.asarray(thrust_n, dtype=float), np.asarray(v_m_s, dtype=float)
        )

        def excess(n):
            return self.evaluate({"n_rev_s": n, "v_m_s": v, "rho": rho})["thrust_n"] - t

        hi = np.full(t.shape, float(n_max))
        f_hi = excess(hi)
        reachable = f_hi >= 0.0
        lo, f_lo = hi.copy(), f_hi.copy()
        open_ = reachable.copy()  # no point below the target found yet
        for _ in range(_HALVINGS):
            if not open_.any():
                break
            mid = np.where(open_, 0.5 * lo, lo)
            f_mid = excess(mid)
            below = open_ & (f_mid < 0.0)
            still = open_ & ~below
            hi, f_hi = np.where(still, mid, hi), np.where(still, f_mid, f_hi)
            lo, f_lo = np.where(open_, mid, lo), np.where(open_, f_mid, f_lo)
            open_ = still
        if open_.any():
            zero = np.zeros(t.shape)
            f_zero = excess(zero)
            lo, f_lo = np.where(open_, zero, lo), np.where(open_, f_zero, f_lo)
            at_zero = open_ & (f_zero >= 0.0)
        else:
            at_zero = np.zeros(t.shape, dtype=bool)
        n = _bracketed_root(excess, lo, hi, f_lo, f_hi, xtol=1e-12 * n_max)
        n = np.where(at_zero, 0.0, n)
        return np.where(reachable, n, np.nan)
