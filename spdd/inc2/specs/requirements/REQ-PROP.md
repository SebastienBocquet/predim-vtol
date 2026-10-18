# Increment 2 — Propulsion (PROP)

### REQ-PROP-004 — The propeller pitch is modelled (changed)

- **Statement:** The system shall model a fixed-pitch propeller by blade elements with
  momentum inflow (diameter, pitch, generic section and chord) to give thrust, power and
  efficiency versus rotation speed and airspeed; coefficient tables (REQ-DATA-002)
  replace it when available. It gives the cruise propeller efficiency of the two-phase
  evaluation.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — static C_T, C_P in the RC range; zero thrust near the pitch
  speed; pitch trends.
- **Satisfied by:** INC2-001, INC2-007

### REQ-PROP-005 — Hover power per motor from the thrust–power data (changed)

- **Statement:** For each lift motor, the system shall give the electric power at its
  hover thrust (REQ-CFG-010) from the thrust–power surrogate of its motor + propeller at
  the battery voltage, with its uncertainty, and the power margin 1 − P / P_max and the
  thrust margin 1 − T / T_max,test. Without data for the pair, the physics model is used
  and the value is flagged "no test data".
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — on a tested pair, the value at a tested thrust equals the
  test point within its noise; flag raised without data.
- **Satisfied by:** INC2-003, INC2-007

### REQ-PROP-007 — The propeller pitch is sized for the two target speeds (changed)

- **Statement:** For each cruise or tilting propulsion unit, the system shall give the
  pitch maximising the propeller × motor efficiency at each target speed (V₁, V₂) within
  the motor limits, the best compromise for both, and for a tilting unit the hover
  penalty of that pitch; the user keeps or imposes the pitch, optionally among the
  database propellers of the same diameter.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — higher target speed ⇒ higher or equal optimal pitch; the
  imposed pitch is used.
- **Satisfied by:** INC2-009

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
