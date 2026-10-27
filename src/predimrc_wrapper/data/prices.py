"""Component prices with their provenance (``prices.yaml``, REQ-COST-001)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

import yaml

STATUSES = ("verified", "search")


@dataclass(frozen=True)
class Price:
    """A price and where it comes from."""

    price: float
    source: str
    status: str
    name: str = ""
    notes: str = ""


@dataclass(frozen=True)
class EscPrice(Price):
    """An ESC of a given current rating."""

    rating_a: float = 0.0


def _price(raw: dict[str, Any], what: str, key: str = "price") -> dict[str, Any]:
    missing = [k for k in (key, "source", "status") if raw.get(k) in (None, "")]
    if missing:
        msg = f"Price of {what}: missing {missing} (every price needs its source and status)."
        raise ValueError(msg)
    if raw["status"] not in STATUSES:
        msg = f"Price of {what}: status {raw['status']!r} not in {STATUSES}."
        raise ValueError(msg)
    return {
        "price": float(raw[key]),
        "source": raw["source"],
        "status": raw["status"],
        "name": raw.get("name", ""),
        "notes": raw.get("notes", ""),
    }


class PriceDatabase:
    """Prices of motors, propellers, ESCs, batteries (per Wh) and cables (per metre)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.currency: str = data["currency"]
        self.retrieved = str(data.get("retrieved", ""))
        exchange = data["exchange"]
        self.usd_per_eur = float(exchange["usd_per_eur"])
        """ECB reference rate: price (EUR) = price (USD) / usd_per_eur."""
        self.exchange_date = str(exchange["date"])
        self.exchange_source: str = exchange["source"]
        self.motors = {
            k: Price(**_price(v, f"motor {k}")) for k, v in data["motors"].items()
        }
        self.propellers = {
            k: Price(**_price(v, f"propeller {k}"))
            for k, v in data["propellers"].items()
        }
        self.escs = {
            kind: sorted(
                (
                    EscPrice(
                        **_price(v, f"ESC {v.get('name')}"),
                        rating_a=float(v["rating_a"]),
                    )
                    for v in items
                ),
                key=lambda e: (e.rating_a, e.price),
            )
            for kind, items in data["escs"].items()
        }
        self.batteries = {
            k: Price(**_price(v, f"battery {k}", "price_per_wh"))
            for k, v in data["batteries"].items()
        }
        cables = data["cables"]
        self.cables = {
            int(awg): Price(
                **_price(
                    {**cables, "price": value, "name": f"AWG{awg}"}, f"cable AWG{awg}"
                )
            )
            for awg, value in cables["price_per_m"].items()
        }

    def motor(self, motor_id: str) -> Price | None:
        return self.motors.get(motor_id)

    def propeller(self, propeller_id: str) -> Price | None:
        return self.propellers.get(propeller_id)

    def esc(self, current_a: float, four_in_one: bool = False) -> EscPrice | None:
        """Cheapest ESC whose rating covers the current (None when none does)."""
        candidates = [
            e
            for e in self.escs["four_in_one" if four_in_one else "separate"]
            if e.rating_a >= current_a
        ]
        return min(candidates, key=lambda e: e.price, default=None)

    def battery(self, chemistry: str) -> Price | None:
        """Price per Wh of nominal energy."""
        return self.batteries.get(chemistry)

    def cable(self, awg: int) -> Price | None:
        """Price per metre of one conductor."""
        return self.cables.get(int(awg))


@cache
def default_prices() -> PriceDatabase:
    """The shipped price list."""
    text = (
        files("predimrc_wrapper.data")
        .joinpath("prices.yaml")
        .read_text(encoding="utf-8")
    )
    return PriceDatabase(yaml.safe_load(text))
