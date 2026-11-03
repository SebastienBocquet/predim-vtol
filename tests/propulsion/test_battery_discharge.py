"""Battery state of charge: open-circuit curve, resistance factor, stateless discharge."""

from __future__ import annotations

import numpy as np
import pytest

from predimrc_wrapper.propulsion.battery import BatteryModel


@pytest.fixture(params=["lipo", "li-ion"])
def battery(request):
    return BatteryModel.from_mass(request.param, 4, 0.45)


def test_without_soc_the_nominal_point_is_unchanged(battery):
    y = battery.evaluate({"power_w": 300.0})
    v0, r = battery.open_circuit_voltage, battery.resistance_ohm
    current = (v0 - np.sqrt(v0**2 - 4.0 * r * 300.0)) / (2.0 * r)
    assert float(y["current_a"]) == pytest.approx(current, rel=1e-12)
    assert float(y["voltage_v"]) == pytest.approx(v0 - r * current, rel=1e-12)


def test_open_circuit_voltage_follows_the_state_of_charge(battery):
    n, p = battery.p.n_series, battery.p
    assert battery.ocv_v(1.0) == pytest.approx(n * p.v_full)
    assert battery.ocv_v(0.0) == pytest.approx(n * p.v_cutoff)
    socs = np.linspace(0.0, 1.0, 21)
    assert np.all(np.diff([battery.ocv_v(s) for s in socs]) > 0)


def test_resistance_grows_below_twenty_percent(battery):
    r = battery.resistance_ohm
    assert battery.resistance_at(1.0) == pytest.approx(r)
    assert battery.resistance_at(0.2) == pytest.approx(r)
    assert battery.resistance_at(0.1) == pytest.approx(1.25 * r)
    assert battery.resistance_at(0.0) == pytest.approx(1.5 * r)


def test_cut_off_flag(battery):
    assert bool(battery.evaluate({"power_w": 100.0, "soc": 0.5})["cutoff_ok"])
    assert not bool(battery.evaluate({"power_w": 100.0, "soc": 0.0})["cutoff_ok"])


def test_discharge_energy_closure_and_shape(battery):
    d = battery.discharge([120.0, 900.0, 60.0], [400.0, 150.0, 400.0], list("abc"))
    assert d.names == ["a", "b", "c"]
    assert d.segment_end == [1, 3, 5]
    assert d.time_s[-1] == pytest.approx(1080.0)
    assert np.all(np.diff(d.soc) <= 0)
    # Energy drawn ≥ terminal energy (Joule losses), ≤ the same at the lowest voltage.
    drawn = (1.0 - d.soc[-1]) * 3600.0 * battery.energy_wh()
    terminal = 400.0 * 120.0 + 150.0 * 900.0 + 400.0 * 60.0
    assert terminal < drawn < terminal * 1.05
    # Same power, lower state of charge: lower voltage.
    assert d.voltage_v[5] < d.voltage_v[0]


def test_discharge_converges_with_the_steps(battery):
    coarse = battery.discharge([1500.0], [150.0], n_sub=5).soc[-1]
    fine = battery.discharge([1500.0], [150.0], n_sub=200).soc[-1]
    assert 0.0 < fine < 0.3  # through the low state of charge (resistance growing)
    assert coarse == pytest.approx(fine, abs=1e-4)  # kinks of the piecewise curve
