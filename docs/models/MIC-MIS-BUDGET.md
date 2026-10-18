# MIC-MIS-BUDGET — Power budget (power sinks per phase)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Power budget of the two-phase flight |
| Model identifier | MIC-MIS-BUDGET |
| Model description | Split of the battery chemical power into its sinks (useful aerodynamic power, propeller, motor, ESC, cables, battery, avionics) in hover and at each target speed. |
| Release / date / type | 0.3.0-inc3 / 2026-10-18 / post-processing (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** show where the energy goes, to tell which component to improve first
  (Results tab, `mission.power_budget`).

## Subject information

- **Modelled entity:** the power flow from the cells to the air, per phase.

## Interface

### Inputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| two-phase result | — | — | hover and cruise operating points with their power chains (MIC-MIS-TWO) |
| aircraft | — | — | air density, disc areas, motor constants (K_v, R_m, I₀) |

### Outputs

| Name | Symbol | Unit | Description |
|---|---|---|---|
| sinks per phase | P_k | W | power of each sink in hover, at V₁ and at V₂ |
| closure | — | W | chemical power − Σ sinks (0 for a complete budget) |

## Implementation

### Modelling choices

1. Useful aerodynamic power: hover, ideal induced power Σ T_i^1.5 / √(2ρA_i) (momentum
   theory); cruise, Σ T_i·V = D·V.
2. Motor losses: hover, I²R_m + I₀·rpm / K_v at the operating current and speed (MIC-PROP-MOT);
   cruise, motor input − shaft power of the blade-element propeller.
3. Propeller losses: shaft power − useful power (the rest of the rotor power: profile,
   non-uniform inflow, swirl).
4. ESC, main / DC / phase cables, battery internal: segments of the power chain
   (MIC-PROP-CHAIN). The ESC loss is listed even when the test data were measured at the
   ESC input (it is then inside the data, not added twice).
5. Multicopter cruise (forward-flight model MIC-MIS-SEG): rotors in forward flight
   (shaft − D·V), motors + ESC + cables together (terminal − shaft − avionics), battery
   internal (chemical − terminal).

### Limitations

- The hover motor losses come from the motor constants while the hover power comes from the
  test data through the surrogate: the propeller term absorbs the difference.

## Verification and validation

- **Criteria:** Σ sinks = chemical power to 1e-9 relative for every template and phase.
- **Report:** `tests/mission/test_power_budget.py`.

## Traceability

- Requirements: REQ-MIS-009
- Canvas: INC3-002
