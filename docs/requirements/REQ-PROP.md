# Propulsion requirements (PROP)

### REQ-PROP-001 — Battery chemistries LiPo and Li-ion are modelled

- **Statement:** The system shall model LiPo and Li-ion batteries by their specific
  energy (Wh/kg, pack level), nominal, full and cut-off cell voltages, internal
  resistance per cell, maximum continuous discharge rate (C) and usable fraction of
  the capacity, with default values per chemistry that the user can override.
- **Rationale:** The trade between LiPo (power) and Li-ion (energy) is central for
  VTOL endurance.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — `tests/propulsion/test_battery.py`.
- **Satisfied by:** SPEC-002

### REQ-PROP-002 — A battery is defined by its cells or by its mass

- **Statement:** The user shall define a battery either by its cell count in series
  and capacity (mAh), or by its series count and mass; the other quantities (energy,
  mass, capacity, maximum current) are derived.
- **Rationale:** The designer thinks either in commercial packs or in mass budget.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — round trip capacity → mass → capacity.
- **Satisfied by:** SPEC-002

### REQ-PROP-003 — The motor operating point is computed from its constants

- **Statement:** The system shall compute the current, voltage, electric power and
  efficiency of a brushless motor from its Kv, winding resistance, no-load current and
  the required shaft torque and speed, and flag operation above its maximum current or
  power.
- **Rationale:** Motor constants are published by manufacturers; the efficiency
  varies strongly with the operating point.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — comparison with a manufacturer test table, ±10 % on current.
- **Satisfied by:** SPEC-002

### REQ-PROP-004 — The propeller is modelled by its thrust and power coefficients

- **Statement:** The system shall model a propeller by its diameter, pitch, mass and
  thrust and power coefficients versus advance ratio, falling back to a figure of merit
  (hover) and a propulsive efficiency (cruise) when no coefficient data exists.
- **Rationale:** Hover and cruise need different operating points of the same model.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — static thrust and power for an APC propeller vs data.
- **Satisfied by:** SPEC-002
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-PROP.md#req-prop-004`.

### REQ-PROP-005 — The hover power is computed per rotor

- **Statement:** The system shall compute the hover thrust per rotor (weight times a
  download factor, divided by the rotor count), and the resulting rotor speed, shaft
  power, motor current and battery power, at the air density of the flight altitude.
- **Rationale:** Hover dominates the energy of a VTOL mission.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — ideal momentum-theory power recovered with FM = 1.
- **Satisfied by:** SPEC-002
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-PROP.md#req-prop-005`.

### REQ-PROP-006 — The cruise power is computed from the drag

- **Statement:** The system shall compute the battery power in level cruise at a given
  speed from the aerodynamic drag, the propeller, motor and ESC efficiencies, and the
  avionics and payload power.
- **Rationale:** The aero polar gives a power at the shaft, not at the battery.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — battery power ≥ drag × speed, consistency of the chain.
- **Satisfied by:** SPEC-002

### REQ-PROP-007 — The propeller is selected automatically or imposed

- **Statement:** The system shall select automatically, among the database propellers
  compatible with the motor and the geometric clearance, the one minimising the hover
  battery power (lift rotors) or the mission energy (tilt-rotor, cruise unit); the user
  shall be able to impose a propeller instead.
- **Rationale:** The propeller choice is the first lever on hover efficiency, but the
  designer must keep control.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the imposed propeller is used; the automatic one is the
  argmin over the candidates.
- **Satisfied by:** SPEC-002, SPEC-003
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-PROP.md#req-prop-007`.
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-PROP.md#req-prop-007`.

### REQ-PROP-008 — Operating limits are checked

- **Statement:** The system shall report as margins the motor current, battery
  discharge rate, battery voltage under load and thrust-to-weight ratio of the lift
  system (minimum 1.5 by default, user-settable) at the most demanding segment.
- **Rationale:** A design whose endurance is good but which cannot hover safely is
  not a solution; margins are also optimisation constraints.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — a deliberately undersized motor yields a negative margin.
- **Satisfied by:** SPEC-002, SPEC-005

## Added by increment 2 (2026-10-14)

### REQ-PROP-009 — The power chain gives the losses of each segment

- **Statement:** The system shall model the power chain battery – main cables – power
  distribution – (DC cables) – ESC – phase cables – motor, and give at hover and at each
  target speed the power entering and the loss of each segment. Cable losses use the
  length, section and material entered by the user; lengths default from the geometry of
  the configuration, sections from the current. ESC topology: lift motors on a 4-in-1
  ESC or on separate ESCs, cruise motor on a separate ESC. ESC positions are entered in %
  of the fuselage length (cruise ESC, 4-in-1 ESC, every ESC of a quadplane 4+1) or in %
  of the arm length (separate lift ESCs of a multicopter or tricopter). The main cable
  starts downstream of the battery (at its rear end); the battery carries no cable
  length. When the thrust–power data were measured with an ESC (`esc_input`), the ESC
  loss is computed with the MVP model (constant efficiency) and shown inside the data,
  not added again. The segments already included in the thrust–power data (measurement point,
  REQ-DATA-005) are not counted twice.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — losses sum to battery power − shaft power exactly; a cable
  twice as long doubles its loss at equal current; default lengths of the tricopter
  equal a hand calculation.
- **Satisfied by:** INC2-004
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-PROP.md#req-prop-009`.

### REQ-PROP-011 — Thrust–power surrogate with an error guarantee

- **Statement:** The system shall predict electric power, current and rotation speed
  versus thrust (and voltage) by a surrogate = physics model (momentum / blade-element
  propeller + motor constants) × Gaussian-process correction fitted on the test data. It
  shall give a standard deviation with every prediction and flag predictions outside the
  trusted domain (relative standard deviation above a setting, default 5 %, or thrust
  beyond the tested range). It shall interpolate within a tested pair and predict pairs
  not tested from similar tested ones (to explore configurations), with a larger
  uncertainty.
- **Rationale:** Interpolating by hand limits the designer to the tested pairs; the
  guarantee tells him when a prediction can be trusted.
- **Priority:** Must
- **Status:** Implemented (2026-10-14)
- **Verification:** Test — leave-one-out and leave-one-pair-out: coverage of the 95 %
  interval within [90 %, 99 %]; held-out interpolation error ≤ 3 % (mean) on the shipped
  data; flags raised beyond the tested thrust.
- **Satisfied by:** INC2-003

### REQ-PROP-012 — The data behind a power value are shown

- **Statement:** For every power used in the flight time, the GUI shall show its origin:
  for hover, the test points of the pair around the operating point, the surrogate mean
  and 95 % band and the physics model; for cruise, the aerodynamic power, the propeller
  operating point and the chain efficiencies. A surrogate validation view shows
  predicted versus measured points and the coverage.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Inspection; Test — the chart builder returns the test points of the
  pair used.
- **Satisfied by:** INC2-003, INC2-009
