# MIC-MIS-SOL — Mission integration and optimal speeds (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Mission integration, optimal speeds and margins |
| Model identifier | MIC-MIS-SOL |
| Model description | Flight time, range, energy per segment, best-endurance and best-range speeds and margins for one scenario. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** give the outputs of interest of the tool for one scenario.

## Subject information

- **Modelled entity:** one mission of the aircraft with a given battery.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `scenario` | — | — | list of segments | — |
| `scenario_name` | — | — | name of the scenario | — |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `flight_time_s` | t | s | total flight time | ≥ 0 |
| `range_m` | x | m | distance flown | ≥ 0 |
| `v_endurance` | V_e | m/s | best-endurance speed | ≥ 0 |
| `v_range` | V_r | m/s | best-range speed | ≥ 0 |
| `margins` | — | — | motor current, motor power, voltage, battery C, thrust-to-weight, mass | — |
| `feasible` | — | — | scenario feasible with the reserve | — |
| `result` | — | — | full MissionResult (per-segment table, sweep, mass) | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `reserve_fraction` | r | — | energy reserve | 0.2 | [0, 0.5] | practice |
| `stall_margin` | k_s | — | minimum cruise speed / minimum polar speed | 1.2 | ≥ 1 | practice |
| `speed_step` | ΔV | m/s | speed sweep step | 0.25 | ≥ 0 | numerical |
| `min_thrust_to_weight` | T/W_min | — | minimum lift thrust-to-weight | 1.5 | ≥ 1 | control authority practice |
<!-- interface:end -->

## Implementation

### Modelling choices

- E_k = P_c,k·t_k (chemical power from MIC-PROP-BAT); t_k = d/V or Δh/V_z or duration.
- Available energy E_u·(1 − r); an `until_reserve` segment lasts
  (E_avail − Σ E_others) / P_c, keeping the energy of the segments that follow.
- Speed sweep V ∈ [k_s·V_min; feasible V_max] (multicopter from 1 m/s);
  V_e = argmin P_b(V), V_r = argmin P_b(V)/V, parabolic refinement.
- Margins: worst case over segments; T/W margin = n·T_max/(m·g) − T/W_min.

### Model limitations

- Quasi-steady, no wind, constant mass.
- No battery sizing, no trim, no imposed-speed envelope margin (after the MVP).

### Model classification

- `analysis.mission.energy_integration`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** Σ E_k = energy used (1e-9); reserve never consumed; parabolic polar with
  constant efficiencies ⇒ V_r / V_e = 3^0.25 within the grid step.
- **Report:** `tests/mission/test_solver.py`.

## Traceability

- Requirements: REQ-MIS-001, REQ-MIS-002, REQ-MIS-003, REQ-MIS-004, REQ-MIS-005,
  REQ-PROP-008, REQ-NFR-006
- Canvas: MVP-005
