# Non-functional requirements (NFR)

### REQ-NFR-001 — Only the wing-borne aerodynamics need Excel

- **Statement:** The aero evaluation of quadplanes and tilt-rotors requires Windows
  and Excel; every other part (propulsion, mission, multicopter, GUI forms, data)
  shall run without Excel.
- **Rationale:** Development and tests of the physics must not depend on Excel.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — fast test suite passes with xlwings mocked out.
- **Satisfied by:** SPEC-001, SPEC-002, SPEC-004, SPEC-005

### REQ-NFR-002 — SI units internally, user units at the boundaries

- **Statement:** All computations shall use SI units; user units (mm, g, dm², mAh,
  km/h) are converted only at the PredimRC, project file and GUI boundaries, and each
  field documents its unit.
- **Rationale:** PredimRC mixes mm, g and dm²; unit errors are the first bug source.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Inspection — docstrings; test — conversion helpers.
- **Satisfied by:** SPEC-001, SPEC-002, SPEC-004
- **Increment 3 (2026-10-18):** statement changed, see `inc3/specs/requirements/REQ-NFR.md#req-nfr-002`.

### REQ-NFR-003 — Fast tests do not need Excel

- **Statement:** The default test run shall not need Excel; tests driving Excel are
  marked `slow` and skipped when Excel is not available.
- **Rationale:** Fast feedback, CI on any machine.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Inspection — `tests/conftest.py`.
- **Satisfied by:** SPEC-001, SPEC-002, SPEC-003, SPEC-004, SPEC-005, SPEC-006, SPEC-007

### REQ-NFR-004 — A result is reproducible

- **Statement:** A result shall be reproducible from its project file, the tool
  version and the database version, which are recorded with the results.
- **Rationale:** Design studies are compared over time.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Inspection — results metadata.
- **Satisfied by:** SPEC-004, SPEC-005

### REQ-NFR-005 — The models are validated against reference data

- **Statement:** The propulsion models should reproduce manufacturer test data of at
  least two motor/propeller combinations within ±10 % on thrust, current and power.
- **Rationale:** Credibility of the pre-sizing.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — `tests/propulsion/test_validation.py`.
- **Satisfied by:** SPEC-002, SPEC-003
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-NFR.md#req-nfr-005`.

## Added by increment 2 (2026-10-14)

### REQ-NFR-006 — Every model has a MIC card (changed)

- **Statement:** Every model and procedure used (including the surrogate, the power
  chain, the V-arm drag, the two-phase evaluation and the calibration) shall have a MIC
  card in `mvp/docs/models/`, its Interface generated from the code when it is a `Model`.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — generated Interface matches each card.
- **Satisfied by:** INC2-001, INC2-003, INC2-004, INC2-006, INC2-007

### REQ-NFR-007 — The model can be calibrated on flight test points

- **Statement:** Optionally, the measured hover and cruise points shall set one model
  factor each (hover: propeller figure of merit or surrogate scale; cruise: propeller
  efficiency or drag factor), the calibration being reported (before, after, factor,
  bound reached) and switched on or off by the user; with test data, the GUI always shows
  the uncalibrated deviation.
- **Priority:** Should
- **Status:** Implemented for the scenario mode; not applied to the two-phase evaluation
- **Verification:** Test — calibrated model reproduces the measurement to 1e-6.
- **Satisfied by:** INC2-001, INC2-009

## Added by increment 3 (2026-10-18)

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
