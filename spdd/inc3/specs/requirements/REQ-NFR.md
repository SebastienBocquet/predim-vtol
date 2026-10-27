# Increment 3 — Non-functional (NFR)

### REQ-NFR-002 — SI units internally, user units at the boundaries (changed)

- **Statement:** All computations use SI units. In the GUI, thrusts are shown in N with
  the equivalent mass in kg in parentheses (`12.3 N (1.25 kg)`), speeds in km/h (inputs
  too, stored in m/s), propeller pitch and diameter in inches; other units are unchanged
  (mm, g, dm², mAh, W). Each field documents its unit.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — unit helpers; app test — KPI tiles and table headers.
- **Satisfied by:** SPEC-001, SPEC-002, SPEC-004, INC3-002

### REQ-NFR-008 — The project follows the vimseo template

- **Statement:** The repository shall provide: `tox` environments (tox-uv) for the tests
  per Python version (full extras by default, core deps with the `core` factor), `check`
  (pre-commit: ruff check and format, file hygiene), `dist` and `update-deps`; compiled
  requirement files (`uv pip compile --universal`); `.ruff.toml` with the vimseo rules;
  coverage settings; a GitHub Actions workflow running the tests and the check; a
  changelog, a contributing guide and the licence.
- **Priority:** Should
- **Status:** Implemented (2026-10-18)
- **Verification:** `tox -e check`, `tox -e py312` pass.
- **Satisfied by:** INC3-001

### REQ-NFR-007 — The model can be calibrated on flight test points (changed)

- **Statement:** Optionally, a measured hover point and a measured cruise point shall each set
  one factor of the two-phase model so that it reproduces the measured battery power at the
  mass of the point: hover → multiplier of the motor powers read in the thrust–power test data
  (`mission.hover_power_factor`, 0.5–2); cruise → multiplier of the total cruise drag
  (`mission.drag_factor`, 0.2–5). The calibration is applied by every Run and every study,
  reported (measured, model before and after, factor, bound reached) in the Test data tab;
  the comparison with the test data stays uncalibrated. The scenario mode of the API keeps its
  own calibration (figure of merit, propeller efficiency or drag).
- **Priority:** Should
- **Status:** Implemented (2026-10-19)
- **Verification:** Test — the calibrated two-phase model reproduces the measurements to 1e-6.
- **Satisfied by:** INC2-001, INC3-005
