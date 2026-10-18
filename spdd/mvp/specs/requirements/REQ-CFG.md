# MVP — Configuration (CFG)

### REQ-CFG-001 — Quadplane and multicopter are supported

- **Statement:** The MVP shall support the quadplane (dedicated lift rotors + cruise
  unit) and the multicopter (4, 6 or 8 rotors).
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Example — one template project per architecture runs end to end.
- **Satisfied by:** MVP-004
- **Deferred:** tilt-rotor.

### REQ-CFG-002 — The rotor layout is user-defined

- **Statement:** The user shall define the number of lift rotors and a symmetric layout
  (boom span, front and rear stations), and the maximum propeller diameter.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — generated positions are symmetric; the diameter bound is
  checked.
- **Satisfied by:** MVP-004
- **Deferred:** free rotor positions, coaxial pairs.

### REQ-CFG-003 — A mass budget closes the total mass

- **Statement:** The total mass shall be the sum of user items (airframe, VTOL
  structure, payload, avionics), motors, propellers, ESCs and battery, with a breakdown
  per category.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — total equals the exact sum of the items.
- **Satisfied by:** MVP-004

### REQ-CFG-004 — Parasitic drag sources are modelled

- **Statement:** The user shall list dedicated drag sources (booms, stopped rotors,
  free CdS), whose equivalent drag areas are added to the PredimRC polar in cruise.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — total CdS equals the sum of sources; drag increases by
  ½ρV²ΣCdS.
- **Satisfied by:** MVP-004
- **Deferred:** routing to the PredimRC accessory area, landing gear and pod kinds.

### REQ-CFG-006 — The multicopter does not need PredimRC

- **Statement:** A multicopter shall be evaluated without Excel, with a body drag area
  given by the user.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — multicopter project runs with `xlwings` unavailable.
- **Satisfied by:** MVP-004, MVP-005

### REQ-CFG-007 — A design is stored in one project file

- **Statement:** All inputs of a design shall be saved to and loaded from one YAML
  project file, used identically by the API, the GUI and the GEMSEO discipline.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — save / load round trip gives an equal project.
- **Satisfied by:** MVP-004

### REQ-CFG-008 — The project is schema-validated and overridable

- **Statement:** The project shall be a pydantic v2 model (unknown fields forbidden,
  bounded fields, enumerations as `Literal`). `with_overrides` shall accept dotted
  paths and re-validate the whole project; an unknown path shall raise an error with
  close suggestions.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — unknown path ⇒ error with suggestions; out-of-bounds value
  ⇒ pydantic error.
- **Satisfied by:** MVP-004
- **Deferred:** typed per-block override form, JSON Schema export.

### REQ-CFG-009 — A maximum take-off mass can be set

- **Statement:** When `max_takeoff_mass_kg` is set, the system shall report
  `margin_mass = 1 − m / m_max` among the margins.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — m > m_max ⇒ negative margin.
- **Satisfied by:** MVP-004, MVP-006
- **Deferred:** bound of battery sizing (battery sizing is out of the MVP).
