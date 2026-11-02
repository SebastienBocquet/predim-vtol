# MIC-CAL-REF — Calibration on measured reference points

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Calibration on measured hover and cruise battery power |
| Model identifier | MIC-CAL-REF |
| Model description | Procedure setting one model factor per measured point so that the evaluation reproduces the measured battery power. |
| Release / date / type | 0.1.0-mvp / 2026-10-13 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

Procedure, not a model class: it calls MIC-MIS-TWO on modified copies of the project
(`predimrc_wrapper.calibration.calibrate_two_phase`). No generated Interface section.

## Purpose and objectives

- **Purpose:** anchor the pre-sizing on flight measurements of an existing aircraft
  before exploring variants (Calibration tab, `calibration` block of the project).

## Subject information

- **Calibrated entity:** the reference configuration of the project, at the measured
  mass.

## Interface

| Input | Unit | Meaning |
|---|---|---|
| `calibration.hover.battery_power_w` | W | measured battery power in hover |
| `calibration.hover.mass_kg` | kg | mass during the measurement (project mass by default) |
| `calibration.cruise.speed_m_s` | m/s | airspeed of the cruise measurement |
| `calibration.cruise.battery_power_w` | W | measured battery power in cruise |
| `calibration.cruise.mass_kg` | kg | mass during the measurement (project mass by default) |

| Output | Meaning |
|---|---|
| calibrated project | `mission.hover_power_factor` and `mission.drag_factor` replaced |
| report (per point) | measured, model before, model after, parameter, values before and after, factor, note |

## Implementation

### Modelling choices

1. Hover point → `mission.hover_power_factor` k_h, multiplier of the motor powers read
   in the thrust–power test data (bounds 0.5–2).
2. Cruise point, after the hover factor → `mission.drag_factor` k_D, multiplier of the
   total cruise drag (bounds 0.2–5). The propeller (blade elements at its pitch) and the
   motor are physics models: the residual goes to the least known term, the drag.
3. Each factor solves model(k) = measured by Brent's method (monotonic residual); a factor at
   its bound is reported in `note`: the measurement is outside what the model can
   represent, check the masses, motor and battery inputs.
4. The calibration describes the reference configuration: `evaluate_two_phase`
   calibrates the project itself; the MDO discipline calibrates the base project once and its variants
   reuse the factors.

### Limitations

- One point per factor: drag and propeller efficiency cannot be separated with a single
  cruise point; the residual is put on the drag.
- Battery power measured at the pack terminals assumed (avionics power included in the
  model).

## Verification and validation

- **Criteria:** model after calibration equals the measurement to 1e-6; the cruise factor
  leaves the hover point unchanged; out-of-range measurement reported.
- **Report:** `tests/test_sizing_calibration.py`.

## Traceability

- Requirements: user feedback of 2026-10-13 (hover and cruise reference points)
- Canvas: to write (specs updated once the code is stable)
