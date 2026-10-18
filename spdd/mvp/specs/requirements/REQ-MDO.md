# MVP — Exploration and optimisation (MDO)

### REQ-MDO-001 — The pre-sizing model is a GEMSEO discipline

- **Statement:** The complete evaluation shall be available as a GEMSEO discipline whose
  inputs are parameters of a base project file (dotted paths) and whose outputs are the
  results and margins of one scenario.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — discipline outputs equal `evaluate(project)` for the same
  project.
- **Satisfied by:** MVP-006
- **Deferred:** several scenarios per evaluation (REQ-MDO-003).

### REQ-MDO-002 — Continuous, discrete and categorical variables

- **Statement:** Float, integer and categorical parameters shall be supported; a
  categorical parameter is exposed as an integer index with a label mapping saved with
  the results.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — index ↔ label round trip; design-space bounds and types.
- **Satisfied by:** MVP-006

### REQ-MDO-004 — Optimisation and DOE examples are provided

- **Statement:** The MVP shall provide `optim_quadplane.py`, `optim_multicopter.py` and
  a 20-point DOE that measures run time.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Example — scripts run to completion (quadplane: slow, Excel).
- **Satisfied by:** MVP-006

### REQ-MDO-005 — Excel in the loop is robust

- **Statement:** The discipline shall evaluate sequentially with a single Excel session,
  cache evaluated points, and turn a failed evaluation into NaN outputs flagged
  infeasible without stopping the study.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — repeated input hits the cache; injected failure ⇒ NaN and
  `feasible = 0`.
- **Satisfied by:** MVP-006
- **Deferred:** pool of Excel instances; the 100 configurations / 20 s budget is
  measured but not required.
