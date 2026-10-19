# Increment 3 — Configuration (CFG)

### REQ-CFG-002 — Motors are listed with their position, role and tilt mask (changed)

- **Statement:** The user shall list the motors, one per arm or boom end, each with its
  position (x aft-positive, y right, mm, from a reference point named and drawn in the
  GUI: wing root leading edge for a winged aircraft, frame centre otherwise), its
  propulsion unit type and its role. The tilting motors are chosen by a **tilt mask**
  (motor numbers, as ArduPilot `Q_TILT_MASK`), with quick choices front / rear / all /
  none; any mask is allowed as long as a winged aircraft keeps at least one motor able
  to push in cruise. Propeller discs shall not overlap; an overlap is reported with the
  motor numbers, their propeller diameters, the distance between centres, the minimum
  distance and how to fix it.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — the tricopter with wing and mask {3} has one tilting rear
  motor and two lift front motors and evaluates; the overlap message names both motors
  and the distances; app test — the drawing and the table agree after a mask change.
- **Satisfied by:** INC2-001, INC3-003

### REQ-CFG-004 — Drag sources, including booms, with their model shown (changed)

- **Statement:** As in increment 2, plus: the booms are an automatic drag source built
  from the boom specification (REQ-CFG-014), listed in the Drag tab with their model
  (section, angle to the flow θ, length, frontal area, effective C_d·sin²θ, CdS, drag
  power at V₁); they are edited in the aircraft configuration tab, not in the Drag tab.
  Inclined members follow the cross-flow principle on the frontal area:
  D = ½ρV²·C_d,section·sin²θ·A_frontal, A_frontal = t·L·sin θ (t: thickness seen by
  the flow, L: boom length).
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — drag of each diagonal boom equals a hand calculation for the
  three sections.
- **Satisfied by:** INC2-006, INC3-003

### REQ-CFG-013 — The current configuration can be saved as a user template

- **Statement:** The GUI shall save the current project (geometry, propulsion unit types,
  motors with positions, roles and tilt mask, booms, battery, masses, drag sources,
  wiring, mission, sizing, test data) as a named user template in a templates folder
  (setting, default `~/.predimrc_wrapper/templates`). The Configuration selector lists
  the shipped and the user templates; user templates can be renamed and deleted.
- **Rationale:** No template per tilt mask or layout is needed, since these are inputs.
  The designer keeps their own starting points.
- **Priority:** Should
- **Status:** Implemented (2026-10-18)
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
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — boom lengths and angles from the anchor equal a hand
  calculation; the phase cable length of a diagonal boom motor includes the boom length.
- **Satisfied by:** INC3-003

### REQ-CFG-015 — The cables are in the mass budget

- **Statement:** The mass of every cable of the power chain (copper and silicone insulation,
  per gauge, times its length and number of conductors) shall be counted in the mass budget
  (category wiring) and shown in the Power chain tab; the gauges not entered are sized for the
  maximum current of the motors (data sheet), the same cables at every operating point.
- **Priority:** Must
- **Status:** Implemented (2026-10-19)
- **Verification:** Test — mass per metre against two published wires (2 %); budget includes
  the wiring; gauges from I_max.
- **Satisfied by:** INC3-006
