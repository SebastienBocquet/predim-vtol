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
