# MIC-CFG-MASS — Mass budget (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Mass budget |
| Model identifier | MIC-CFG-MASS |
| Model description | Total mass and breakdown from user items and chosen components; maximum-mass margin. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** close the total mass that drives every power computation.

## Subject information

- **Modelled entity:** the mass of the complete aircraft.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `mass_items` | m_i | kg | user items as (category, mass) pairs | — |
| `propulsion_items` | m_u,j | kg | motor + propeller + ESC mass of each motor, as (category, mass) pairs | — |
| `battery_mass_kg` | m_b | kg | battery mass (MIC-PROP-BAT) | ≥ 0 |
| `max_takeoff_mass_kg` | m_max | kg | optional maximum take-off mass | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `total_kg` | m | kg | total mass | ≥ 0 |
| `breakdown` | — | kg | mass per category | — |
| `margin_mass` | — | — | 1 − m / m_max (NaN without m_max) | — |

### Parameters

None.
<!-- interface:end -->

## Implementation

### Modelling choices

- m = Σ m_i + Σ_motors (m_m + m_p + m_esc)_j + m_b, one propulsion unit per motor; a
  tilting motor counts once (category "tilt propulsion").
- margin_mass = 1 − m / m_max.

### Model limitations

- Structure masses are user inputs (no structural sizing).
- Wiring and fixtures are user items.

### Model classification

- `engineering.mass_budget`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** total = exact sum; no double counting; m > m_max ⇒ negative margin.
- **Report:** `tests/aircraft/test_mass.py`.

## Traceability

- Requirements: REQ-CFG-003, REQ-CFG-009, REQ-NFR-006
- Canvas: MVP-004
