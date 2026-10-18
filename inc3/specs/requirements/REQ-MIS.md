# Increment 3 — Mission (MIS)

### REQ-MIS-009 — The power budget lists every power sink

- **Statement:** For hover and each target speed, the system shall split the battery
  chemical power into: useful aerodynamic power (hover: Σ T^1.5/√(2ρA); cruise: D·V),
  propeller losses (shaft − useful), motor losses (copper I²R_m and no-load I₀·U),
  ESC losses, cable losses (main, DC, phase), battery internal losses and avionics. The
  sinks sum to the chemical power. The Results tab shows them as a table and a stacked
  bar chart.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the sum of the sinks equals the chemical power to 1e-9
  relative for the tricopter and the quadplane.
- **Satisfied by:** INC3-002
