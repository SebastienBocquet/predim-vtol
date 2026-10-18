# MIC-CFG-DRAG — Parasitic drag and drag polar (MVP)

## Administrative data

| Attribute | Value |
|---|---|
| Model name | Parasitic drag sources and total drag polar |
| Model identifier | MIC-CFG-DRAG |
| Model description | Equivalent drag areas of VTOL appendages added to the PredimRC polar (quadplane), or body drag (multicopter). |
| Release / date / type | 0.1.0-mvp / 2026-10-12 / specification (pre-release) |
| Supplier / confidentiality / legal | see [index](index.md) |

## Purpose and objectives

- **Model purpose:** provide D(V) for the cruise segments, including the drag of the
  VTOL system.

## Subject information

- **Modelled entity:** booms, stopped lift rotors and other appendages; the complete
  aircraft in cruise.

## Interface

<!-- interface:start -->
### Inputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `sources` | — | — | list of {kind: boom \| stopped_rotor \| cds, count, ...} | — |
| `v_m_s` | V | m/s | true airspeed | ≥ 0 |
| `rho` | ρ | kg/m³ | air density | ≥ 0 |
| `polar` | — | — | PredimRC speed polar at the total mass (quadplane) | — |
| `body_cds_m2` | CdS_b | m² | body drag area (multicopter) | ≥ 0 |

### Outputs

| Name | Symbol | Unit | Description | Physical bounds |
|---|---|---|---|---|
| `cds_dedicated_m2` | ΣCdS | m² | sum of dedicated drag areas | ≥ 0 |
| `drag_n` | D | N | total drag at V (NaN outside the polar) | ≥ 0 |
| `v_min_m_s` | V_min | m/s | lowest valid polar speed at ρ (quadplane) | ≥ 0 |

### Parameters

| Name | Symbol | Unit | Description | Default / origin | Physical bounds | Source |
|---|---|---|---|---|---|---|
| `boom_cf` | C_f | — | boom skin friction coefficient | 0.005 | ≥ 0 | generic turbulent flat plate |
| `boom_cd_end` | C_d,end | — | boom base drag coefficient | 0.15 | ≥ 0 | generic |
| `blade_cd` | C_d,b | — | stopped blade drag (blade planform) | 0.05 | ≥ 0 | generic, blades aligned |
<!-- interface:end -->

## Implementation

### Modelling choices

- Boom (axial flow in cruise): CdS = C_f·π·d·L + C_d,end·π·d²/4.
- Stopped rotor: CdS = n_b·c̄·R·C_d,b.
- Free source: CdS given.
- Shapes as the PredimRC accessory shapes, C_d referred to the frontal area, extracted
  from the workbook (`data/drag_shapes.yaml`, `Calculs1!AD3`): Profilé 0.2, Mixte 0.6,
  Non profilé 1.0.
- V-arms (motor arms attached under the fuselage, going to the motors): one straight
  arm per motor from its root (x_a, ±w/2, z_a) to the motor; frontal area
  A = Σ t·L_i·√(1 − u_x,i²); CdS = C_d(shape)·A; area from the geometry unless entered.
- Body part: CdS = C_d(shape)·A, A entered.
- Booms of the configuration (`Project.booms`, `aircraft/booms.py`, INC3-003), section
  round / square / profiled with C_d from Hoerner (`data/boom_sections.yaml`: 1.2, 2.0,
  0.1, referred to the frontal area t·L of a member normal to the flow):
  - parallel booms (along the flow, from the front to the rear motor, at least to the wing
    spar): CdS = C_f·p·L + C_d,end·A_section (p: perimeter of the section);
  - diagonal booms (one per lift motor from an anchor under the fuselage, or the frame
    centre): cross-flow principle on the frontal area A_i = t·L_i·sin θ_i,
    CdS_i = C_d,section·sin²θ_i·A_i + C_f·p·L_i (θ_i: angle between boom i and the flow).
- Every source reports its model, formula and coefficient source
  (`aircraft/drag_sources.py`, Drag tab).
- Quadplane: D(V) = D_PredimRC(V_eas, m) + ½·ρ·V²·ΣCdS, with V = V_eas·√(ρ₀/ρ); PredimRC
  runs with an accessory surface of 0 (REQ-AERO-006), a former accessory becomes a
  `cds` source.
- Total drag × `mission.drag_factor` (1 unless calibrated).
- Multicopter: D(V) = ½·ρ·V²·CdS_b.

### Model limitations

- Generic coefficients; stopped rotors assumed aligned with the flow.
- V-arms and booms as straight beams of constant section; no interference drag.
- Cross-flow principle: valid for bluff sections (round, square); for a profiled boom
  inclined to the flow it is an approximation (the profile is not aligned with the local
  flow).
- No mass scaling of the polar: each new mass is a PredimRC evaluation (memoised).

### Model classification

- `physics.aerodynamics.parasitic_drag`

## Verification and validation

- **Verification status:** not started.
- **Validation status:** not started.
- **Criteria:** ΣCdS = sum of sources; D_parasitic ∝ V² (model-form test).
- **Report:** `tests/aircraft/test_drag.py`.

## Traceability

- Requirements: REQ-CFG-004, REQ-CFG-006, REQ-CFG-014, REQ-AERO-005, REQ-NFR-006
- Canvas: MVP-004, INC2-006, INC3-003 (booms)
