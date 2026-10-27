"""Thrust–power surrogate: physics model × Gaussian-process correction (MIC-PROP-SUR).

The physics mean of a motor + propeller pair at a static thrust T: blade-element
propeller (MIC-PROP-BEM) for the rotation speed and the shaft power, motor constants
(MIC-PROP-MOT) for the current and the electric power, divided by the ESC efficiency when
the data were measured at the ESC input. A Gaussian process fitted on the test data
corrects the log ratios r = ln(data / physics) of power, current and rpm, with inputs
x = (ln T, D, P/D, ln Kv, ln U). Predictions: P = P_phys·exp(μ_r), relative standard
deviation σ_r, 95 % interval P·exp(±1.96 σ_r).
"""

from __future__ import annotations

import hashlib
import operator
import warnings
from dataclasses import dataclass
from dataclasses import field
from functools import cache

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel
from sklearn.gaussian_process.kernels import Matern
from sklearn.gaussian_process.kernels import WhiteKernel

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.core.units import INCH
from predimrc_wrapper.data import MotorDatabase
from predimrc_wrapper.data import PropellerDatabase
from predimrc_wrapper.data import TestDatabase
from predimrc_wrapper.data import default_database
from predimrc_wrapper.data import default_propellers
from predimrc_wrapper.data import default_tests
from predimrc_wrapper.propulsion.motor import MotorModel
from predimrc_wrapper.propulsion.propeller import BladeElementPropeller

TEST_RHO = 1.225
"""Air density assumed for the manufacturer tests (not published), kg/m³."""

ESC_EFFICIENCY = 0.95
"""Constant ESC efficiency of the MVP, used for data measured at the ESC input."""

OUTPUTS = ("power_w", "current_a", "rpm")


@dataclass(frozen=True)
class Pair:
    """A motor + propeller pair, with the constants the physics mean needs."""

    motor_id: str
    propeller_id: str
    kv: float
    r_m: float
    i0: float
    p_max: float
    diameter_m: float
    pitch_m: float

    @classmethod
    def of(
        cls,
        motor_id: str,
        propeller_id: str,
        motors: MotorDatabase | None = None,
        propellers: PropellerDatabase | None = None,
    ) -> Pair:
        m = (motors or default_database()).motor(motor_id)
        p = (propellers or default_propellers()).propeller(propeller_id)
        return cls(
            motor_id,
            propeller_id,
            m.kv,
            m.r_m,
            m.i0,
            m.p_max,
            p.diameter_in * INCH,
            p.pitch_in * INCH,
        )

    @classmethod
    def custom(
        cls,
        motor_id: str,
        diameter_in: float,
        pitch_in: float,
        motors: MotorDatabase | None = None,
    ) -> Pair:
        """A pair whose propeller is not in the database (given by diameter and pitch)."""
        m = (motors or default_database()).motor(motor_id)
        return cls(
            motor_id,
            f"{diameter_in:g}x{pitch_in:g}",
            m.kv,
            m.r_m,
            m.i0,
            m.p_max,
            diameter_in * INCH,
            pitch_in * INCH,
        )


def physics_mean(
    pair: Pair, thrust_n, voltage_v, rho: float = TEST_RHO, esc_input: bool = False
) -> dict[str, np.ndarray]:
    """Static electric power (W), supply current (A) and rpm of a pair at a thrust (physics only).

    The current is the DC current drawn at the supply voltage, I = P / U, as in the
    manufacturer tables (power = voltage × current).
    """
    bem = BladeElementPropeller(diameter_m=pair.diameter_m, pitch_m=pair.pitch_m)
    t = np.asarray(thrust_n, dtype=float)
    n = bem.n_for_thrust(t, 0.0, rho, n_max=1500.0)
    y = bem.evaluate({"n_rev_s": np.nan_to_num(n, nan=1.0), "v_m_s": 0.0, "rho": rho})
    omega = 2.0 * np.pi * np.nan_to_num(n, nan=1.0)
    motor = MotorModel(
        kv=pair.kv, r_m=pair.r_m, i0=pair.i0, i_max=1e9, p_max=1e9, mass_kg=0.0
    )
    mot = motor.evaluate({
        "torque_nm": y["shaft_power_w"] / omega,
        "omega_rad_s": omega,
    })
    power = mot["power_elec_w"] / (ESC_EFFICIENCY if esc_input else 1.0)
    bad = ~np.isfinite(n)
    return {
        "power_w": np.where(bad, np.nan, power),
        "current_a": np.where(bad, np.nan, power / np.asarray(voltage_v, dtype=float)),
        "rpm": np.where(bad, np.nan, 60.0 * n),
    }


