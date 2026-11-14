# MIC-PROP-BAT — Battery pack (LiPo / Li-ion)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Battery pack, specific-energy and internal-resistance model |
| Model identifier | MIC-PROP-BAT |
| Model description | Energy, mass, maximum current, terminal voltage and current drawn for a terminal power. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** size and compare packs, capturing the energy / power trade-off
  between LiPo and Li-ion.

## Subject information

- **Modelled entity:** a pack of n_s cells in series (and n_p in parallel), wiring and
  packaging included.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `power_w` | P | W | terminal power demanded | ≥ 0 |
| `soc` | s | — | state of charge (optional; nominal voltage without) | [0, 1] |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `current_a` | I | A | pack current | ≥ 0 |
| `voltage_v` | U | V | terminal voltage under load | ≥ 0 |
| `chemical_power_w` | P_c | W | power drawn from the cells, losses included | ≥ 0 |
| `c_rate_margin` | — | — | 1 − I / I_max | — |
| `feasible` | — | — | false when P > V₀² / 4R | — |
| `cutoff_ok` | — | — | terminal cell voltage U / n_s ≥ V_c | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `chemistry` | — | — | cell chemistry: lipo or li-ion | project | — | project |
| `n_series` | n_s | — | cells in series | project | [1, 14] | project |
| `n_parallel` | n_p | — | cells in parallel | 1 | [1, 10] | project |
| `capacity_ah` | C | Ah | pack capacity (given or derived from mass) | project | ≥ 0 | project |
| `mass_kg` | m_b | kg | pack mass (given or derived from capacity) | project | ≥ 0 | project |
| `specific_energy_wh_kg` | e | Wh/kg | pack-level specific energy | chemistry table (150 LiPo / 200 Li-ion) | ≥ 0 | generic data sheets, to confirm |
| `v_full` | V_f | V | full cell voltage | chemistry table (4.2 / 4.2) | ≥ 0 | cell data sheets |
| `v_nominal` | V_n | V | nominal cell voltage | chemistry table (3.7 / 3.6) | ≥ 0 | cell data sheets |
| `v_cutoff` | V_c | V | cut-off cell voltage | chemistry table (3.3 / 2.8) | ≥ 0 | cell data sheets |
| `r_cell_ohm_ah` | r | Ω·Ah | cell resistance × capacity | chemistry table (0.010 / 0.040) | ≥ 0 | generic, to confirm |
| `c_max` | c_max | C | maximum continuous discharge rate | chemistry table (30 / 8) | ≥ 0 | generic data sheets |
| `usable_fraction` | f_u | — | usable fraction of the capacity | chemistry table (0.85 / 0.90) | [0, 1] | engineering practice |
| `ocv_shape` | y(s) | — | open-circuit cell voltage (V − V_c)/(V_f − V_c) versus state of charge | chemistry table | — | generic discharge curves, to confirm |
| `r_low_soc_factor` | k_R | — | internal resistance at 0 % / at ≥ 20 % state of charge | chemistry table (1.5 / 1.5) | ≥ 1 | generic, to confirm |
<!-- interface:end -->

## Implementation

### Modelling choices

- C = m_b·e / (n_s·V_n) (mass mode) or given (capacity mode).
- E = n_s·V_n·C; m_b = E / e; usable energy E_u = 3600·f_u·E.
- R = n_s·r / C; V₀ = n_s·V_n; U(I) = V₀ − R·I.
- Current for a power: R·I² − V₀·I + P = 0, smallest root; P > V₀²/(4R) ⇒ infeasible.
- Chemical power P_c = V₀·I, so Joule losses are counted in the energy.
- I_max = c_max·C.
- State of charge s (optional input), energy-based: s = 1 − E_drawn / E. Open-circuit
  voltage V₀(s) = n_s·(V_c + y(s)·(V_f − V_c)), y the generic discharge curve of the
  chemistry (piecewise linear, y(0) = 0, y(1) = 1); internal resistance R(s) = R·(1 +
  (k_R − 1)·max(0, (0.2 − s)/0.2)). Without s: V₀ = n_s·V_n and R (nominal point).
- `cutoff_ok`: terminal cell voltage U/n_s ≥ V_c.
- Discharge along a flight (`discharge`): stateless, the whole history of terminal powers
  (piecewise constant) is given; ds/dt = −P_c(s)/E integrated with the midpoint rule, 20
  steps per segment.

### Model limitations

- Generic discharge curves (LiPo 3.30 → 4.20 V, Li-ion NMC 2.8 → 4.2 V) and resistance
  factor k_R = 1.5, to confirm on cell data sheets. With a 20 % reserve the LiPo is still
  on its plateau at landing (3.74 V open circuit, above V_n = 3.7 V); the Li-ion is below
  (3.47 V against 3.6 V).
- The state of charge counts energy, not charge: the mean of the curves differs from V_n
  by a few %, so energy and charge counts differ by as much.
- No Peukert, temperature, relaxation or ageing effects.

### Model classification

- `physics.electrical.battery.equivalent_circuit_r`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** capacity → mass → capacity round trip exact; R = 0 ⇒ P_c = P; E ∝ m_b
  and R ∝ n_s/C (model-form tests).
- **Report:** `tests/propulsion/test_battery.py`.

## Traceability

- Requirements: REQ-PROP-001, REQ-PROP-002, REQ-PROP-008, REQ-NFR-006
- Canvas: MVP-003
