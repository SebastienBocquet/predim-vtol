# Increment 2 — Exploration and optimisation (MDO)

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
