"""Thrust–power surrogate and its error guarantee (INC2-003)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.data import TestDatabase
from predimrc_wrapper.data import default_tests
from predimrc_wrapper.data.tests import parse_test
from predimrc_wrapper.propulsion import ThrustPowerSurrogate
from predimrc_wrapper.propulsion.surrogate import Pair
from predimrc_wrapper.propulsion.surrogate import ThrustPowerFit
from predimrc_wrapper.propulsion.surrogate import default_fit
from predimrc_wrapper.propulsion.surrogate import physics_mean


def test_shipped_data_meet_the_guarantee():
    report = default_fit().validate()
    assert report.n_points == 144
    assert report.n_pairs == 17
    assert report.loo_mean_rel_err <= 0.03
    assert 0.90 <= report.loo_coverage_95 <= 0.99
    assert report.lopo_mean_rel_err <= 0.05
    assert report.passed()
    assert report.data_hash == default_tests().hash()


def test_physics_mean_within_25_percent_of_every_pair():
    for test in default_tests().records.values():
        phys = physics_mean(
            Pair.of(test.motor_id, test.propeller_id), test.thrust_n, test.voltage
        )
        assert np.mean(np.abs(phys["power_w"] / test.power_w - 1)) < 0.25, test.id


def test_tested_pair_interpolation():
    test = default_tests().records["tmotor-mn2806-650kv__tmotor-p12x4__15.3v"]
    model = ThrustPowerSurrogate(motor_id=test.motor_id, propeller_id=test.propeller_id)
    p = model.predict(test.thrust_n, test.voltage)
    assert p.source == "tested_pair"
    assert np.all(np.abs(p.power_w / test.power_w - 1) < 0.03)
    low, high = p.interval95()
    assert np.mean((test.power_w >= low) & (test.power_w <= high)) >= 0.85
    assert np.all(p.trusted)


def test_untrusted_beyond_tested_thrust():
    model = ThrustPowerSurrogate(
        motor_id="tmotor-mn2806-650kv", propeller_id="tmotor-p12x4"
    )
    p = model.predict(np.array([5.0, 14.0]), 15.3)
    assert p.trusted.tolist() == [True, False]
    assert "beyond the tested range" in p.reason[1]


def test_untested_pair_has_larger_uncertainty():
    tested = ThrustPowerSurrogate(
        motor_id="tmotor-mn2806-650kv", propeller_id="tmotor-p12x4"
    )
    untested = ThrustPowerSurrogate(
        motor_id="tmotor-mn2806-650kv",
        propeller_id="12.5x4.2",
        diameter_in=12.5,
        pitch_in=4.2,
    )
    a, b = tested.predict(6.0, 15.3), untested.predict(6.0, 15.3)
    assert b.source == "untested_pair"
    assert b.sd_rel[0] >= a.sd_rel[0]
    assert b.power_w[0] == pytest.approx(a.power_w[0], rel=0.15)


def test_physics_only_without_data(tmp_path):
    fit = ThrustPowerFit(TestDatabase({}))
    p = ThrustPowerSurrogate(
        fit, motor_id="tmotor-mn2806-650kv", propeller_id="tmotor-p12x4"
    ).predict(6.0, 15.3)
    assert p.source == "physics_only"
    assert not p.trusted[0]
    assert p.reason[0] == "no test data"
    assert p.power_w[0] == pytest.approx(p.physics_power_w[0])


def test_synthetic_data_coverage():
    """Data drawn from the physics model with 2 % noise: coverage close to 95 %."""
    rng = np.random.default_rng(1)
    records = {}
    for motor, prop, volt in (
        ("tmotor-mn2806-650kv", "tmotor-p12x4", 15.3),
        ("tmotor-mn2806-400kv", "tmotor-p13x4.4", 23.3),
        ("tmotor-mn2212-780kv", "tmotor-9545b", 14.8),
    ):
        thrust_g = np.linspace(250, 950, 12)
        phys = physics_mean(Pair.of(motor, prop), thrust_g * 9.81e-3, volt)
        power = phys["power_w"] * np.exp(rng.normal(0, 0.02, thrust_g.size))
        rows = [
            [t, p / volt, p, r]
            for t, p, r in zip(thrust_g, power, phys["rpm"], strict=False)
        ]
        raw = {
            "id": motor,
            "motor_id": motor,
            "propeller_id": prop,
            "voltage_v": volt,
            "bench": "synthetic",
            "source": "synthetic",
            "retrieved": "2026-10-14",
            "status": "estimated",
            "columns": ["thrust_g", "current_a", "power_w", "rpm"],
            "rows": rows,
        }
        records[motor] = parse_test(raw, "synthetic")
    report = ThrustPowerFit(TestDatabase(records, digest="synthetic")).validate()
    assert 0.85 <= report.loo_coverage_95 <= 1.0
    assert report.loo_mean_rel_err < 0.03
