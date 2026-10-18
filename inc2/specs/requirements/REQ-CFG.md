# Increment 2 — Configuration (CFG)

### REQ-CFG-001 — Quadplane, tricopter, multicopter and tilting motors (changed)

- **Statement:** The system shall support the quadplane (wing + lift rotors + cruise
  motor, e.g. 4+1), the tricopter, the multicopter with N ≥ 3 motors, and wing-borne
  variants where any motor tilts (tilt-rotor).
- **Priority:** Must
- **Status:** Implemented (2026-10-13) — templates quadcopter, tricopter, quadplane 4+1,
  tilt-rotor.
- **Verification:** Example — each template evaluates end to end.
- **Satisfied by:** INC2-001

### REQ-CFG-002 — Motors are listed with their position and role (changed)

- **Statement:** The user shall list the motors, one per arm or boom end (no coaxial
  pairs), each with its position (x aft-positive, y right, mm), its propulsion unit type
  (motor, propeller, ESC; heterogeneous types allowed) and its role: lift, cruise or tilt.
  The tilting motors are chosen in the aircraft configuration tab. Propeller discs of the
  lift motors shall not overlap. Layout generators (multirotor, tricopter, quadplane,
  tilt-rotor) fill the list.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — overlap rejected; unknown unit type rejected; a tilt motor
  lifts in hover, pushes in cruise and counts once in the mass.
- **Satisfied by:** INC2-001, INC2-009

### REQ-CFG-004 — Drag sources, including V-arms, with their model shown (changed)

- **Statement:** The user shall list the parasitic drag sources: booms, stopped rotors,
  V-arms (motor arms attached under the fuselage and going diagonally to the motors),
  free CdS. Each source is computed by a named model whose formula, coefficients and
  coefficient sources are shown in the Drag tab. As in PredimRC, a source is described
  by a shape — "Profilé", "Mixte", "Non profilé", one C_d each taken from PredimRC
  (`Calculs1!D169:D171`; "Non profilé" C_d = 1.0) — and a frontal area, which defaults
  to the value derived from the geometry of the chosen configuration.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — V-arm frontal area and drag equal a hand calculation for a
  tricopter; the frontal area follows the motor positions.
- **Satisfied by:** INC2-006

### REQ-CFG-012 — The multicopter cruise drag is a shape C_d × a frontal area

- **Statement:** The cruise drag of a multicopter body shall be C_d × frontal area, the
  C_d given by a shape as in PredimRC (Profilé 0.2, Mixte 0.6, Non profilé 1.0) or entered,
  the frontal area entered; a CdS may replace them; drag sources (V-arms...) are added.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — body drag of the templates; the model text shown in the Drag tab.
- **Satisfied by:** INC2-006, INC2-009

### REQ-CFG-010 — Thrust per motor from the moment balance; front / rear ratio shown

- **Statement:** The system shall compute the hover thrust of each lift motor from the
  mass and the balance of forces and moments about the CG (x, y given by the user;
  statically indeterminate layouts solved by the minimum of Σ T_i² / A_i), reject a CG
  outside the lift motors, and display the thrust of each motor and the front / rear
  thrust ratio (motors ahead of / behind the CG).
- **Rationale:** This is the first step of the designer's hover calculation.
- **Priority:** Must
- **Status:** Implemented (2026-10-15).
- **Verification:** Test — tricopter: moments balanced to 1e-12; ratio equals the hand
  calculation.
- **Satisfied by:** INC2-001, INC2-007

### REQ-CFG-011 — Motors are pre-selected from a target mass range

- **Statement:** From a target take-off mass range, the system shall give for each
  propulsion unit type the range of motor power needed, from a hover power law fitted on
  a reference aircraft (default 1.87 kg, 280 W) and the minimum thrust-to-weight, and the
  database motors within that range.
- **Priority:** Should
- **Status:** Implemented (2026-10-13) — MIC-CFG-SIZ.
- **Verification:** Test — reference point reproduced; candidates within range.
- **Satisfied by:** INC2-001
