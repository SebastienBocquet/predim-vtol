# MIC-AERO-SIMPLE — Simple aerodynamic model of the winged aircraft

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Simple aerodynamic model (wing, stabiliser, fuselage) |
| Model identifier | MIC-AERO-SIMPLE |
| Model description | Trimmed speed polar, neutral point and centre of gravity of a winged aircraft from its PredimRC-style geometry, with textbook methods and NeuralFoil section polars; the default aerodynamic backend, PredimRC being optional. |
| Release / date / type | 0.2.0 / 2026-11-14 / implementation |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** give the cruise polar (power versus speed), the stall speed and the
  centre of gravity for the static margin entered, on any platform, without Excel.
- **Objective:** pre-sizing accuracy: same inputs and outputs as PredimRC, deviations
  from it documented below.

## Subject information

- **Modelled entity:** the clean airframe of a winged RC aircraft (quadplane): wing of up
  to 5 trapezoidal panels, flat or V stabiliser, pod-and-boom fuselage. The VTOL
  appendages (booms, stopped rotors) are drag sources of MIC-CFG-DRAG, not of this model.

## Interface

Inputs and outputs are those of the PredimRC backend (`predim_vtol.aero.base`):

### Inputs

| Name | Unit | Description |
|---|---|---|
| `wing` | mm, ° | root chord; per panel: tip chord, length, leading-edge offset from the root leading edge, twist, dihedral |
| `stab` | mm | root chord, panels, lever (wing root LE to stabiliser root LE), height, profile label, V opening label, lateral gap |
| `fus` | mm, dm² | length, width, height, nose lever (nose to wing root LE), shape, beam, wing position, incidence and accessory labels |
| `settings` | g, %, —, m, °C, km/h | mass, static margin, trim C_z (`cz_reg`), altitude, temperature, imposed speeds V1, V2 |
| `profile` | — | wing airfoil: name in `aero/airfoils.yaml` or in the user file `<user data>/airfoils.yaml` |

### Outputs

| Name | Unit | Description |
|---|---|---|
| `cz`, `cx`, `vx`, `drag_n`, `power_required_w`, `sink_rate`, `finesse_vx` | —, m/s, N, W | trimmed polar, 60 points from the wing maximum lift to C_L = 0.02 |
| `imposed` | m/s, N, W | drag and power at V1, V2 versus the wing C_L (same layout as PredimRC) |
| `v_min`, `v_min_power`, `v_max_finesse` | m/s | stall, minimum power and maximum L/D speeds |
| `foyer`, `cg` | % MAC | neutral point, CG at the static margin entered |
| `neutral_point_mm`, `cg_mm` | mm | from the wing root leading edge |
| `total_surface`, `mean_chord`, `span_aero`, `span_total`, `aspect_ratio`, `aspect_ratio_el`, `wing_loading`, `tail_volume` | dm², mm, —, g/dm² | geometry |
| `stab_incidence_deg`, `longitudinal_dihedral_deg` | ° | at the trim C_z |

### Parameters

| Name | Value | Description | Source |
|---|---|---|---|
| `WING_CL_MAX_FACTOR` | 0.9 | wing / section maximum lift; section drag read at C_L / 0.9 | usual straight-wing value |
| `TAIL_DYNAMIC_PRESSURE_RATIO` | 0.9 | η at the tail | usual value |
| `TAIL_EFFICIENCY` | 0.85 | factor on the tail term of the neutral point | calibrated on PredimRC |
| `FUSELAGE_MOMENT_FACTOR` | 6.0 | factor on the Munk-Multhopp fuselage moment | calibrated on PredimRC |
| `STAB_PROFILES` | NACA 0006 / 0010 / 2406 / 2410 | stabiliser label → airfoil | thin, thick, cambered |
| `FUSELAGE_SHAPES` | wetted factor 0.75 / 0.85 / 0.9; form ×1 / 1.35 / 1.7 | Profilée / Caisse arrondie / Caisse | Hoerner, tuned on the PredimRC drag increments |
| `BEAMS` | boom Ø 0.12–0.45 D; afterbody C_d 0–0.12 | Fine … Jet | tuned on the PredimRC drag increments |
| `ACCESSORY_CD` | 0.15 / 0.5 / 1.1 | accessory C_d on its frontal area | Hoerner; 1.1 from PredimRC |

