# Configuration requirements (CFG)

### REQ-CFG-001 — Three VTOL architectures are supported

- **Statement:** The system shall support the quadplane (dedicated lift rotors plus
  cruise unit), the pure multicopter and the tilt-rotor architectures.
- **Rationale:** These are the architectures in scope of the first milestone;
  tailsitters are out of scope.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Example — one project file per architecture runs end to end.
- **Satisfied by:** SPEC-004
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-CFG.md#req-cfg-001`.

### REQ-CFG-002 — The rotor layout is user-defined

- **Statement:** The user shall define the number of lift rotors (4, 6 or 8; coaxial
  pairs allowed), their position (x, y in the aircraft frame) and the maximum
  propeller diameter allowed by the layout.
- **Rationale:** The geometry is specified by the user; the layout bounds the
  propeller diameter and feeds the geometry preview.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — default symmetric layout generated from boom span; diameter
  bound respected.
- **Satisfied by:** SPEC-004
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-CFG.md#req-cfg-002`.
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-CFG.md#req-cfg-002`.

### REQ-CFG-003 — A mass budget closes the total mass

- **Statement:** The system shall build the total mass from: airframe structure (user),
  VTOL-specific structure (booms, mounts; user), payload (user), avionics (user),
  motors, propellers and ESCs (database or user), and battery (user or sized), and
  report the breakdown.
- **Rationale:** The VTOL structure mass is a user input and the mass drives every
  power.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the total equals the sum of the items.
- **Satisfied by:** SPEC-004

### REQ-CFG-004 — Parasitic drag sources are listed and modelled

- **Statement:** The user shall list parasitic drag sources (booms, stopped lift
  rotors, landing gear, payload pod, free CdS). Each source is computed by a dedicated
  model (equivalent drag area) or routed to the PredimRC accessory surface.
- **Rationale:** The drag of the VTOL system penalises the cruise of a quadplane.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — total drag area equals the sum of dedicated sources; routed
  sources reach the PredimRC accessory cell.
- **Satisfied by:** SPEC-004
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-CFG.md#req-cfg-004`.
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-CFG.md#req-cfg-004`.

### REQ-CFG-005 — The battery can be sized for a target scenario

- **Statement:** The system should offer a sizing mode in which the battery mass is
  computed so that a given scenario is flown with the required reserve, accounting
  for the effect of the battery mass on the total mass.
- **Rationale:** "How much battery for this mission" is the usual first question.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — the sized battery yields a reserve equal to the target
  within 1 %.
- **Satisfied by:** SPEC-004, SPEC-005

### REQ-CFG-006 — The multicopter does not need PredimRC

- **Statement:** A multicopter shall be evaluated without the PredimRC workbook, with a
  body drag area given by the user.
- **Rationale:** A multicopter has no wing; requiring Excel would be useless and slow.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — multicopter project runs with Excel unavailable.
- **Satisfied by:** SPEC-004, SPEC-005

### REQ-CFG-007 — A design is stored in one project file

- **Statement:** All the inputs of a design (geometry, configuration, components, drag
  sources, scenarios, settings) shall be saved to and loaded from one human-readable
  project file, used identically by the Python API, the GUI and the GEMSEO discipline.
- **Rationale:** One source of truth across the three entry points; reproducibility.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — save/load round trip gives an equal project.
- **Satisfied by:** SPEC-004

## Added by increment 2 (2026-10-14)

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

## Added by increment 3 (2026-10-18)

### REQ-CFG-013 — The current configuration can be saved as a user template

- **Statement:** The GUI shall save the current project (geometry, propulsion unit types,
  motors with positions, roles and tilt mask, booms, battery, masses, drag sources,
  wiring, mission, sizing, test data) as a named user template in a templates folder
  (setting, default `~/.predimrc_wrapper/templates`). The Configuration selector lists
  the shipped and the user templates; user templates can be renamed and deleted.
- **Rationale:** No template per tilt mask or layout is needed, since these are inputs.
  The designer keeps their own starting points.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — a saved template is listed and reloads into an identical
  project.
- **Satisfied by:** INC3-003

### REQ-CFG-014 — Booms are parallel or diagonal, with a chosen section

- **Statement:** The user shall choose, in the aircraft configuration tab, the boom layout
  — parallel (booms along the flow carrying the motors) or diagonal (one straight boom
  per lift motor from an anchor under the fuselage) — and the boom section — profiled,
  square or round — with its thickness (and chord when profiled). The anchor position
  (x, half width, depth under the fuselage) defaults from the fuselage. The booms are
  drawn in the geometry views, give their drag (REQ-CFG-004) and the cable paths of the
  power chain (REQ-PROP-009).
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — boom lengths and angles from the anchor equal a hand
  calculation; the phase cable length of a diagonal boom motor includes the boom length.
- **Satisfied by:** INC3-003
