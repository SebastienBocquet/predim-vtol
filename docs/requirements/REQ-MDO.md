# Exploration and optimisation requirements (MDO)

### REQ-MDO-001 — The pre-sizing model is a GEMSEO discipline

- **Statement:** The complete evaluation (aero, configuration, propulsion, mission)
  shall be available as a GEMSEO discipline whose inputs are parameters of a base
  project file and whose outputs are the mission results and margins.
- **Rationale:** GEMSEO provides DOE, optimisation, surrogates and post-processing.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — discipline executes with default inputs and returns the
  same results as the Python API.
- **Satisfied by:** SPEC-006

### REQ-MDO-002 — Continuous, discrete and categorical variables are supported

- **Statement:** The user shall be able to vary continuous parameters (chords,
  spans, masses), discrete ones (cell count, rotor count) and categorical ones
  (chemistry, motor, propeller, airfoil), the categorical ones being exposed to the
  design space as integer indexes with a readable mapping.
- **Rationale:** Component choices are categorical and central to the trade-offs.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — index → label mapping round trip; DOE over a categorical.
- **Satisfied by:** SPEC-006

### REQ-MDO-003 — One evaluation covers several scenarios

- **Statement:** The discipline shall evaluate a design over several named scenarios
  and expose one set of outputs per scenario.
- **Rationale:** A design is judged on a mission set (e.g. inspection, delivery).
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — outputs suffixed by scenario name.
- **Satisfied by:** SPEC-006

### REQ-MDO-004 — DOE and optimisation examples are provided

- **Statement:** The tool shall provide runnable examples of a DOE (parameter sweep
  with a categorical variable) and of a constrained optimisation (maximise endurance
  under margin constraints).
- **Rationale:** Entry points for the user's own studies.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Example — `examples/mdo/*.py` run to completion (slow).
- **Satisfied by:** SPEC-006

### REQ-MDO-005 — Excel in the loop is robust and economical

- **Statement:** The discipline shall evaluate sequentially with a single Excel
  session, cache already-evaluated points, and report a failed evaluation as an error
  of that point without stopping the whole study.
- **Rationale:** PredimRC evaluation costs about 1 s and Excel COM is not parallel.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — repeated point hits the cache; injected failure is reported.
- **Satisfied by:** SPEC-006

## Added by increment 2 (2026-10-14)

### REQ-MDO-007 — Configurations are explored from the GUI

- **Statement:** The user shall explore configurations from the GUI: a design of
  experiments over continuous variables (full factorial or Latin hypercube, number of
  points given) crossed with categorical choices (motors, propellers, cell count,
  configuration templates), evaluated with the two-phase evaluation; results shown as a
  table, scatter plots of any output versus any input, and the feasible designs and
  Pareto front (flight time versus mass by default) highlighted.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — a 2 × 2 × 5 exploration gives 20 rows; infeasible points
  flagged; Pareto front non-dominated.
- **Satisfied by:** INC2-008

### REQ-MDO-008 — Optimisation from the GUI, optionally over motors and propellers

- **Statement:** The user shall run an optimisation from the GUI: objective (flight
  time at V₁ or V₂, range, mass), algorithm (SLSQP, NLOPT_COBYLA, COBYQA), continuous
  variables with bounds, constraints on the margins (not applicable ones dropped) and,
  optionally, categorical choices of motors and propellers from the databases (outer
  loop over the combinations); the best design can be applied to the project. The
  surrogate uncertainty can be constrained (relative σ ≤ setting).
- **Priority:** Must (continuous), Should (categorical motors and propellers)
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — optimum improves on the start; applied design reproduces the
  optimum outputs.
- **Satisfied by:** INC2-001, INC2-008

### REQ-MDO-009 — Analyses are stored and reloaded

- **Statement:** Every exploration and optimisation shall be stored as a study: its
  definition (variables, bounds, choices, objective, constraints, algorithm), the base
  project, all evaluated points with inputs, outputs, uncertainties and feasibility, the
  summary, and the reproducibility metadata (tool version, database and test-data
  hashes, PredimRC profile and workbook hash, date), in a unique dated sub-folder of a
  root folder chosen in the GUI (default: the current working directory). The GUI shall
  list, reopen, compare
  (overlay of two studies), rename and delete studies, and apply a stored design.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — a study saved then reloaded in a new session gives the same
  tables; metadata present.
- **Satisfied by:** INC2-008