## Implementation

### Modelling choices

- **Planform:** exact integrals over the trapezoids: area, span (both halves, no dihedral
  projection, as PredimRC), MAC = ∫c²/S, its leading edge from ∫c·x_LE/S, aerodynamic
  centre at MAC/4; equivalent taper from the mean chord.
- **Lift slopes:** Helmbold / DATCOM with the section slope of the airfoil at Re = 200 000;
  V-tail: Γ = (180° − opening)/2, pitch effectiveness cos²Γ, panel normal coefficient
  C_N = C_L,t / cos Γ for its drag.
- **Downwash:** DATCOM, dε/dα = 4.44 (K_A K_λ K_H √cos Λ)^1.19.
- **Induced drag:** C_L² / (π A e), e of Nita & Scholz (taper, sweep) times the fuselage
  factor 1 − 2 (d/b)²; same for the stabiliser on its own aspect ratio.
- **Profile drag:** section polars cd(cl, Re) from NeuralFoil (`tools/airfoil_polars.py`),
  interpolated in log Re (scaled by Re^−0.5 below, Re^−0.2 above the table); wing read at
  C_L / 0.9, stabiliser at C_N.
- **Fuselage:** pod from the nose to one equivalent diameter behind the wing root trailing
  edge, turbulent C_f (Schlichting) × Hoerner form factor × wetted area; boom from the pod
  to the tail end; afterbody C_d on the pod frontal area; accessory C_d × area.
- **Neutral point:** x_NP = (a_w S x_ac,w + k_t η a_t S_t (1 − dε/dα) x_ac,t − k_f M_α,f)
  / (a_w S + k_t η a_t S_t (1 − dε/dα)), M_α,f the Munk moment of the fuselage width
  distribution with the wing upwash ahead of the wing and the downwash behind (Multhopp).
- **Trim:** at every polar point, the stabiliser lift balances the moments about the CG
  (wing lift and C_m0, fuselage moment, stabiliser C_m0); the fuselage axis is aligned
  with the flow at `cz_reg`. Points where the stabiliser stalls are dropped.
- **Polar:** wing C_L from the maximum (0.9 c_l,max at the stall Reynolds number) down;
  V from the total lift (wing + stabiliser) = weight.

### Model limitations

- Pre-stall only: no post-stall branch; twist, dihedral and the wing position label have
  no effect (as in PredimRC); the `incidence` label is not used.
- No propeller slipstream, no interference drag besides the calibrated factors.
- Neutral point: the calibrated factors make it agree with PredimRC (mean gap below 1 %
  of the MAC); the uncalibrated textbook value is about 10 % of the MAC further aft. Two
  configurations differ more: a thick "Jet" rear fuselage (PredimRC 7 % MAC further aft)
  and a strongly swept wing (6 % MAC).
- **Performance versus PredimRC** (52 reference cases around the quadplane template):
  minimum power 25 % lower (−35 % to −17 %), maximum L/D 14 % higher, stall speed 11 %
  lower. The gap comes mainly from the high lift coefficients: PredimRC reads the
  section polar at about C_L / 0.78 (the 3D/2D lift slope ratio, as if the section were
  at the geometric angle of attack of the wing), this model at C_L / 0.9. Reading it at
  C_L / 0.66 with +6 % profile drag reproduces PredimRC within 6 % RMS. Use the
  calibration on measured flight points (MIC-CAL-REF) or the mission drag factor to
  match a real aircraft.

### Model classification

- `physics.aerodynamics.airframe`

## Verification and validation

- **Verification status:** geometry identical to PredimRC (area, MAC, spans, aspect ratio,
  tail volume); pitch equilibrium at every point; level-flight consistency (D·V = m·g·|V_z|).
- **Validation status:** compared with PredimRC v2.64 (SD7003) on 52 one-factor
  variations; gaps above. Section polars: NeuralFoil SD7003 within the wind tunnel data
  of Selig (cd ≈ 0.0095 at cl 0.5, Re 200 000). Not validated against flight data.
- **Report:** `tests/aero/test_simple.py`, reference data
  `tests/aero/data/predimrc_reference.json`.

## Traceability

- Requirements: REQ-AERO (simple backend), REQ-NFR-006
