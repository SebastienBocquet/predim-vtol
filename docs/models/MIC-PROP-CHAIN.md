# MIC-PROP-CHAIN — Power chain battery – cables – ESC – cables – motors

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Power chain with cable, ESC and battery losses |
| Model identifier | MIC-PROP-CHAIN |
| Model description | Power entering and loss of each segment from the battery to the motors, at one operating point. |
| Release / date / type | 0.2.0-inc2 / 2026-10-14 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** turn the motor input powers (surrogate or motor model) into the
  battery power, and show where the power is lost (INC2-004, REQ-PROP-009).

## Subject information

- **Modelled entity:** battery, main cable and connector, DC branch cables, ESCs (separate
  or 4-in-1), phase cables, of one aircraft.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `motor_power_w` | P_m,i | W | electric power at each motor input (or at each ESC input for esc_input data) | ≥ 0 |
| `motor_current_a` | I_m,i | A | motor (phase-side) current of each motor | ≥ 0 |
| `esc_input` | — | — | per motor: the power is measured at the ESC input | — |
| `avionics_power_w` | P_av | W | avionics and payload power on the bus | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `result` | — | — | ChainResult: segments, battery power, voltages, currents | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `branches` | — | — | per motor: cable lengths and gauges, ESC efficiency | project wiring + geometry | — | project |
| `main_length_mm` | L_main | mm | main cable length, battery rear → distribution | geometry | ≥ 0 | project |
| `main_awg` | — | AWG | main cable gauge | project or motor maximum current | — | project |
| `connector_mohm` | R_conn | mΩ | battery connector resistance | 0.5 | ≥ 0 | XT60-class connector, generic |
| `wire_temperature_c` | T_w | °C | wire temperature | 40.0 | — | generic |
| `battery` | — | — | battery model (MIC-PROP-BAT) | project | — | project |
<!-- interface:end -->

## Implementation

### Modelling choices

- Copper resistance ρ(T) = 1.72e-8·(1 + 0.00393·(T − 20)) Ω·m, R = ρL/A, AWG area
  from d = 0.127 mm·92^((36 − n)/39).
- Gauges (INC3-006): entered, else the smallest wire rated for 1.25 × the maximum current
  I_max of the motor (data sheet) for its DC and phase cables, and for 1.25 × max(Σ I_max of
  the lift motors, Σ I_max of the cruise motors) for the main cable: the cables as
  installed, the same at every operating point (losses, mass, cost).
- Phase cables: DC-equivalent loss I_m²·2R_phase with the motor current I_m (larger than
  the supply current at part throttle: the ESC lowers the average voltage).
- ESC: constant efficiency of the propulsion unit (MVP model, default 0.95); for data
  measured at the ESC input, the ESC loss is shown as part of the data.
- DC branch and main cable: supply-side currents I = P / U_bus, 2 conductors; connector
  resistance on the main cable (default 0.5 mΩ).
- Battery: MIC-PROP-BAT, terminal voltage under load; bus voltage by fixed point.
- Default lengths from the geometry (`propulsion/wiring.py`): main cable from the rear
  of the battery (nose of a quadplane, centred on a rotary frame) to the distribution
  point (4-in-1 board, or wing spar / frame centre); separate lift ESCs at % of the arm
  (multicopter, tricopter) or at % of the fuselage (quadplane); cruise ESC at % of the
  fuselage; quadplane paths along the fuselage, the wing and the boom. Gauges from the
  current (ampacity × 1.25 margin) unless entered.

### Model limitations

- No ESC loss model versus duty cycle (REQ-PROP-010), no switching losses.
- Phase loss with a DC-equivalent current (RMS of the trapezoidal phase current not
  modelled).
- Avionics on the bus at the bus voltage.

### Model classification

- `physics.electrical.dc_network`

## Verification and validation

- **Verification status:** model-form tests (energy balance closes; zero lengths and ideal
  components give no loss).
- **Validation status:** not started.
- **Report:** `tests/propulsion/test_chain.py`, `tests/model_forms/`.

## Traceability

- Requirements: REQ-PROP-009
- Canvas: INC2-004