def features(pair: Pair, thrust_n, voltage_v) -> np.ndarray:
    """GP inputs (ln T, D, P/D, ln Kv, ln U), one row per point."""
    t, u = np.broadcast_arrays(
        np.asarray(thrust_n, dtype=float), np.asarray(voltage_v, dtype=float)
    )
    ones = np.ones_like(t)
    return np.column_stack([
        np.log(t),
        pair.diameter_m * ones,
        pair.pitch_m / pair.diameter_m * ones,
        np.log(pair.kv) * ones,
        np.log(u),
    ])


@dataclass
class Prediction:
    """Surrogate prediction at one or several thrusts (arrays)."""

    power_w: np.ndarray
    power_sd: np.ndarray
    current_a: np.ndarray
    current_sd: np.ndarray
    rpm: np.ndarray
    rpm_sd: np.ndarray
    sd_rel: np.ndarray
    """Relative standard deviation of the power (σ of ln P)."""
    trusted: np.ndarray
    reason: np.ndarray
    source: str
    """``tested_pair``, ``untested_pair`` or ``physics_only``."""
    physics_power_w: np.ndarray

    def interval95(self) -> tuple[np.ndarray, np.ndarray]:
        """95 % interval of the power (W)."""
        return self.power_w * np.exp(-1.96 * self.sd_rel), self.power_w * np.exp(
            1.96 * self.sd_rel
        )


@dataclass
class ValidationReport:
    """Error guarantee of the surrogate on its data (REQ-PROP-011, REQ-NFR-005)."""

    n_points: int
    n_pairs: int
    loo_mean_rel_err: float
    loo_max_rel_err: float
    loo_coverage_95: float
    lopo_mean_rel_err: float
    lopo_max_rel_err: float
    lopo_coverage_95: float
    physics_mean_rel_err: float
    data_hash: str
    per_pair: dict[str, dict[str, float]] = field(default_factory=dict)

    def passed(self) -> bool:
        """Thresholds of INC2-003: LOO mean error ≤ 3 %, LOO coverage in [90 %, 99 %]."""
        return self.loo_mean_rel_err <= 0.03 and 0.90 <= self.loo_coverage_95 <= 0.99


def _kernel(n_features: int):
    return ConstantKernel(0.01, (1e-6, 10.0)) * Matern(
        np.ones(n_features), (1e-2, 1e3), nu=2.5
    ) + WhiteKernel(1e-4, (1e-8, 1e-1))


