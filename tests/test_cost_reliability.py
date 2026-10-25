"""Prices, purchase cost, cost of use, motor-out hover (REQ-COST-001 to -003)."""

from __future__ import annotations

import copy

import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import layouts
from predimrc_wrapper.cost import cost
from predimrc_wrapper.data.prices import PriceDatabase
from predimrc_wrapper.data.prices import default_prices
from predimrc_wrapper.reliability import default_spins
from predimrc_wrapper.reliability import motor_out


def test_every_price_has_a_source():
    prices = default_prices()
    assert prices.currency == "USD"
    records = [
        *prices.motors.values(),
        *prices.propellers.values(),
        *prices.batteries.values(),
        *prices.cables.values(),
        *[e for kind in prices.escs.values() for e in kind],
    ]
    assert records
    for r in records:
        assert r.price > 0
        assert r.source.startswith("https://")
        assert r.status in ("verified", "search")
    from predimrc_wrapper.data import default_database  # noqa: PLC0415

    assert set(default_database().ids()) <= set(prices.motors)


def test_price_without_source_rejected():
    from importlib.resources import files  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    data = yaml.safe_load(
        files("predimrc_wrapper.data")
        .joinpath("prices.yaml")
        .read_text(encoding="utf-8")
    )
    data = copy.deepcopy(data)
    del data["motors"]["tmotor-mn2212-780kv"]["source"]
    with pytest.raises(ValueError, match="source"):
        PriceDatabase(data)


def test_esc_is_the_cheapest_rating_covering_the_current():
    prices = default_prices()
    assert prices.esc(15.0).rating_a == 20
    assert prices.esc(25.0).rating_a == 40
    assert prices.esc(500.0) is None
    assert prices.esc(40.0, four_in_one=True).rating_a == 55


def test_purchase_cost_is_the_sum_of_the_items():
    project = Project.template("quadplane")
    result = cost(AircraftModel(project), 1200.0)
    priced = [i.total for i in result.items if i.total is not None]
    assert result.purchase == pytest.approx(sum(priced))
    assert sum(result.by_category().values()) == pytest.approx(result.purchase)
    motors = next(i for i in result.items if i.item == "tmotor-mn2806-650kv")
    assert motors.quantity == 4
    assert motors.unit_price == pytest.approx(46.90 / default_prices().usd_per_eur)


def test_override_replaces_the_database_price():
    project = Project.template("quadplane").with_overrides({
        "cost": {
            "frame": 120.0,
            "overrides": {"motor:tmotor-mn2806-650kv": 30.0, "cable:10": 6.0},
        }
    })
    result = cost(AircraftModel(project), 1200.0)
    motors = next(i for i in result.items if i.item == "tmotor-mn2806-650kv")
    assert motors.unit_price == 30.0
    assert motors.status == "entered"
    assert "silicone wire AWG10" not in result.missing
    assert result.by_category()["frame"] == 120.0


def test_four_in_one_is_one_board_for_the_lift_motors():
    project = Project.template("quadplane").with_overrides({
        "wiring": {"lift_esc": "four_in_one", "four_in_one_mass_g": 15.0}
    })
    escs = [
        i for i in cost(AircraftModel(project), 1200.0).items if i.category == "ESCs"
    ]
    assert [e.quantity for e in escs] == [1, 1]  # the pusher's ESC and one 4-in-1 board
    assert any("4in1" in e.item for e in escs)


def test_cost_of_use_by_hand():
    project = Project.template("tricopter").with_overrides({
        "cost": {"battery_cycles": 250, "motor_life_h": 500.0, "propeller_flights": 100}
    })
    t = 1800.0
    result = cost(AircraftModel(project), t)
    cats = result.by_category()
    assert result.per_flight["battery"] == pytest.approx(cats["battery"] / 250)
    assert result.per_flight["motors"] == pytest.approx(cats["motors"] * 0.5 / 500.0)
    assert result.per_flight["propellers"] == pytest.approx(cats["propellers"] / 100)
    assert result.cost_per_hour == pytest.approx(result.cost_per_flight / 0.5)


def _multirotor(n: int, arm_mm: float) -> Project:
    data = Project.template("multicopter").to_dict()
    data["motors"] = layouts.multirotor(n, arm_mm, "lift")
    data["battery"]["mass_g"] = 500
    return Project.model_validate(data)


def test_quad_x_does_not_survive_a_motor_loss():
    rel = motor_out(AircraftModel(Project.template("multicopter")))
    assert not rel.yaw_by_tilt
    assert not any(c.survivable for c in rel.cases)
    assert rel.worst_thrust_to_weight == 0.0


def test_hexacopter_survives_a_motor_loss():
    project = _multirotor(6, 400.0)
    assert default_spins(project) == [-1, 1, -1, 1, -1, 1]
    rel = motor_out(AircraftModel(project))
    assert rel.all_survivable
    for c in rel.cases:
        weight = sum(c.thrusts_n.values())
        assert weight == pytest.approx(
            AircraftModel(project).download_factor
            * AircraftModel(project).total_mass_kg
            * 9.81
        )
        assert c.thrust_to_weight > 1.0


def test_tricopter_rule_yaw_by_the_tilting_rear_motor():
    rel = motor_out(AircraftModel(Project.template("tricopter")))
    assert rel.yaw_by_tilt
    assert len(rel.cases) == 3
    assert not any(
        c.survivable for c in rel.cases
    )  # 2 motors cannot balance pitch and roll
    assert "battery (one pack)" in rel.single_points


def test_spin_given_replaces_the_default():
    project = _multirotor(6, 400.0).with_overrides({"motors.0.spin": "ccw"})
    assert default_spins(project)[0] == 1
