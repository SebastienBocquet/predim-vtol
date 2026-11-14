# MIC-PROP-PRP — Propeller, momentum theory (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Propeller, momentum theory with figure of merit and constant cruise efficiency |
| Model identifier | MIC-PROP-PRP |
| Model description | Shaft power, torque and rotation speed for a thrust, in hover and in axial cruise. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** give the shaft power and speed needed for a thrust, so that motors
  and propeller diameters can be compared.

## Subject information

- **Modelled entity:** a fixed-pitch RC propeller in axial flow.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `thrust_n` | T | N | required thrust | ≥ 0 |
| `v_m_s` | V | m/s | axial inflow speed (0 in hover) | ≥ 0 |
| `rho` | ρ | kg/m³ | air density | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `n_rev_s` | n | rev/s | rotation speed | ≥ 0 |
| `shaft_power_w` | P | W | shaft power | ≥ 0 |
| `torque_nm` | Q | N·m | P / (2πn) | ≥ 0 |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `diameter_m` | D | m | propeller diameter | project (inches) | ≥ 0 | project |
| `mass_kg` | m_p | kg | propeller mass | project | ≥ 0 | project |
| `figure_of_merit` | FM | — | hover figure of merit | 0.65 | [0, 1] | RC propeller literature |
| `static_ct` | CT₀ | — | static thrust coefficient (speed estimate) | 0.1 | ≥ 0 | generic |
| `cruise_efficiency` | η_c | — | propulsive efficiency in cruise | 0.7 | [0, 1] | generic |
<!-- interface:end -->

## Implementation

### Modelling choices

- Hover (V = 0): A = πD²/4; P = T^1.5 / (FM·√(2ρA)); n = √(T / (CT₀·ρ·D⁴)).
- Cruise (V > 0): P = T·V / η_c; n from the hover formula (estimate only).
- Q = P / (2πn).

### Model limitations

- No CT/CP tables: propeller pitch and the variation of efficiency with speed are not
  represented (tables come after the MVP).
- Speed in cruise is only an estimate, used for the motor operating point.
- Tip Mach not checked.

### Model classification

- `physics.aerodynamics.rotor.momentum_theory`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** FM = 1 ⇒ ideal momentum power to 1e-9; P ∝ T^1.5, ρ^−0.5, D^−1
  (model-form tests).
- **Report:** `tests/propulsion/test_propeller.py`, `tests/model_forms/`.

## Traceability

- Requirements: REQ-PROP-004, REQ-PROP-005, REQ-NFR-006
- Canvas: MVP-003
