# MIC-COST — Purchase cost and cost of use

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Purchase cost and wear cost of an aircraft |
| Model identifier | MIC-COST |
| Model description | Purchase cost from a price list with provenance, and wear cost per flight and per flight hour (battery cycles, motor life, propeller replacements). |
| Release / date / type | 0.3.0-inc3 / 2026-10-18 / cost model (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** compare configurations on price and cost of use (Cost and reliability
  tab, discipline outputs `cost_purchase`, `cost_per_hour`; `cost/model.py`).

## Subject information

- **Modelled entity:** the bill of materials of the propulsion and power chain, plus the
  frame and avionics entered by the user.

## Interface

### Inputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| project | — | — | motors, propellers, ESC topology, battery, wiring (`Project`) |
| `cost` | — | — | frame and avionics prices, overrides, wear settings (`CostSpec`) |
| flight time | t | s | two-phase flight time at V₁ (MIC-MIS-TWO) |
| hover currents | I_i | A | gauges of the cables (MIC-PROP-CHAIN), 10 A when not given |

### Outputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| items | — | USD | priced items with quantity, unit price, source and status |
| purchase | C_p | USD | Σ priced items |
| per flight | C_f | USD | wear cost of one flight |
| per hour | C_h | USD/h | C_f / t |

### Parameters

| Name | Default | Source |
|---|---|---|
| price list | `data/prices.yaml` | manufacturer and retailer pages, 2026-10-18 (URL per price) |
| ESC margin | 1.25 × I_max of the motor | rule of thumb |
| battery cycles | 300 (LiPo), 500 (Li-ion) | typical RC cycle life at 80 % capacity |
| motor life | 1000 h | order of magnitude of bearing life of RC brushless motors |
| propeller flights | 200 | assumption (wear, small damage) |

## Implementation

### Modelling choices

1. Motors: price of the motor id, one per motor slot.
2. Propellers: price of the database propeller of the unit type; a propeller given only by
   diameter and pitch takes the cheapest database propeller of the same diameter (status
   "estimate"); pair prices halved.
3. ESCs: separate, the cheapest rating ≥ 1.25 × I_max of the motor; 4-in-1 lift ESC, one
   board whose rating ≥ 1.25 × the largest lift-motor I_max, plus a separate ESC per cruise
   motor.
4. Battery: price per Wh of the chemistry (one retail pack each) × nominal energy.
5. Cables: conductor lengths of the power chain (main 2, DC 2, phase 3 conductors) × price
   per metre of the gauge.
6. Wear per flight: C_f = P_battery / N_cycles + Σ P_motor · t / L_motor + Σ P_prop / N_flights.
7. An item without a price is listed as "missing" and left out of the total, never 0.

### Limitations

- Retail prices of one date and one currency (USD, no conversion), taxes and shipping
  excluded; some prices read in search results (status "search").
- No connectors, servos, labour; frame and avionics as entered.

## Verification and validation

- **Criteria:** total = Σ items; an override replaces the database price; wear formula on a
  hand case.
- **Report:** `tests/test_cost_reliability.py`.

## Traceability

- Requirements: REQ-COST-001, REQ-COST-002
- Canvas: INC3-004
