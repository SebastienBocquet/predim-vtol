# Component data requirements (DATA)

### REQ-DATA-001 — A motor database covers a few commercial ranges

- **Statement:** The tool shall ship a motor database covering at least: T-Motor MN
  (lift), T-Motor Antigravity (lift, light), SunnySky X (lift, low cost) and T-Motor AT
  (cruise), with for each motor: Kv, winding resistance, no-load current, maximum
  current, maximum power, mass, recommended cell count and propeller range.
- **Rationale:** These ranges cover the typical 1–10 kg RC VTOL class and publish
  their constants and test data.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the database loads and every entry is complete.
- **Satisfied by:** SPEC-003
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-DATA.md#req-data-001`.

### REQ-DATA-002 — A propeller database gives performance coefficients

- **Statement:** The tool shall ship a propeller database with diameter, pitch, mass
  and, when available, thrust and power coefficients versus advance ratio (APC
  performance files, T-Motor test tables).
- **Rationale:** The propeller selection and the cruise operating point need the
  coefficients.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — loaded coefficient tables are monotonic in advance ratio
  and positive at J = 0.
- **Satisfied by:** SPEC-003
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-DATA.md#req-data-002`.

### REQ-DATA-003 — Every data entry has a provenance

- **Statement:** Every motor and propeller entry shall record its source (URL or
  document), its retrieval date and a status (`verified` against the source, or
  `estimated`).
- **Rationale:** Data copied from the internet must be traceable and checkable.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — loader rejects entries without source.
- **Satisfied by:** SPEC-003

### REQ-DATA-004 — The user extends the database without code

- **Statement:** The user should be able to add motors and propellers by dropping
  data files in a user folder, which are merged with the shipped database.
- **Rationale:** Designers use components which are not in the shipped ranges.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — an entry in a temporary user folder is found by its id.
- **Satisfied by:** SPEC-003

## Added by increment 2 (2026-10-14)

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
