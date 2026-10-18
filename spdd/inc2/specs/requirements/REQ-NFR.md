# Increment 2 — Non-functional (NFR)

### REQ-NFR-005 — The surrogate and the models are validated against data (changed)

- **Statement:** The thrust–power surrogate shall be validated on the stored test data
  (leave-one-out and leave-one-pair-out: mean and maximum relative error, coverage of
  the 95 % interval), and the evaluation shall be compared with the flight test points
  when entered; the validation report is shown in the GUI and stored with the data
  hash.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — validation metrics computed on the shipped data within the
  thresholds of REQ-PROP-011.
- **Satisfied by:** INC2-003, INC2-009

### REQ-NFR-006 — Every model has a MIC card (changed)

- **Statement:** Every model and procedure used (including the surrogate, the power
  chain, the V-arm drag, the two-phase evaluation and the calibration) shall have a MIC
  card in `docs/models/`, its Interface generated from the code when it is a `Model`.
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
