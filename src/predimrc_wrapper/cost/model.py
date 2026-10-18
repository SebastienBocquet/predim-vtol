"""Purchase cost and cost of use (REQ-COST-001, REQ-COST-002, MIC-COST).

Purchase cost: Σ items, each priced from ``data/prices.yaml`` (with its source) or an override
of the project (``cost.overrides``):

- motors: one per motor slot, price of the motor id;
- propellers: one per motor, price of the database propeller of its unit type; a propeller given
  only by its diameter and pitch is priced as the cheapest database propeller of the same
  diameter (status "estimate");
- ESCs: separate ESCs, the cheapest rating ≥ 1.25 × I_max of the motor; with a 4-in-1 lift
  ESC, one board whose rating ≥ 1.25 × the largest I_max of the lift motors, plus a separate
  ESC per cruise motor;
- battery: price per Wh of the chemistry × nominal energy;
- cables: main (2 conductors), DC (2 per ESC), phase (3 per motor), price per metre of the
  gauge, lengths and gauges of the power chain;
- frame and avionics: entered.

An item without a price is listed with "no price" and left out of the total (never 0).

Cost of use (wear), per flight of duration t (two-phase flight time at V₁):

    C_flight = P_battery / N_cycles + Σ P_motor · t / L_motor + Σ P_propeller / N_flights,prop

and per flight hour C_hour = C_flight / t. Defaults: N_cycles 300 (LiPo), 500 (Li-ion);
L_motor 1000 h; N_flights,prop 200.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from predimrc_wrapper.data.prices import default_prices

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel

DEFAULT_CYCLES = {"lipo": 300, "li-ion": 500}
ESC_MARGIN = 1.25


@dataclass
class CostItem:
    """One line of the purchase cost."""

    category: str
    item: str
    quantity: float
    unit_price: float | None
    source: str
    status: str

    @property
    def total(self) -> float | None:
        return None if self.unit_price is None else self.quantity * self.unit_price


@dataclass
class CostResult:
    """Purchase cost and cost of use."""

    items: list[CostItem]
    currency: str
    flight_time_s: float
    per_flight: dict[str, float]
    """Wear cost of one flight by category (battery, motors, propellers)."""

    @property
    def purchase(self) -> float:
        return sum(i.total for i in self.items if i.total is not None)

    @property
    def missing(self) -> list[str]:
        return [i.item for i in self.items if i.unit_price is None]

    @property
    def cost_per_flight(self) -> float:
        return sum(self.per_flight.values())

    @property
    def cost_per_hour(self) -> float:
        return (
            self.cost_per_flight / (self.flight_time_s / 3600.0)
            if self.flight_time_s > 0
            else float("nan")
        )

    def by_category(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for i in self.items:
            if i.total is not None:
                out[i.category] = out.get(i.category, 0.0) + i.total
        return out


def cost(
    aircraft: AircraftModel,
    flight_time_s: float,
    hover_currents_a: list[float] | None = None,
) -> CostResult:
    """Purchase cost and cost of use of a project."""
    from predimrc_wrapper.aircraft.project import CostSpec  # noqa: PLC0415
    from predimrc_wrapper.data import default_propellers  # noqa: PLC0415
    from predimrc_wrapper.propulsion.chain import PowerChain  # noqa: PLC0415
    from predimrc_wrapper.propulsion.wiring import default_layout  # noqa: PLC0415

    project = aircraft.project
    spec = project.cost or CostSpec()
    prices = default_prices()
    over = spec.overrides
    items: list[CostItem] = []

    def priced(category, item, quantity, key, record):
        if key in over:
            items.append(
                CostItem(
                    category, item, quantity, over[key], "project override", "entered"
                )
            )
        elif record is None:
            items.append(
                CostItem(category, item, quantity, None, "no price", "missing")
            )
        else:
            items.append(
                CostItem(
                    category, item, quantity, record.price, record.source, record.status
                )
            )

    motor_ids = [project.propulsion_units[m.unit].motor_id for m in project.motors]
    for motor_id in dict.fromkeys(motor_ids):
        priced(
            "motors",
            motor_id,
            motor_ids.count(motor_id),
            f"motor:{motor_id}",
            prices.motor(motor_id),
        )
    props = []
    for m in project.motors:
        unit = project.propulsion_units[m.unit]
        props.append(
            unit.propeller_id
            or f"{unit.prop_diameter_in:g}x{unit.prop_pitch_in or 0:g}"
        )
    for prop in dict.fromkeys(props):
        n = props.count(prop)
        if prices.propeller(prop) is not None or f"propeller:{prop}" in over:
            priced("propellers", prop, n, f"propeller:{prop}", prices.propeller(prop))
            continue
        # Not a database propeller: price of a database propeller of the same diameter.
        diameter = float(prop.split("x")[0])
        same = [
            (p_id, prices.propeller(p_id))
            for p_id in default_propellers().ids(diameter)
            if prices.propeller(p_id) is not None
        ]
        if not same:
            items.append(
                CostItem(
                    "propellers", f"propeller {prop} in", n, None, "no price", "missing"
                )
            )
            continue
        p_id, record = min(same, key=lambda s: s[1].price)
        items.append(
            CostItem(
                "propellers",
                f"propeller {prop} in (priced as {p_id})",
                n,
                record.price,
                record.source,
                "estimate",
            )
        )

    four_in_one = (
        project.wiring is not None and project.wiring.lift_esc == "four_in_one"
    )
    i_max = [aircraft.db.motor(mid).i_max for mid in motor_ids]
    separate = [
        ESC_MARGIN * i
        for i, m in zip(i_max, project.motors, strict=True)
        if not (four_in_one and m.role != "cruise")
    ]
    chosen: dict[str, tuple[int, object]] = {}
    for need in separate:
        esc = prices.esc(need, four_in_one=False)
        name = esc.name if esc else f"ESC ≥ {need:.0f} A"
        chosen[name] = (chosen.get(name, (0, esc))[0] + 1, esc)
    for name, (n, esc) in chosen.items():
        priced("ESCs", name, n, "esc", esc)
    if four_in_one:
        need = ESC_MARGIN * max(
            i for i, m in zip(i_max, project.motors, strict=True) if m.role != "cruise"
        )
        esc = prices.esc(need, four_in_one=True)
        priced(
            "ESCs", esc.name if esc else f"4-in-1 ESC ≥ {need:.0f} A", 1, "esc4in1", esc
        )

    battery = aircraft.battery
    energy_wh = battery.energy_wh()
    chem = project.battery.chemistry
    priced(
        "battery",
        f"{chem} pack, {energy_wh:.0f} Wh",
        energy_wh,
        "battery_per_wh",
        prices.battery(chem),
    )

    chain = PowerChain.from_project(project, battery, hover_currents_a).p
    layout = default_layout(project)
    metres: dict[int, float] = {}
    metres[chain.main_awg] = (
        metres.get(chain.main_awg, 0.0) + 2 * layout.main_length_mm / 1000
    )
    for b in chain.branches:
        metres[b.dc_awg] = metres.get(b.dc_awg, 0.0) + 2 * b.dc_length_mm / 1000
        metres[b.phase_awg] = (
            metres.get(b.phase_awg, 0.0) + 3 * b.phase_length_mm / 1000
        )
    for awg, length in sorted(metres.items()):
        if length > 0:
            priced(
                "cables",
                f"silicone wire AWG{awg}",
                round(length, 2),
                f"cable:{awg}",
                prices.cable(awg),
            )

    items.extend((
        CostItem(
            "frame",
            "frame (airframe, booms, fuselage)",
            1,
            spec.frame,
            "project",
            "entered",
        ),
        CostItem(
            "avionics",
            "avionics (FC, GPS, receiver)",
            1,
            spec.avionics,
            "project",
            "entered",
        ),
    ))

    hours = flight_time_s / 3600.0
    totals = {i.category: 0.0 for i in items}
    for i in items:
        if i.total is not None:
            totals[i.category] += i.total
    cycles = spec.battery_cycles or DEFAULT_CYCLES[chem]
    per_flight = {
        "battery": totals.get("battery", 0.0) / cycles,
        "motors": totals.get("motors", 0.0) * hours / spec.motor_life_h,
        "propellers": totals.get("propellers", 0.0) / spec.propeller_flights,
    }
    return CostResult(items, prices.currency, flight_time_s, per_flight)
