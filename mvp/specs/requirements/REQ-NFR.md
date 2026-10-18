# MVP — Non-functional (NFR)

### REQ-NFR-001 — Only the wing aerodynamics needs Excel

- **Statement:** Only the quadplane wing aerodynamics requires Windows and Excel;
  propulsion, mission, multicopter, GUI forms and data shall run without Excel.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — fast suite passes with `xlwings` unavailable.
- **Satisfied by:** MVP-001, MVP-003, MVP-004, MVP-005

### REQ-NFR-002 — SI internally, user units at the boundaries

- **Statement:** All computations use SI units; user units (mm, g, dm², mAh, in) are
  converted only at the PredimRC, project file and GUI boundaries; every field states
  its unit.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Inspection; test of the conversion helpers.
- **Satisfied by:** MVP-001, MVP-002, MVP-004

### REQ-NFR-003 — Fast tests do not need Excel

- **Statement:** The default test run does not need Excel; Excel tests are marked `slow`
  and skipped when Excel is unavailable.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Inspection — `tests/conftest.py`.
- **Satisfied by:** all MVP canvases

### REQ-NFR-006 — Every model has a MIC card

- **Statement:** Every MVP model outside PredimRC is described by a MIC card in
  `mvp/docs/models/` (MIC Core groups + Interface + Traceability), kept up to date with
  the code; once MVP-002 exists, the Interface section is generated from the `Model`
  declarations.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — generated Interface matches the card; inspection of the
  descriptive part.
- **Satisfied by:** MVP-002, MVP-003, MVP-004, MVP-005
