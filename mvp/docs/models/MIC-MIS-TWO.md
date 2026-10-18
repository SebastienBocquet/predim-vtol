# MIC-MIS-TWO — Two-phase flight time (hover, then cruise at a target speed)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Two-phase flight time of the designer's process |
| Model identifier | MIC-MIS-TWO |
| Model description | Hover power from the moment balance and the thrust–power data, cruise power at two target speeds from PredimRC, flight time with a reserve. |
| Release / date / type | 0.2.0-inc2 / 2026-10-15 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** compute the flight time the way the designer does, so that every
  number can be checked by hand (INC2-007, REQ-MIS-008).

## Subject information

- **Modelled entity:** one flight: hover for t_h, then cruise at V₁ or V₂ until the
  reserve.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `hover_time_s` | t_h | s | hover time | ≥ 0 |
| `target_speeds_m_s` | V_k | m/s | cruise target speeds (None: minimum power, maximum L/D) | — |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `result` | — | — | TwoPhaseResult: hover, cruise per target speed, flight times, margins | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `reserve_fraction` | r | — | energy reserve, fraction of the nominal energy | 0.2 | [0, 0.5] | designer, 2026-10-14 |
| `avionics_power_w` | P_av | W | avionics and payload power | 5.0 | ≥ 0 | project |
| `min_thrust_to_weight` | T/W_min | — | minimum lift thrust-to-weight | 1.5 | ≥ 1 | control authority practice |
<!-- interface:end -->

## Implementation

### Modelling choices

- Hover: T_i = f_i·k_dl·m·g (force and moment balance about the CG,
  `hover_thrust_split`); electric power of each motor from MIC-PROP-SUR at T_i and the
  bus voltage (iterated once); motor current from R·I² + (ω/Kv)·I − P = 0; chain
  MIC-PROP-CHAIN to the cells. Front / rear ratio = Σ T ahead of the CG / Σ T behind.
- Propeller of a unit: its `propeller_id`, else the database propeller of the same
  diameter and pitch, else an untested pair (D, P) — pitch 0.4·D when not given
  (flagged untrusted).
- Cruise (wing-borne): aerodynamic power at V_k from the PredimRC imposed-speed block +
  drag sources (`aircraft/cruise.py`); thrust shared by disc area among cruise and tilt
  motors; MIC-PROP-BEM at the unit pitch (constant η_c when no pitch, flagged); motor
  constants MIC-PROP-MOT; chain. Multicopter: MVP forward-flight model (MIC-MIS-SEG) at
  the best-endurance and best-range speeds.
- Energy: E_avail = (1 − r)·E_nom, r = 20 % of the nominal energy (designer, 2026-10-15);
  powers drawn from the cells (chemical power).
- t_c,k = (E_avail − P_h·t_h) / P_c,k; flight time t_h + t_c,k; range V_k·t_c,k;
  σ_t from the surrogate σ of the hover power (motor errors fully correlated).
- Margins: motor power and current (hover and cruise), hover thrust versus the tested
  maximum, lift T/W (MVP physics), battery C-rate, take-off mass.

### Model limitations

- No climb, descent or transition segments (scenario mode of the MVP for those).
- Cruise uncertainty not propagated (physics models).
- Constant mass, no wind.

### Model classification

- `mission.energy_budget.two_phase`

## Verification and validation

- **Verification status:** flight time equals the formula from the displayed powers
  (model-form test); moments balanced; zero hover ⇒ cruise-only endurance.
- **Validation status:** designer's tricopter: 256 W computed versus 280 W measured in
  hover (−9 %, uncalibrated).
- **Report:** `tests/mission/test_two_phase.py`.

## Traceability

- Requirements: REQ-MIS-008, REQ-CFG-010, REQ-PROP-004, REQ-PROP-005
- Canvas: INC2-007