def _alpha(noise_var: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Per-point noise variance in the normalised units of the GP (``normalize_y``)."""
    return np.maximum(noise_var / max(float(np.var(y)), 1e-12), 1e-10)


class ThrustPowerFit:
    """The Gaussian processes fitted on a test database (one per output)."""

    def __init__(
        self,
        tests: TestDatabase,
        motors: MotorDatabase | None = None,
        propellers: PropellerDatabase | None = None,
        seed: int = 0,
    ) -> None:
        self.tests, self.motors, self.propellers, self.seed = (
            tests,
            motors,
            propellers,
            seed,
        )
        rows, targets, groups, physics, noise = [], {k: [] for k in OUTPUTS}, [], [], []
        self.pairs: dict[tuple[str, str], Pair] = {}
        self.max_thrust: dict[tuple[str, str], float] = {}
        for test in tests.records.values():
            pair = Pair.of(test.motor_id, test.propeller_id, motors, propellers)
            self.pairs[test.pair] = pair
            self.max_thrust[test.pair] = max(
                self.max_thrust.get(test.pair, 0.0), test.max_thrust_n
            )
            phys = physics_mean(
                pair,
                test.thrust_n,
                test.voltage,
                TEST_RHO,
                test.measured_at == "esc_input",
            )
            data = {
                "power_w": test.power_w,
                "current_a": test.current_a,
                "rpm": test.rpm,
            }
            ok = np.isfinite(phys["power_w"])
            rows.append(features(pair, test.thrust_n, test.voltage)[ok])
            groups += [f"{test.motor_id}|{test.propeller_id}"] * int(ok.sum())
            physics.append(phys["power_w"][ok] / data["power_w"][ok])
            # Measurement noise of the table: its own P vs U·I disagreement (log variance).
            mismatch = np.log(test.power_w / (test.voltage * test.current_a))
            noise.append(np.full(int(ok.sum()), np.mean(mismatch**2)))
            for k in OUTPUTS:
                targets[k].append(np.log(data[k][ok] / phys[k][ok]))
        self.x = np.vstack(rows) if rows else np.zeros((0, 5))
        self.y = {
            k: np.concatenate(v) if v else np.zeros(0) for k, v in targets.items()
        }
        self.groups = np.asarray(groups)
        self.physics_ratio = np.concatenate(physics) if physics else np.zeros(0)
        self.noise_var = np.concatenate(noise) if noise else np.zeros(0)
        self.x_min, self.x_max = (
            (self.x.min(axis=0), self.x.max(axis=0)) if len(self.x) else (None, None)
        )
        self.gps: dict[str, GaussianProcessRegressor] = {}
        for k in OUTPUTS:
            y = self.y[k]
            finite = np.isfinite(y)
            if finite.sum() < 3:
                continue
            gp = GaussianProcessRegressor(
                _kernel(self.x.shape[1]),
                alpha=_alpha(self.noise_var[finite], y[finite]),
                normalize_y=True,
                n_restarts_optimizer=3,
                random_state=seed,
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                gp.fit(self.x[finite], y[finite])
            self.gps[k] = gp
        # Residual σ of the physics alone, used when no data covers a prediction.
        self.physics_sd = (
            float(np.std(self.y["power_w"])) if len(self.y["power_w"]) else 0.25
        )

    def correction(self, key: str, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Mean and standard deviation of the log correction (zero mean, physics σ without GP)."""
        if key not in self.gps:
            return np.zeros(len(x)), np.full(len(x), self.physics_sd)
        mean, sd = self.gps[key].predict(x, return_std=True)
        return mean, sd

    # --- validation ------------------------------------------------------------

    def _loo(self, key: str) -> tuple[np.ndarray, np.ndarray]:
        """Closed-form leave-one-out mean and σ (fixed hyperparameters, Rasmussen & Williams eq. 5.12)."""
        gp = self.gps[key]
        y = self.y[key]
        mu_y, sd_y = gp._y_train_mean, gp._y_train_std  # noqa: SLF001  (normalisation of sklearn)
        yn = (y - mu_y) / sd_y
        k = gp.kernel_(self.x)
        k[np.diag_indices_from(k)] += gp.alpha
        inv = np.linalg.inv(k)
        alpha = inv @ yn
        diag = np.diag(inv)
        mean = yn - alpha / diag
        sd = np.sqrt(1.0 / diag)
        return mean * sd_y + mu_y, sd * sd_y

    def _lopo(self, key: str) -> tuple[np.ndarray, np.ndarray]:
        """Leave-one-pair-out: refit with the fitted hyperparameters, predict the left-out pair."""
        mean, sd = np.full(len(self.x), np.nan), np.full(len(self.x), np.nan)
        for g in np.unique(self.groups):
            out = self.groups == g
            gp = GaussianProcessRegressor(
                self.gps[key].kernel_,
                alpha=_alpha(self.noise_var[~out], self.y[key][~out]),
                normalize_y=True,
                optimizer=None,
            )
            gp.fit(self.x[~out], self.y[key][~out])
            mean[out], sd[out] = gp.predict(self.x[out], return_std=True)
        return mean, sd

    def validate(self) -> ValidationReport:
        """LOO and leave-one-pair-out errors and 95 % coverage on the power."""
        y = self.y["power_w"]
        loo_m, loo_s = self._loo("power_w")
        lopo_m, lopo_s = self._lopo("power_w")
        loo_err, lopo_err = np.abs(np.expm1(loo_m - y)), np.abs(np.expm1(lopo_m - y))
        per_pair = {}
        for g in np.unique(self.groups):
            sel = self.groups == g
            per_pair[g] = {
                "n": int(sel.sum()),
                "loo_mean_rel_err": float(loo_err[sel].mean()),
                "lopo_mean_rel_err": float(lopo_err[sel].mean()),
                "physics_mean_rel_err": float(
                    np.abs(self.physics_ratio[sel] - 1).mean()
                ),
            }
        return ValidationReport(
            n_points=len(y),
            n_pairs=len(per_pair),
            loo_mean_rel_err=float(loo_err.mean()),
            loo_max_rel_err=float(loo_err.max()),
            loo_coverage_95=float(np.mean(np.abs(loo_m - y) <= 1.96 * loo_s)),
            lopo_mean_rel_err=float(lopo_err.mean()),
            lopo_max_rel_err=float(lopo_err.max()),
            lopo_coverage_95=float(np.mean(np.abs(lopo_m - y) <= 1.96 * lopo_s)),
            physics_mean_rel_err=float(np.abs(self.physics_ratio - 1).mean()),
            data_hash=self.tests.hash(),
            per_pair=per_pair,
        )


@cache
def _default_fit(data_hash: str) -> ThrustPowerFit:  # noqa: ARG001  (cache key)
    return ThrustPowerFit(default_tests())


def default_fit() -> ThrustPowerFit:
    """The fit of the shipped and user tests, cached by their content hash."""
    return _default_fit(default_tests().hash())


def _tested_point_within_band(model: ThrustPowerSurrogate) -> bool:
    fit = default_fit()
    test = fit.tests.tests(model.p.motor_id, model.p.propeller_id)[0]
    i = len(test.thrust_n) // 2
    y = model.evaluate({
        "thrust_n": test.thrust_n[i],
        "battery_voltage_v": test.voltage[i],
        "rho": TEST_RHO,
    })
    return abs(np.log(test.power_w[i] / float(y["power_w"]))) <= 3.0 * float(
        y["power_sd_rel"]
    )


def _uncertainty_grows_beyond_data(model: ThrustPowerSurrogate) -> bool:
    fit = default_fit()
    t_max = fit.max_thrust[model.p.motor_id, model.p.propeller_id]
    test = fit.tests.tests(model.p.motor_id, model.p.propeller_id)[0]
    y = model.evaluate({
        "thrust_n": np.array([0.6 * t_max, 1.6 * t_max]),
        "battery_voltage_v": test.voltage_v,
        "rho": TEST_RHO,
    })
    return bool(y["power_sd_rel"][1] > y["power_sd_rel"][0] and not y["trusted"][1])


_EXAMPLE = {"motor_id": "tmotor-mn2806-650kv", "propeller_id": "tmotor-p12x4"}


class ThrustPowerSurrogate(Model):
    """Electric power, current and rpm of a motor + propeller pair at a static thrust.

    P = P_phys(T)·exp(μ_r(x)); σ_rel = σ_r(x); trusted when σ_rel ≤ s_max and T ≤ T_max
    of the tested pair (tested pair) or x within the tested input box (untested pair).
    """

    mic_id = "MIC-PROP-SUR"
    inputs = ports(
        Port("thrust_n", "T", "N", "static thrust of one rotor", (0, None)),
        Port(
            "battery_voltage_v", "U", "V", "voltage at the ESC / motor input", (0, None)
        ),
        Port("rho", "ρ", "kg/m³", "air density", (0, None)),
    )
    outputs = ports(
        Port(
            "power_w",
            "P",
            "W",
            "electric power at the measurement point of the data",
            (0, None),
        ),
        Port(
            "power_sd_rel",
            "σ_rel",
            "—",
            "relative standard deviation of the power",
            (0, None),
        ),
        Port("current_a", "I", "A", "current", (0, None)),
        Port("rpm", "N", "rpm", "rotation speed", (0, None)),
        Port("physics_power_w", "P_phys", "W", "physics mean of the power", (0, None)),
        Port("trusted", "—", "—", "inside the trusted domain"),
    )
    parameters = params(
        Param(
            "motor_id", "—", "—", "motor id", origin="project", source="motor database"
        ),
        Param(
            "propeller_id",
            "—",
            "—",
            "propeller id, or 'DxP' for a propeller not in the database",
            origin="project",
            source="propeller database",
        ),
        Param(
            "diameter_in",
            "D",
            "in",
            "propeller diameter when not in the database",
            default=None,
            source="project",
        ),
        Param(
            "pitch_in",
            "P",
            "in",
            "propeller pitch when not in the database",
            default=None,
            source="project",
        ),
        Param(
            "esc_input",
            "—",
            "—",
            "give the power at the ESC input (data measured there)",
            default=False,
            source="data",
        ),
        Param(
            "max_sd_rel",
            "s_max",
            "—",
            "largest trusted relative standard deviation",
            default=0.05,
            bounds=(0, 1),
            source="designer, 2026-10-14",
        ),
    )
    expected_forms = [
        Invariant(
            "a tested point lies within 3σ of the prediction",
            _tested_point_within_band,
            params=_EXAMPLE,
        ),
        Invariant(
            "σ grows beyond the tested thrust, flagged untrusted",
            _uncertainty_grows_beyond_data,
            params=_EXAMPLE,
        ),
    ]

    def __init__(self, fit: ThrustPowerFit | None = None, **values) -> None:
        super().__init__(**values)
        self.fit = fit

    @property
    def pair(self) -> Pair:
        fit = self.fit or default_fit()
        key = (self.p.motor_id, self.p.propeller_id)
        if key in fit.pairs:
            return fit.pairs[key]
        if self.p.diameter_in is not None:
            return Pair.custom(
                self.p.motor_id,
                self.p.diameter_in,
                self.p.pitch_in or self.p.diameter_in / 2,
            )
        return Pair.of(self.p.motor_id, self.p.propeller_id)

    def predict(self, thrust_n, battery_voltage_v, rho: float = TEST_RHO) -> Prediction:
        fit = self.fit or default_fit()
        pair = self.pair
        t = np.atleast_1d(np.asarray(thrust_n, dtype=float))
        u = np.broadcast_to(np.asarray(battery_voltage_v, dtype=float), t.shape)
        phys = physics_mean(pair, t, u, rho, bool(self.p.esc_input))
        x = features(pair, np.maximum(t, 1e-6), u)
        key = (pair.motor_id, pair.propeller_id)
        source = (
            "tested_pair"
            if key in fit.max_thrust
            else ("untested_pair" if fit.gps else "physics_only")
        )
        out = {}
        for k in OUTPUTS:
            mu, sd = fit.correction(k, x)
            out[k], out[f"{k}_sd"] = phys[k] * np.exp(mu), phys[k] * np.exp(mu) * sd
            if k == "power_w":
                sd_rel = sd
        reason = np.full(t.shape, "", dtype=object)
        reason = np.where(
            sd_rel > self.p.max_sd_rel, "relative σ above the threshold", reason
        )
        if source == "tested_pair":
            reason = np.where(
                t > fit.max_thrust[key] * (1 + 1e-9),
                "thrust beyond the tested range",
                reason,
            )
        elif source == "untested_pair":
            inside = np.all((x >= fit.x_min - 1e-9) & (x <= fit.x_max + 1e-9), axis=1)
            reason = np.where(~inside, "outside the tested inputs", reason)
        else:
            reason = np.full(t.shape, "no test data", dtype=object)
        reason = np.where(
            np.isfinite(phys["power_w"]),
            reason,
            "thrust not reachable by the physics model",
        )
        return Prediction(
            out["power_w"],
            out["power_w_sd"],
            out["current_a"],
            out["current_a_sd"],
            out["rpm"],
            out["rpm_sd"],
            sd_rel,
            reason == "",
            reason.astype(str),
            source,
            phys["power_w"],
        )

    def evaluate(self, x):
        p = self.predict(
            x["thrust_n"], x["battery_voltage_v"], float(x.get("rho", TEST_RHO))
        )
        scalar = np.ndim(x["thrust_n"]) == 0
        pick = (operator.itemgetter(0)) if scalar else (lambda a: a)
        return {
            "power_w": pick(p.power_w),
            "power_sd_rel": pick(p.sd_rel),
            "current_a": pick(p.current_a),
            "rpm": pick(p.rpm),
            "physics_power_w": pick(p.physics_power_w),
            "trusted": pick(p.trusted),
        }


def data_hash(tests: TestDatabase) -> str:
    """Hash of the data a fit depends on (alias of ``TestDatabase.hash``)."""
    return tests.hash() or hashlib.sha256(b"").hexdigest()[:16]
