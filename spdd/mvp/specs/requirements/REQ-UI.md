# MVP — User interface (UI)

### REQ-UI-001 — All MVP inputs are entered through forms

- **Statement:** A local Streamlit GUI shall let the user enter every MVP project input:
  geometry, architecture and rotor layout, mass items, battery, motors, propellers,
  drag sources, scenario and settings, with units shown.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Inspection — each project field has a widget.
- **Satisfied by:** MVP-007

### REQ-UI-002 — The geometry is previewed

- **Statement:** The GUI shall show a top view and a front view (wing panels,
  stabiliser, fuselage, rotor discs) updated from the inputs.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — the plot builder gives a half-span of 912.5 mm for the
  reference wing and draws one disc per rotor.
- **Satisfied by:** MVP-007
- **Deferred:** PredimRC image capture.

### REQ-UI-003 — The results are displayed

- **Statement:** The GUI shall show flight time, range, best-endurance and best-range
  speeds, margins (negative ones highlighted), the mass breakdown, the segment table and
  the battery power versus speed curve.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Inspection; app smoke test.
- **Satisfied by:** MVP-007

### REQ-UI-004 — The project is opened and saved from the GUI

- **Statement:** The GUI shall open and save project files in the same format as the
  API. When the project came from disk, saving defaults to "Save as".
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — a file saved by the GUI loads identically with the API.
- **Satisfied by:** MVP-007

### REQ-UI-006 — Forms have three levels

- **Statement:** Forms shall be generated from the project schema, with required fields
  (marked *, computation blocked while missing), optional fields with their default
  shown (badge "default" until changed, then "entered"), and advanced fields collapsed.
  Validation errors are shown under the field.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — missing required field ⇒ Run disabled; changed default ⇒
  "entered" badge.
- **Satisfied by:** MVP-004, MVP-007

### REQ-UI-007 — Start from a template project

- **Statement:** The GUI shall offer one template project per MVP architecture
  (quadplane, multicopter), with a starter scenario; the results list the values left
  at their default.
- **Priority:** Should
- **Status:** Accepted (MVP)
- **Verification:** Test — both templates load and evaluate; defaults listed.
- **Satisfied by:** MVP-004, MVP-007
