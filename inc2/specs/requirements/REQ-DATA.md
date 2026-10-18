# Increment 2 — Component and test data (DATA)

### REQ-DATA-001 — Motor database of the 150–250 W class (changed)

- **Statement:** The shipped motor database shall hold motors of 150 W to 250 W maximum
  power (180 s), values copied from manufacturer pages.
- **Priority:** Must
- **Status:** Implemented (2026-10-12) — 5 motors (T-Motor MN2212 ×2, MN2806 ×2,
  AT2308).
- **Verification:** Test — every entry complete, with provenance.
- **Satisfied by:** INC2-001
- **Open:** a second cruise motor and the designer's own motors.

### REQ-DATA-002 — A propeller database is shipped

- **Statement:** The tool shall ship a propeller database: id, manufacturer, diameter,
  pitch, blade count, mass, and, when published, thrust and power coefficients versus
  advance ratio; with provenance (REQ-DATA-003). Propulsion unit types reference a
  database propeller or give diameter, pitch and mass directly.
- **Priority:** Must
- **Status:** Implemented (2026-10-14) without coefficient tables (none published for the shipped propellers)
- **Verification:** Test — the file loads; coefficient tables positive at J = 0 and
  C_T decreasing with J.
- **Satisfied by:** INC2-002

### REQ-DATA-005 — Thrust–power test data are stored with their provenance

- **Statement:** The tool shall store thrust–power test data per motor + propeller (+ ESC)
  + voltage: rows of throttle, thrust, current, voltage, electric power, rotation speed
  (and temperature when given), with source, date, test bench, and the electrical point
  where the power is measured: `esc_input` when the table names the ESC used for the
  test (the ESC loss is then accounted for with the MVP constant-efficiency model),
  `motor_input` otherwise. The data are the motor
  manufacturer tables published on the internet, copied into data files; shipped and
  user files are merged. Importing a CSV of a bench test is a Could (no bench planned).
- **Rationale:** The designer's hover calculation interpolates in these data.
- **Priority:** Must (manufacturer tables), Could (CSV import)
- **Status:** Implemented (2026-10-14)
- **Verification:** Test — CSV import round trip; missing provenance or measurement
  point rejected; units converted (g → N).
- **Satisfied by:** INC2-002

### REQ-DATA-006 — Flight test points are stored in the project

- **Statement:** The user may enter measured flight points in the project: hover (battery
  power, mass, voltage, optional per-motor throttle) and cruise (airspeed, battery power,
  mass), each with date, conditions (altitude, temperature) and comment.
- **Priority:** Should
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — points saved and reloaded with the project.
- **Satisfied by:** INC2-002, INC2-009
