# MIC-PROP-SUR — Thrust–power surrogate (physics × Gaussian process)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Thrust–power surrogate of a motor + propeller pair |
| Model identifier | MIC-PROP-SUR |
| Model description | Electric power, supply current and rotation speed at a static thrust, with a standard deviation and a trust flag, from manufacturer thrust tables. |
| Release / date / type | 0.2.0-inc2 / 2026-10-14 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** replace the designer's manual interpolation in thrust–power tables
  for the hover power of each motor, and predict pairs not tested, with an error
  guarantee (INC2-003, REQ-PROP-011).

## Subject information

- **Modelled entity:** one motor + fixed-pitch propeller (+ ESC when the data include it)
  in static conditions.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `thrust_n` | T | N | static thrust of one rotor | ≥ 0 |
| `battery_voltage_v` | U | V | voltage at the ESC / motor input | ≥ 0 |
| `rho` | ρ | kg/m³ | air density | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `power_w` | P | W | electric power at the measurement point of the data | ≥ 0 |
| `power_sd_rel` | σ_rel | — | relative standard deviation of the power | ≥ 0 |
| `current_a` | I | A | current | ≥ 0 |
| `rpm` | N | rpm | rotation speed | ≥ 0 |
| `physics_power_w` | P_phys | W | physics mean of the power | ≥ 0 |
| `trusted` | — | — | inside the trusted domain | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `motor_id` | — | — | motor id | project | — | motor database |
| `propeller_id` | — | — | propeller id, or 'DxP' for a propeller not in the database | project | — | propeller database |
| `diameter_in` | D | in | propeller diameter when not in the database | None | — | project |
| `pitch_in` | P | in | propeller pitch when not in the database | None | — | project |
| `esc_input` | — | — | give the power at the ESC input (data measured there) | False | — | data |
| `max_sd_rel` | s_max | — | largest trusted relative standard deviation | 0.05 | [0, 1] | designer, 2026-10-14 |
<!-- interface:end -->

## Implementation

### Modelling choices

- Physics mean: blade-element propeller (MIC-PROP-BEM) gives rpm and shaft power at T;
  motor constants (MIC-PROP-MOT) give the electric power; P / η_esc (0.95) when the data
  were measured at the ESC input; supply current I = P / U (tables give power = U·I).
- Correction: three Gaussian processes (power, current, rpm) on r = ln(data / physics),
  inputs (ln T, D, P/D, ln Kv, ln U), kernel C·Matérn 5/2 (automatic relevance) + white
  noise, hyperparameters by maximum likelihood (scikit-learn, 3 restarts, seed 0).
- Prediction P = P_phys·exp(μ_r), σ_rel = σ_r, 95 % interval P·exp(±1.96 σ_r).
- Trusted when σ_rel ≤ 5 % (setting) and T ≤ maximum tested thrust (tested pair), or
  inputs within the tested box (untested pair); otherwise flagged with the reason.
- Test density 1.225 kg/m³ assumed (not published by the manufacturers).
- Fit cached in memory by the content hash of the test files.

### Model limitations

- Static thrust only (hover); cruise uses MIC-PROP-BEM.
- Eight shipped pairs (T-Motor MN2212, MN2806, AT2308): untested pairs far from them are
  flagged untrusted.
- Manufacturer tables, test conditions partly unknown (density, ESC).

### Model classification

- `surrogate.gaussian_process.physics_informed_mean`

## Verification and validation

- **Verification status:** model-form tests (tested point within 3σ; σ grows and the flag
  is raised beyond the tested thrust).
- **Validation status (shipped data, 84 points, 8 pairs, 2026-10-14):** leave-one-out
  mean error 0.8 %, max 5.9 %, coverage of the 95 % interval 95.2 %; leave-one-pair-out
  mean error 1.7 %, max 10.7 %, coverage 97.6 %; physics mean alone 4.5 %.
- **Criteria:** LOO mean error ≤ 3 %, LOO coverage in [90 %, 99 %]; physics mean within
  ±25 % of every pair.
- **Report:** `tests/propulsion/test_surrogate.py`, `ThrustPowerFit.validate()`.

## Traceability

- Requirements: REQ-PROP-005, REQ-PROP-011, REQ-PROP-012, REQ-NFR-005
- Canvas: INC2-003
