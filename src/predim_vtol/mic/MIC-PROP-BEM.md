# MIC-PROP-BEM — Propeller, blade elements with momentum inflow

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Fixed-pitch propeller, blade-element momentum theory |
| Model identifier | MIC-PROP-BEM |
| Model description | Thrust, torque, power and efficiency of a fixed-pitch propeller versus rotation speed and axial speed, with its pitch. |
| Release / date / type | 0.1.0-mvp / 2026-10-13 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** compare propeller pitches for a motor, in hover and versus the
  cruise speed (pitch study of the GUI). Not used by the mission solver yet, which keeps
  MIC-PROP-PRP.

## Subject information

- **Modelled entity:** a fixed-pitch RC propeller of constant geometric pitch in axial
  flow.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `n_rev_s` | n | rev/s | rotation speed | ≥ 0 |
| `v_m_s` | V | m/s | axial inflow speed | ≥ 0 |
| `rho` | ρ | kg/m³ | air density | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `thrust_n` | T | N | thrust (negative when windmilling) | — |
| `shaft_power_w` | P | W | shaft power | — |
| `torque_nm` | Q | N·m | shaft torque | — |
| `ct` | C_T | — | T / (ρn²D⁴) | — |
| `cp` | C_P | — | P / (ρn³D⁵) | — |
| `efficiency` | η | — | T·V / P (0 in hover) | — |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `diameter_m` | D | m | propeller diameter | project (inches) | ≥ 0 | project |
| `pitch_m` | P | m | geometric pitch (constant along the blade) | project (inches) | ≥ 0 | project |
| `n_blades` | B | — | number of blades | 2 | [1, 8] | project |
| `chord_ratio_75` | c₇₅ | — | chord / radius at 0.75 R | 0.14 | [0, 1] | typical RC propellers |
| `chord_slope` | s | — | chord taper: c/R = c₇₅·(1 + s·(0.75 − r/R)) | 1.0 | ≥ 0 | typical RC propellers |
| `hub_ratio` | r_h/R | — | hub radius / radius | 0.15 | [0, 1] | generic |
| `cl_alpha` | a | 1/rad | section lift slope (low Reynolds) | 5.7 | ≥ 0 | thin aerofoil, Reynolds-reduced |
| `alpha_zero_lift` | α₀ | rad | zero-lift angle (cambered section) | -0.1 | — | set to match UIUC APC 10x4.7SF static data |
| `cl_max` | c_l,max | — | section stall lift coefficient | 1.1 | — | low-Reynolds aerofoils |
| `cl_min` | c_l,min | — | section negative stall lift coefficient | -0.5 | — | low-Reynolds aerofoils |
| `cd0` | c_d0 | — | section profile drag at zero lift | 0.025 | ≥ 0 | low-Reynolds aerofoils |
| `cd_k` | k | — | section drag rise with c_l² | 0.02 | ≥ 0 | low-Reynolds aerofoils |
| `cd_stall` | c_d,s | 1/rad | drag rise per radian beyond stall | 0.5 | ≥ 0 | fitted on the 8 shipped manufacturer thrust tables (2026-10-14) |
| `n_stations` | N_r | — | number of radial stations | 24 | ≥ 4 | numerical |
<!-- interface:end -->

## Implementation

### Modelling choices

- Radial stations r ∈ [r_h, R]; θ = atan(P / 2πr); φ = atan((V + v_i) / ωr); α = θ − φ.
- c_l = clip(a·(α − α₀), c_l,min, c_l,max); c_d = c_d0 + k·c_l² + c_d,s·Δα beyond stall.
- Local induced velocity from ½ρW²Bc(c_l·cos φ − c_d·sin φ) = 4πρr(V + v_i)·v_i·F,
  Prandtl tip loss F, solved per station by a bracketed regula falsi (Illinois, relative
  tolerance 1e-12); v_i = 0 where the blade gives no thrust (windmilling).
- Rotation speed for a thrust (`n_for_thrust`): static (V = 0), closed form
  n = √(T / (ρ C_T0 D⁴)), C_T0 from one evaluation at 100 rev/s. Exact for this model: with
  no Reynolds or Mach effect, doubling n doubles every velocity of a station and keeps its
  velocity triangle, so C_T does not depend on n (T ∝ n²). In forward flight, n_max halved
  while T(n) ≥ T (propulsive branch, the thrust dips below its n = 0 value), then the same
  regula falsi in the bracket. 0 when T is reached at rest, NaN above n_max.
- T = ∫dT; Q = ∫½ρW²Bc(c_l·sin φ + c_d·cos φ)·r dr; P = Q·ω; η = T·V / P.
- Chord c/R = c₇₅·(1 + s·(0.75 − r/R)).
- Post-stall drag c_d,s = 0.5 fitted on the 8 shipped manufacturer thrust tables
  (static power within 14 % for every pair, 5.7 % on average, 2026-10-14).
- Other defaults set to match the order of magnitude of the UIUC APC 10x4.7SF data
  (static C_T ≈ 0.11, C_P ≈ 0.045, η_max ≈ 0.65 near J ≈ 0.5).

### Model limitations

- Generic section and chord: absolute values within about ±20 %; to calibrate on a
  bench test or on manufacturer tables.
- Swirl (tangential induction), Reynolds and tip Mach effects neglected.
- Axial flow only (no edgewise flight).

### Model classification

- `physics.aerodynamics.rotor.blade_element_momentum`

## Verification and validation

- **Verification status:** model-form tests.
- **Validation status:** not started.
- **Criteria:** T ∝ n² and P ∝ ρ at V = 0; static C_T, C_P of a 10x4.5 in the RC range;
  zero thrust between 0.9 and 1.6 times the pitch speed n·P (about 1.5 for a 10x4.5 with
  the default camber); higher pitch more efficient
  at speed and less in hover.
- **Report:** `tests/propulsion/test_propulsion.py`, `tests/model_forms/`.

## Traceability

- Requirements: user feedback of 2026-10-13 (propeller adaptation versus speed)
- Canvas: to write (specs updated once the code is stable)
