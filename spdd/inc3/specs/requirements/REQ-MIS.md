# Increment 3 — Mission (MIS)

### REQ-MIS-009 — The power budget lists every power sink

- **Statement:** For hover and each target speed, the system shall split the battery
  chemical power into: useful aerodynamic power (hover: Σ T^1.5/√(2ρA); cruise: D·V),
  propeller losses (shaft − useful), motor losses (copper I²R_m and no-load I₀·U),
  ESC losses, cable losses (main, DC, phase), battery internal losses and avionics. The
  sinks sum to the chemical power. The Results tab shows them as a table and a stacked
  bar chart.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — the sum of the sinks equals the chemical power to 1e-9
  relative for the tricopter and the quadplane.
- **Satisfied by:** INC3-002

### REQ-MIS-010 — The flight includes the vertical phases

- **Statement:** The two-phase flight shall include a vertical climb to a transition altitude
  h at a climb speed v_c (momentum-theory climb power per rotor), a hover time at that
  altitude, and a vertical descent from h at v_d (hover power); each phase is shown with its
  duration, battery power and energy, and the cruise time is the energy left after them
  divided by the cruise power.
- **Rationale:** The designer enters the transition altitude rather than a hover time
  covering every vertical phase (feedback of 2026-10-19).
- **Priority:** Must
- **Status:** Implemented (2026-10-19)
- **Verification:** Test — durations h/v_c, h/v_d; climb power factor by hand; with h = 0 and
  no transition the former formula holds.
- **Satisfied by:** INC3-006

### REQ-MIS-011 — The transition is checked at a tilt angle

- **Statement:** For a winged aircraft the flight shall include a transition of a given
  duration. With tilting motors, they are at a given tilt angle θ from the horizontal and give
  T·sin θ vertically, so each must give F / sin θ for its hover share F (no wing lift, start of
  the transition); the power, current and test-data margins of every motor at that point are
  shown and enter the feasibility ("Margin transition"); the transition energy counts in the
  flight. Without tilting motors the transition is at hover power.
- **Priority:** Must
- **Status:** Implemented (2026-10-19)
- **Verification:** Test — tilted thrust F / sin θ; θ = 90° equals hover; a too steep angle
  makes the transition margin negative.
- **Satisfied by:** INC3-006
