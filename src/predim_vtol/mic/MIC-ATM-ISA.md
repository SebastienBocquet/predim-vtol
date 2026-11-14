# MIC-ATM-ISA — ISA atmosphere

## Administrative data

| Attribute | Value |
|---|---|
| Model name | ISA atmosphere (troposphere) |
| Model identifier | MIC-ATM-ISA |
| Model description | Air density from pressure altitude and temperature offset to ISA. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** provide the air density used by every rotor and drag computation.

## Subject information

- **Modelled entity:** the atmosphere at flight altitude.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `altitude_m` | h | m | pressure altitude | [0, 11000] |
| `delta_isa_k` | ΔT | K | temperature offset to ISA | [-40, 40] |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `density` | ρ | kg/m³ | air density | ≥ 0 |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `t0` | T₀ | K | sea-level temperature | 288.15 | ≥ 0 | ISO 2533 |
| `p0` | p₀ | Pa | sea-level pressure | 101325.0 | ≥ 0 | ISO 2533 |
| `lapse_rate` | L | K/m | temperature lapse rate | 0.0065 | ≥ 0 | ISO 2533 |
| `r_air` | R | J/(kg·K) | gas constant of air | 287.053 | ≥ 0 | ISO 2533 |
<!-- interface:end -->

## Implementation

### Modelling choices

- T = T₀ − L·h + ΔT
- p = p₀ · (1 − 2.25577·10⁻⁵·h)^5.25588
- ρ = p / (R·T)

### Model limitations

- Troposphere only; humidity neglected.

### Model classification

- `physics.atmosphere.isa`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** ρ(0, 0) = 1.2250 ± 0.0005 kg/m³; ρ(1000 m, 0) = 1.1117 ± 0.001 kg/m³;
  ρ decreasing with h and ΔT (model-form test).
- **Report:** `tests/propulsion/test_atmosphere.py`.

## Traceability

- Requirements: REQ-PROP-005, REQ-NFR-002, REQ-NFR-006
- Canvas: MVP-003
