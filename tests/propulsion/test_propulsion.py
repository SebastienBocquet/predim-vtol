"""Tests of the propulsion models (MVP-003)."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.propulsion import BatteryModel
from predimrc_wrapper.propulsion import MomentumPropeller
from predimrc_wrapper.propulsion import MotorModel
from predimrc_wrapper.propulsion import PropulsionUnit
from predimrc_wrapper.propulsion import density


def test_isa():
    assert density(0.0) == pytest.approx(1.2250, abs=5e-4)
    assert density(1000.0) == pytest.approx(1.1117, abs=1e-3)
    with pytest.raises(ValueError, match="troposphere"):
        density(12000.0)


def test_battery_round_trip():
    b = BatteryModel.from_capacity("lipo", 6, 5000.0)
    back = BatteryModel.from_mass("lipo", 6, b.p.mass_kg)
    assert back.p.capacity_ah == pytest.approx(5.0, rel=1e-12)
    assert b.energy_wh() == pytest.approx(6 * 3.7 * 5.0)
    assert b.usable_energy_j() == pytest.approx(3600 * 0.85 * 111.0)
    assert b.max_current_a() == pytest.approx(150.0)


def test_battery_infeasible_power():
    b = BatteryModel.from_capacity("li-ion", 6, 5000.0)
    p_max = b.open_circuit_voltage**2 / (4 * b.resistance_ohm)
    y = b.evaluate({"power_w": np.array([0.5 * p_max, 1.01 * p_max])})
    assert y["feasible"].tolist() == [True, False]
    assert np.isnan(y["current_a"][1])
    assert y["chemical_power_w"][0] > 0.5 * p_max


def test_battery_unknown_chemistry():
    with pytest.raises(ValueError, match="Unknown chemistry"):
        BatteryModel.from_mass("nimh", 6, 0.5)


def test_motor_from_database():
    m = MotorModel.from_database("tmotor-mn2212-920kv")
    assert m.p.r_m == pytest.approx(0.142)
    y = m.evaluate({"torque_nm": 0.0, "omega_rad_s": 300.0})
    assert float(y["current_a"]) == pytest.approx(0.5)


def test_propeller_ideal_hover():
    prop = MomentumPropeller(diameter_m=0.4, mass_kg=0.03, figure_of_merit=1.0)
    t, rho = 8.0, 1.2
    expected = t**1.5 / np.sqrt(2 * rho * np.pi * 0.2**2)
    assert float(prop.evaluate({"thrust_n": t, "v_m_s": 0.0, "rho": rho})["shaft_power_w"]) == pytest.approx(expected, rel=1e-12)


def _unit(i_max=25.0):
    return PropulsionUnit(
        MotorModel(kv=330.0, r_m=0.085, i0=1.1, i_max=i_max, p_max=750.0, mass_kg=0.171),
        MomentumPropeller(diameter_m=0.381, mass_kg=0.025),
    )


@pytest.mark.parametrize("v", [0.0, 12.0])
def test_unit_energy_chain(v):
    y = _unit().evaluate({"thrust_n": 5.0, "v_axial_m_s": v, "rho": 1.225, "battery_voltage_v": 22.2})
    assert float(y["battery_power_w"]) >= float(y["power_elec_w"]) >= float(y["shaft_power_w"]) >= 5.0 * v
    assert bool(y["feasible"])


def test_unit_undersized_motor():
    y = _unit(i_max=4.0).evaluate({"thrust_n": 15.0, "v_axial_m_s": 0.0, "rho": 1.225, "battery_voltage_v": 22.2})
    assert not bool(y["feasible"])
    assert str(y["limiting"]) == "motor_current"


def test_unit_max_thrust_is_feasible_limit():
    unit = _unit()
    t_max = unit.max_thrust(1.225, 22.2)
    ok = unit.evaluate({"thrust_n": 0.999 * t_max, "v_axial_m_s": 0.0, "rho": 1.225, "battery_voltage_v": 22.2})
    ko = unit.evaluate({"thrust_n": 1.01 * t_max, "v_axial_m_s": 0.0, "rho": 1.225, "battery_voltage_v": 22.2})
    assert bool(ok["feasible"]) and not bool(ko["feasible"])


def test_unit_vectorised():
    t = np.linspace(1.0, 10.0, 5)
    y = _unit().evaluate({"thrust_n": t, "v_axial_m_s": 0.0, "rho": 1.225, "battery_voltage_v": 22.2})
    assert y["battery_power_w"].shape == (5,)
    assert np.all(np.diff(y["battery_power_w"]) > 0)


def test_blade_element_thrust_inverse():
    from predimrc_wrapper.propulsion import BladeElementPropeller  # noqa: PLC0415

    prop = BladeElementPropeller(diameter_m=0.3048, pitch_m=0.1016)
    n = prop.n_for_thrust(np.array([3.0, 6.0]), np.array([0.0, 10.0]), 1.225)
    y = prop.evaluate({"n_rev_s": n, "v_m_s": np.array([0.0, 10.0]), "rho": 1.225})
    assert y["thrust_n"] == pytest.approx([3.0, 6.0], rel=1e-6)
    assert np.isnan(prop.n_for_thrust(1e4, 0.0, 1.225))


def test_blade_element_pitch_trends():
    """A higher pitch: more static power at equal thrust, more efficient at speed."""
    from predimrc_wrapper.propulsion import BladeElementPropeller  # noqa: PLC0415

    low, high = (BladeElementPropeller(diameter_m=0.254, pitch_m=p * 0.0254) for p in (4.5, 8.0))
    for prop in (low, high):
        prop.n_static = float(prop.n_for_thrust(5.0, 0.0, 1.225))
    p_low = float(low.evaluate({"n_rev_s": low.n_static, "v_m_s": 0.0, "rho": 1.225})["shaft_power_w"])
    p_high = float(high.evaluate({"n_rev_s": high.n_static, "v_m_s": 0.0, "rho": 1.225})["shaft_power_w"])
    assert p_high > p_low
    eta = [float(p.evaluate({"n_rev_s": p.n_for_thrust(2.0, 20.0, 1.225), "v_m_s": 20.0, "rho": 1.225})["efficiency"])
           for p in (low, high)]
    assert eta[1] > eta[0]
