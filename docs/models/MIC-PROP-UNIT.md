# MIC-PROP-UNIT — Propulsion unit (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Propulsion unit: ESC (constant efficiency) + motor + propeller |
| Model identifier | MIC-PROP-UNIT |
| Model description | Battery power and feasibility for a thrust; maximum thrust. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** link a thrust demand to the power drawn from the battery and to
  the operating limits.

## Subject information

- **Modelled entity:** an ESC → motor → propeller chain; several identical units can
  share one battery.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `thrust_n` | T | N | thrust of one unit | ≥ 0 |
| `v_axial_m_s` | V | m/s | axial inflow speed | ≥ 0 |
| `rho` | ρ | kg/m³ | air density | ≥ 0 |
| `battery_voltage_v` | U_bat | V | battery voltage under load | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `rpm` | N | rpm | rotation speed | ≥ 0 |
| `shaft_power_w` | P | W | shaft power | ≥ 0 |
| `power_elec_w` | P_el | W | motor electric power | ≥ 0 |
| `battery_power_w` | P_b | W | power drawn from the battery by the unit | ≥ 0 |
| `motor_current_a` | I_m | A | motor current | ≥ 0 |
| `current_margin` | — | — | 1 − I_m / I_max | — |
| `power_margin` | — | — | 1 − P_el / P_max | — |
| `voltage_margin` | — | — | 1 − U_m / (d_max·U_bat) | — |
| `feasible` | — | — | all limits respected | — |
| `limiting` | — | — | first violated limit: motor_current, motor_power, voltage | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `esc_efficiency` | η_esc | — | ESC efficiency (constant in the MVP) | 0.95 | [0, 1] | generic |
| `esc_mass_kg` | m_esc | kg | ESC mass | 0.03 | ≥ 0 | project |
| `max_duty` | d_max | — | maximum duty cycle | 0.95 | [0, 1] | generic |
<!-- interface:end -->

## Implementation

### Modelling choices

- (n, P) = propeller(T, V, ρ); ω = 2πn; Q = P/ω.
- (I_m, U_m, P_el) = motor(Q, ω).
- P_b = P_el / η_esc.
- Feasible if I_m ≤ I_max, P_el ≤ P_max and U_m ≤ d_max·U_bat.
- T_max: bisection on T up to the first limit.

### Model limitations

- Constant ESC efficiency (η_esc(d) comes after the MVP).
- No wiring losses (after the MVP).
- Thrust shared equally between identical units.

### Model classification

- `physics.propulsion.electric_chain`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** P_b ≥ P_el ≥ P ≥ T·V; undersized motor ⇒ `limiting = motor_current`.
- **Report:** `tests/propulsion/test_unit.py`.

## Traceability

- Requirements: REQ-PROP-005, REQ-PROP-006, REQ-PROP-008, REQ-NFR-006
- Canvas: MVP-003
