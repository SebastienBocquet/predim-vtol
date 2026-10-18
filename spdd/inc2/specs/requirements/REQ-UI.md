# Increment 2 — User interface (UI)

### REQ-UI-002 — The geometry is previewed per configuration (changed)

- **Statement:** The GUI shall show top and front views of the chosen configuration:
  wing, stabiliser (V-tail projected), fuselage, booms or arms (including V-arms), every
  motor drawn by role (lift disc, cruise disc, tilting motor), motor numbers, CG.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — one disc per motor and per role for each template.
- **Satisfied by:** INC2-001, INC2-006

### REQ-UI-003 — The results follow the two-phase evaluation (changed)

- **Statement:** The Results tab shall show, per target speed: hover power, cruise power,
  energies, flight time and range with their uncertainty, the margins (negative in red),
  the front / rear thrust ratio, the mass breakdown, and the link to the data behind
  each power (REQ-PROP-012).
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Inspection; app test — KPI tiles present for V₁ and V₂.
- **Satisfied by:** INC2-009

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
