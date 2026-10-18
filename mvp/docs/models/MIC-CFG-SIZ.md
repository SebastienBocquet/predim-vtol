# MIC-CFG-SIZ — Motor power law (pre-selection)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Hover power law and motor power needed |
| Model identifier | MIC-CFG-SIZ |
| Model description | Hover battery power versus take-off mass, fitted on a reference aircraft, and power each lift motor must deliver at the minimum thrust-to-weight. |
| Release / date / type | 0.1.0-mvp / 2026-10-13 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** narrow the motor choice to a power range from a target mass range,
  before any detailed evaluation (Sizing tab, `sizing.motor_power_ranges`).

## Subject information

- **Modelled entity:** the hover power of a multirotor or VTOL aircraft and its share per
  lift motor.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `mass_kg` | m | kg | take-off mass | ≥ 0 |
| `power_share` | s_i | — | share of the hover power taken by the motor | [0, 1] |
| `thrust_to_weight` | T/W | — | thrust-to-weight to deliver | ≥ 1 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `hover_power_w` | P_h | W | hover battery power of the aircraft | ≥ 0 |
| `motor_power_w` | P_i | W | power the motor must deliver | ≥ 0 |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `reference_mass_kg` | m_ref | kg | mass of the reference aircraft | 1.87 | ≥ 0 | user tricopter, 2026-10-13 |
| `reference_hover_power_w` | P_ref | W | measured hover battery power of the reference | 280.0 | ≥ 0 | user tricopter, 2026-10-13 |
| `mass_exponent` | k | — | 1: propellers grow with the aircraft; 1.5: same propellers | 1.0 | [0, 2] | momentum theory |
<!-- interface:end -->

## Implementation

### Modelling choices

- P_h = P_ref·(m / m_ref)^k, default reference: tricopter of 1.87 kg, 12 in propellers at
  the front and 10 in at the rear, 280 W measured in hover (≈ 150 W/kg).
- k = 1 when the propellers grow with the aircraft (constant disc loading per kg),
  k = 1.5 with the same propellers (momentum theory, P ∝ T^1.5).
- Share of a lift motor: s_i ∝ T_i^1.5 / √A_i, T_i from the hover thrust split
  (CG balance, or disc areas without CG).
- Lift motor: P_i = s_i·P_h·(T/W_min)^1.5 (power at full thrust at fixed propeller).
- Cruise motor of a wing-borne aircraft (in `motor_power_ranges`): P_c = m·g·V_max /
  ((L/D)·η), shared by disc area; tilting motor: the larger of both.
- Accepted range of a unit type: [min P_i at m_min; headroom·max P_i at m_max],
  headroom 1.3 by default.

### Model limitations

- One reference point; the law ignores the disc loading and the efficiency of the actual
  propellers and motors (pre-selection only, the mission solver checks the limits).
- Battery power compared with the motor electric power: slightly conservative (ESC
  losses).

### Model classification

- `empirical.scaling_law`

## Verification and validation

- **Verification status:** model-form tests.
- **Validation status:** one reference point (user tricopter).
- **Criteria:** reference point reproduced exactly; P_h ∝ m^k; P_i ∝ (T/W)^1.5.
- **Report:** `tests/test_sizing_calibration.py`, `tests/model_forms/`.

## Traceability

- Requirements: user feedback of 2026-10-13 (motor power range from the target mass)
- Canvas: to write (specs updated once the code is stable)
