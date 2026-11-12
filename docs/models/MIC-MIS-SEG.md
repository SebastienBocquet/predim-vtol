# MIC-MIS-SEG — Segment powers (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Battery power per flight segment |
| Model identifier | MIC-MIS-SEG |
| Model description | Battery power of hover, vertical, transition, cruise and loiter segments for quadplane and multicopter. |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** turn a segment and a speed into a battery power and its limits.

## Subject information

- **Modelled entity:** the aircraft in quasi-steady flight.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `kind` | — | — | hover, vertical_climb, vertical_descent, transition, cruise, loiter | — |
| `v_m_s` | V | m/s | airspeed (cruise, loiter) | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `battery_power_w` | P_b | W | total battery power | ≥ 0 |
| `battery_current_a` | I | A | battery current | ≥ 0 |
| `chemical_power_w` | P_c | W | power drawn from the cells (MIC-PROP-BAT) | ≥ 0 |
| `shaft_power_w` | P_s | W | total shaft power of the running propellers | ≥ 0 |
| `margins` | — | — | motor current, motor power, voltage, battery C-rate margins (worst motor) | — |
| `feasible` | — | — | all limits respected | — |
| `limiting` | — | — | first violated limit, if any | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `transition_factor` | κ_tr | — | transition power / hover power | 1.0 | ≥ 0 | conservative assumption |
| `avionics_power_w` | P_av | W | avionics and payload power | 5.0 | ≥ 0 | project |
| `download_factor` | k_dl | — | hover thrust / weight (1.05 quadplane, 1.0 multicopter when None) | None | — | quadplane practice |
<!-- interface:end -->

## Implementation

### Modelling choices

- Motors listed one by one, each with its propulsion unit type (heterogeneous motors
  and propellers) and its role: lift, cruise or tilt (both).
- Hover thrust split f_i of the lift and tilt rotors: minimum of Σ T_i²/A_i under the
  vertical force balance and, with a CG, the pitch and roll moment balances; in
  proportion to the disc areas without CG. A negative thrust (CG outside the rotors) is
  an error.
- Hover, vertical climb, vertical descent (MVP): T_i = f_i·k_dl·m·g;
  P_b = Σ UNIT_i(T_i, 0) + P_av; margins are the worst over the motors.
- Transition: κ_tr·P_hover.
- Wing-borne cruise / loiter: T = D(V) shared by disc area among the cruise and tilt
  motors; lift-only rotors at 0 W; P_b = Σ UNIT_j(T_j, V) + P_av.
- Multicopter cruise / loiter: tan α = D/(m·g); T_i = f_i·√((mg)² + D²);
  v_h,i = √(T_i/(2ρA_i)); v_i = v_h² / √((V·cos α)² + (V·sin α + v_i)²) by fixed point;
  P_i = κ·T_i·v_i + T_i·V·sin α + P_0,i·(1 + K·μ²), then motor and ESC. The hover power
  T_i·v_h,i/FM_i is split into the induced power κ·T_i·v_h,i and the profile power
  P_0,i = T_i·v_h,i·(1/FM_i − κ); μ = V·cos α/(Ω_i·R_i), Ω_i at the hover rotation speed
  for T_i. κ = 1.15 (capped at 1/FM_i so that P_0 ≥ 0) and K = 4.65 are constants of the
  model (rotorcraft literature). T_i·V·sin α sums to D·V. At V = 0, P_i is the hover power.
  Dividing the whole power by FM (earlier versions) scaled the profile power down with v_i and
  overstated the power saved in cruise (−35 % instead of about −25 % at V1 for the
  `multicopter` template).
- D includes `mission.drag_factor` (1 unless calibrated, MIC-CAL-REF).

### Model limitations

- Vertical climb and descent at hover power (momentum-theory climb after the MVP).
- No transition dynamics, no vortex ring state, no wind, constant mass.
- Multicopter forward flight by Glauert momentum theory, κ and P_0 from the hover FM:
  κ constant with speed, no rotor-rotor interference (rear rotors in the wake of the front
  ones), rotation speed of the static propeller for μ.

### Model classification

- `physics.flight_mechanics.quasi_steady`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** multicopter at V = 0 ≡ hover (equality to 1e-9).
- **Report:** `tests/mission/test_powers.py`.

## Traceability

- Requirements: REQ-PROP-005, REQ-PROP-006, REQ-MIS-002, REQ-CFG-006, REQ-NFR-006
- Canvas: MVP-005
