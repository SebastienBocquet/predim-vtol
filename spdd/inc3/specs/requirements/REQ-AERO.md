# Increment 3 — Aerodynamics (AERO)

### REQ-AERO-009 — The PredimRC workbook is chosen by folder and profile name (changed)

- **Statement:** The user shall give the folder of the PredimRC workbooks (one workbook
  per wing airfoil); the tool shall list the profiles found with the naming convention
  `PredimRC_<profile>.xls` (also `.xlsx`, `.xlsm`) and open the workbook of the profile
  chosen by name. The folder and the naming rule are shown and editable in the aircraft
  configuration tab, next to the profile selector (not only in the sidebar settings).
  The workbooks are not stored in the repository.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** App test — the folder input is in the first tab; changing it updates
  the profile list.
- **Satisfied by:** INC2-005, INC3-002

### REQ-AERO-012 — The CG entered is checked against the PredimRC CG

- **Statement:** For a winged aircraft, after a Run, the aircraft configuration tab shall show
  next to the CG entered the CG given by PredimRC for the static margin entered (mm from the
  wing root leading edge, `3-Geometrie!D30`, with the neutral point `D31` and the MAC), and a
  warning when both differ by more than 2 % of the MAC, giving the static margin the CG
  entered would have; a button copies the PredimRC CG into the project.
- **Rationale:** The CG sets the thrust split in hover and the static margin of the wing;
  both must describe the same aircraft (feedback of 2026-10-19).
- **Priority:** Should
- **Status:** Implemented (2026-10-19)
- **Verification:** Test — the PredimRC MAC and MAC leading edge equal the ones computed from
  the wing panels (same reference as the motor stations); warning levels of the check.
- **Satisfied by:** INC3-005
