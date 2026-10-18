# MVP — Aerodynamics (AERO)

### REQ-AERO-001 — A user geometry is evaluated by PredimRC

- **Statement:** The system shall evaluate the aerodynamics of a user geometry (wing
  of up to 5 panels, horizontal stabiliser, fuselage) with the PredimRC SD7003
  workbook, and return its polars versus speed and versus lift coefficient.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test (slow, Excel) — `tricoptere_short_2` reproduced within 0.5 %
  (surface 30.80 dm², total span 1825 mm, aspect ratio 9.83, CG 30.1 %).
- **Satisfied by:** MVP-001
- **Deferred:** other airfoils (REQ-AERO-009).

### REQ-AERO-002 — The PredimRC template is never modified

- **Statement:** An evaluation shall not modify the workbook stored in `profiles/`,
  including when the evaluation fails.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — template file hash unchanged after a successful and a
  failing run.
- **Satisfied by:** MVP-001

### REQ-AERO-003 — All the settings entered are applied

- **Statement:** Mass, static margin (in %) and trim lift coefficient `cz_reg` (imposed
  value, multiple of 0.05 as in the PredimRC spinner) shall be written into the
  workbook before computing. PredimRC has no reference-speed input; values at a given
  speed are interpolated in Python.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test (slow) — cells read back after a run.
- **Satisfied by:** MVP-001
- **Deferred:** `cz_reg` derived from a reference speed (REQ-AERO-010).

### REQ-AERO-004 — Drop-down inputs are given by their label

- **Statement:** Drop-down inputs (stabiliser airfoil and opening, fuselage shape and
  beam, wing position, linked incidence, accessory shape) shall be given by their
  PredimRC label; an unknown label shall be rejected with the list of allowed labels.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test (slow) — valid label accepted, invalid label raises.
- **Satisfied by:** MVP-001

### REQ-AERO-005 — Drag and required power versus speed are available

- **Statement:** The system shall provide, versus speed, the drag, the power required
  in level flight and the lift-to-drag ratio, and the minimum-power and best-L/D speeds.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — D·V equals the required power within 1 %.
- **Satisfied by:** MVP-001

### REQ-AERO-007 — Successive evaluations reuse one Excel session

- **Statement:** Successive evaluations shall reuse the same Excel instance and
  workbook copy, and the cost of one evaluation shall be measured and reported.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test (slow) — 20 evaluations in one session; timing logged by
  `examples/mvp/benchmark_aero.py`.
- **Satisfied by:** MVP-001
- **Deferred:** pool of Excel instances (REQ-MDO-006).
