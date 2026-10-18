# User interface requirements (UI)

### REQ-UI-001 — All inputs are entered through forms

- **Statement:** A local web GUI shall let the user enter every input of a project:
  geometry, configuration and layout, mass items, battery, motors, propellers, drag
  sources, scenarios and settings, with units displayed and invalid values reported.
- **Rationale:** The inputs are many; a form is faster and safer than editing YAML.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Inspection — each project field has a widget.
- **Satisfied by:** SPEC-007

### REQ-UI-002 — The geometry is previewed

- **Statement:** The GUI shall display a top and front view of the aircraft (wing
  trapezes, stabiliser, fuselage, rotor discs) updated from the inputs, and could show
  the PredimRC geometry image when available.
- **Rationale:** A visual check catches input errors before computing.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the plot builder returns the expected span and rotor count.
- **Satisfied by:** SPEC-007
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-UI.md#req-ui-002`.
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-UI.md#req-ui-002`.

### REQ-UI-003 — The results are displayed

- **Statement:** The GUI shall display the mass breakdown, the mission results per
  segment, the endurance, range and optimal speeds, the margins, and the battery power
  versus speed curve.
- **Rationale:** The outputs of interest must be readable at a glance.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Inspection.
- **Satisfied by:** SPEC-007
- **Increment 2 (2026-10-14):** statement changed, see `spdd/inc2/specs/requirements/REQ-UI.md#req-ui-003`.

### REQ-UI-004 — The project is saved and loaded from the GUI

- **Statement:** The GUI shall load and save project files in the same format as the
  Python API.
- **Rationale:** Designs created in the GUI are reused in GEMSEO studies.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — file saved by the GUI loads in the API.
- **Satisfied by:** SPEC-007

### REQ-UI-005 — The propeller choice is automatic or imposed in the GUI

- **Statement:** The GUI shall show the automatically selected propeller and let the
  user override it.
- **Rationale:** See REQ-PROP-007.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Inspection.
- **Satisfied by:** SPEC-007

## Added by increment 2 (2026-10-14)

### REQ-UI-008 — Tabs follow the designer's workflow

- **Statement:** The GUI shall be organised in tabs following the workflow: Aircraft
  configuration (title = configuration name, editable; template; motors and their roles,
  tilting motors; CG), Masses and battery, Hover, Cruise (PredimRC layout), Drag, Power
  chain, Propeller sizing, Test data, Results, Exploration, Optimisation, Studies.
  Changing the configuration updates every tab at once. Tabs that do not apply (Cruise
  PredimRC for a multicopter) explain why.
- **Priority:** Must
- **Status:** Implemented (2026-10-15), with an extra Mission tab
- **Verification:** App test — the tab list per configuration; switching configuration
  updates the tabs and the geometry.
- **Satisfied by:** INC2-009
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-UI.md#req-ui-008`.

### REQ-UI-009 — The MIC cards open from the sidebar

- **Statement:** The sidebar shall give access to a page listing the MIC cards of the
  models (identifier, title, status) and showing the selected card, with its generated
  Interface; the help of a quantity links to the card of its model.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** App test — every card of `docs/models` is listed and renders.
- **Satisfied by:** INC2-009

### REQ-UI-010 — Every quantity is defined by a help in the GUI

- **Statement:** Every quantity of the GUI — input fields, table columns, KPI tiles,
  chart axes and legends — shall have a help entry, shown as a tooltip ("?" icon) and in
  a searchable glossary: name, definition, symbol, unit, for an input its default value
  and the source of that default (data sheet, literature, user reference aircraft…), and
  the MIC card of the model using it. Help entries come from one registry fed by the
  project schema descriptions, the model `Port` / `Param` declarations and a glossary
  file for derived quantities.
- **Rationale:** The designer must understand every number before trusting the tool.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — every project field, model port and parameter, KPI and chart
  axis label has a registry entry with definition and unit (a missing entry fails the
  test); app test — tooltips present on the inputs of each tab.
- **Satisfied by:** INC2-009
- **Increment 3 (2026-10-18):** statement changed, see `spdd/inc3/specs/requirements/REQ-UI.md#req-ui-010`.

## Added by increment 3 (2026-10-18)

### REQ-UI-011 — The test data comparison is explained with a sketch and formulas

- **Statement:** The Test data tab shall explain what is compared and how each model
  value is obtained, with formulas and a sketch of the energy chain: hover
  P = Σ surrogate(T_i) + chain losses + avionics; winged cruise = PredimRC power at
  imposed speed + drag sources; multicopter cruise = in-house body C_d·A + drag sources +
  forward-flight rotor model (no PredimRC). The calibration section explains why one
  factor per point and when it applies (scenario mode).
- **Priority:** Should
- **Status:** Implemented (2026-10-18)
- **Verification:** Inspection.
- **Satisfied by:** INC3-002
