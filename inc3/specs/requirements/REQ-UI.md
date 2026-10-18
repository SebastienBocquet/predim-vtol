# Increment 3 — User interface (UI)

### REQ-UI-002 — The geometry is previewed with dimensions (changed)

- **Statement:** As in increment 2, plus a motor positions drawing built from the motor
  table (shown even when the project is invalid): reference point marked and named, x and
  y dimension lines with their values per motor, propeller discs, overlapping discs in
  red; booms drawn with their layout and section.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — one x and one y dimension per motor.
- **Satisfied by:** INC2-001, INC2-006, INC3-003

### REQ-UI-008 — Tabs follow the designer's workflow (changed)

- **Statement:** Pre-sizing page tabs: Aircraft configuration (name, template, geometry
  of wing / stabiliser / fuselage, PredimRC folder and profile, booms, motors and tilt
  mask, CG), Masses and battery, Mission, Cruise, Drag, Hover, Power chain, Propeller
  sizing, Test data, Results, Cost and reliability. Exploration, Optimisation and Studies
  move to their own sidebar page "Studies", next to Pre-sizing, MIC cards and Glossary.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** App test — tab list and sidebar pages.
- **Satisfied by:** INC2-009, INC3-002, INC3-003, INC3-004

### REQ-UI-010 — Every quantity is defined by a help in the GUI (changed)

- **Statement:** As in increment 2, plus: the propulsion unit types are explained where
  they are added ("Add a propulsion unit type": one motor + propeller + ESC combination,
  referenced by each motor; removable when no motor uses it).
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — help coverage stays complete.
- **Satisfied by:** INC2-009, INC3-003

### REQ-UI-011 — The test data comparison is explained with a sketch and formulas

- **Statement:** The Test data tab shall explain what is compared and how each model
  value is obtained, with formulas and a sketch of the energy chain: hover
  P = Σ surrogate(T_i) + chain losses + avionics; winged cruise = PredimRC power at
  imposed speed + drag sources; multicopter cruise = in-house body C_d·A + drag sources +
  forward-flight rotor model (no PredimRC). The calibration section explains why one
  factor per point and when it applies (scenario mode).
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Inspection.
- **Satisfied by:** INC3-002
