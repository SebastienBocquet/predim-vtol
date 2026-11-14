# MIC-PROP-MOT — Brushless motor, 3-constant model

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Brushless DC motor, Kv–R_m–I₀ model |
| Model identifier | MIC-PROP-MOT |
| Model description | Current, voltage, electric power and efficiency for a required torque and speed. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** compute the electrical operating point and margins of lift and
  cruise motors from published constants.

## Subject information

- **Modelled entity:** an outrunner brushless motor driven by an ESC (ESC excluded).

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `torque_nm` | Q | N·m | torque required by the propeller | ≥ 0 |
| `omega_rad_s` | ω | rad/s | rotation speed | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `current_a` | I | A | motor current | ≥ 0 |
| `voltage_v` | U | V | equivalent DC motor voltage | ≥ 0 |
| `power_elec_w` | P_el | W | electric input power | ≥ 0 |
| `efficiency` | η_m | — | Q·ω / P_el | [0, 1] |
| `current_margin` | — | — | 1 − I / I_max | — |
| `power_margin` | — | — | 1 − P_el / P_max | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `kv` | Kv | rpm/V | speed constant | database | ≥ 0 | manufacturer data sheet |
| `r_m` | R_m | Ω | phase-to-phase winding resistance | database | ≥ 0 | manufacturer data sheet |
| `i0` | I₀ | A | no-load current | database | ≥ 0 | manufacturer data sheet |
| `i_max` | I_max | A | maximum current | database | ≥ 0 | manufacturer data sheet |
| `p_max` | P_max | W | maximum power | database | ≥ 0 | manufacturer data sheet |
| `mass_kg` | m_m | kg | motor mass with cables | database | ≥ 0 | manufacturer data sheet |
<!-- interface:end -->

## Implementation

### Modelling choices

- Kv_SI = Kv·π/30 (rad/s/V); K_t = 1/Kv_SI (K_t = K_e).
- I = Q·Kv_SI + I₀.
- U = ω/Kv_SI + R_m·I.
- P_el = U·I; η_m = Q·ω / P_el.

### Model limitations

- Constant I₀ (it actually grows with speed); cold R_m; no explicit iron losses.
- Expected accuracy ±10 % between 30 and 90 % throttle; poor below 20 %.

### Model classification

- `physics.electrical.motor.bldc_3_constants`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** Q = 0 ⇒ I = I₀; I affine in Q; η_m < 1 (model-form tests).
- **Report:** `tests/propulsion/test_motor.py`.

## Traceability

- Requirements: REQ-PROP-003, REQ-PROP-008, REQ-DATA-001, REQ-NFR-006
- Canvas: MVP-003
