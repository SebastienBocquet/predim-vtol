# Aerodynamics requirements (AERO)

### REQ-AERO-001 — A user geometry is evaluated by PredimRC

- **Statement:** The system shall evaluate the aerodynamics of a user-specified
  geometry (wing up to 5 trapezes, horizontal stabiliser, fuselage, wing airfoil) with
  the PredimRC workbook, and return its polars versus speed and versus lift coefficient.
- **Rationale:** PredimRC is the reference aero model of the tool; the geometry is an
  input of the user, not a result of the sizing.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — `tests/aero/test_predimrc_wrapper.py` (slow, needs Excel),
  reproduction of the `tricoptere_short_2` reference case.
- **Satisfied by:** SPEC-001

### REQ-AERO-002 — The PredimRC template is never modified

- **Statement:** An evaluation shall not modify the PredimRC workbook shipped in
  `profiles/`.
- **Rationale:** The current wrapper saves over the template, so a run changes the
  starting point of the next one and corrupts the reference.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — the template file hash is unchanged after a run.
- **Satisfied by:** SPEC-001

### REQ-AERO-003 — All the settings entered are applied

- **Statement:** Every setting given by the user (mass, static margin, trim lift
  coefficient, reference speed) shall be written into the workbook before computing.
- **Rationale:** Today the trim lift coefficient is silently ignored.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — read back each written cell after a run.
- **Satisfied by:** SPEC-001

### REQ-AERO-004 — Drop-down inputs are given by their label

- **Statement:** The inputs which are drop-down lists in PredimRC (stabiliser profile
  and opening, fuselage shape and beam, wing position, linked incidence, accessory
  shape) shall be given by their PredimRC label, and an unknown label shall be rejected
  with the list of allowed labels.
- **Rationale:** Integer indexes are error-prone and silently produce wrong geometries.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — valid label accepted, invalid label raises.
- **Satisfied by:** SPEC-001

### REQ-AERO-005 — The drag and the required power versus speed are available

- **Statement:** The system shall provide, versus flight speed, the aerodynamic drag,
  the power required for level flight, the lift-to-drag ratio, and the speeds of
  minimum power and of maximum lift-to-drag ratio.
- **Rationale:** The mission solver needs the drag to size the cruise propulsion and
  find optimal speeds.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — drag × speed equals required power within 1 %.
- **Satisfied by:** SPEC-001

### REQ-AERO-006 — Appendages can be accounted for by PredimRC

- **Statement:** The user should be able to route parasitic drag sources to the
  PredimRC accessory surface (surface and shape), so that PredimRC includes them in its
  polar.
- **Rationale:** PredimRC already models an accessory drag; reusing it keeps one
  consistent polar.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — the polar drag increases with the accessory surface.
- **Satisfied by:** SPEC-001, SPEC-004
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-AERO.md#req-aero-006`.

### REQ-AERO-007 — Successive evaluations reuse one Excel session

- **Statement:** Successive evaluations shall reuse the same Excel instance and
  workbook copy, without restarting Excel.
- **Rationale:** Starting Excel costs several seconds; exploration runs hundreds of
  evaluations.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — 20 evaluations in one session; timing logged.
- **Satisfied by:** SPEC-001

### REQ-AERO-008 — An image of the PredimRC geometry view can be captured

- **Statement:** The system could export the geometry drawing of the PredimRC workbook
  as an image, to display it in the GUI.
- **Rationale:** The PredimRC drawing is the reference view the user knows.
- **Priority:** Could
- **Status:** Proposed
- **Verification:** Example — PNG produced from the reference case.
- **Satisfied by:** SPEC-001, SPEC-007
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-AERO.md#req-aero-008`.

### REQ-AERO-009 — Several airfoils are available

- **Statement:** The user should be able to choose the wing airfoil among the PredimRC
  workbooks available in `profiles/`, the list being discovered from the folder.
- **Rationale:** Only SD7003 exists today, the registry is hard-coded and refers to a
  missing NACA2412 file.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — the available profiles are the workbooks of the folder.
- **Satisfied by:** SPEC-001
- **Increment 2 (2026-10-14):** statement changed, see `inc2/specs/requirements/REQ-AERO.md#req-aero-009`.
- **Increment 3 (2026-10-18):** statement changed, see `inc3/specs/requirements/REQ-AERO.md#req-aero-009`.

## Added by increment 2 (2026-10-14)

### REQ-AERO-011 — The aerodynamic power curve is identical to PredimRC (iso-model)

- **Statement:** The aerodynamic power versus speed curve used by the tool, without the
  tool's drag sources and at the PredimRC density, shall equal the curve computed by the
  PredimRC workbook at every PredimRC speed point within 1e-6 relative; the GUI shall
  display the check (maximum deviation) next to the curve.
  The tool writes into PredimRC the flight altitude and temperature (`3-Geometrie!T29`,
  `T30`; density read back in `U30`) and the target speeds V_x 1, V_x 2 (`AB29`, `AB30`);
  the aerodynamic power at each target speed equals the PredimRC "vitesse imposée"
  value at the trimmed C_z = 2mg / (ρSV²) within 1e-6 relative.
- **Rationale:** The designer trusts PredimRC; any difference must come only from what
  the tool adds (drag sources, density), and be visible.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test (slow) — reference case, tool curve versus the PredimRC sheet
  cells; Test — with drag sources, the difference equals ½ρV³·ΣCdS exactly.
- **Satisfied by:** INC2-005
