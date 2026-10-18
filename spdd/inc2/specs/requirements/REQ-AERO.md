# Increment 2 — Aerodynamics (AERO)

### REQ-AERO-006 — The PredimRC accessory drag is not used (changed)

- **Statement:** The system shall write 0 in the PredimRC accessory surface (and keep its
  shape unchanged) for every evaluation; all parasitic drag outside the PredimRC
  airframe is modelled by the tool's drag sources (REQ-CFG-004), so that no drag is
  counted twice. The GUI shall state it in the Cruise and Drag tabs.
- **Rationale:** The designer adds booms, arms and stopped rotors in the tool; leaving the
  PredimRC accessory drag in would double count them.
- **Priority:** Must
- **Status:** Implemented (2026-10-14)
- **Verification:** Test (slow) — accessory cell read back as 0; a project file with a
  non-zero `accessory_area_dm2` loses it with a warning (no drag source is created from
  PredimRC: decision of 2026-10-15, the user enters the parasitic drag in the Drag tab).
- **Satisfied by:** INC2-005, INC2-006
- **Replaces:** the full-spec statement "route parasitic drag sources to the PredimRC
  accessory surface".

### REQ-AERO-008 — The PredimRC geometry and power curve are shown as in PredimRC

- **Statement:** The Cruise tab shall reproduce the PredimRC layout at least for the
  geometry (plan view and the inputs table of wing panels, stabiliser and fuselage) and
  the aerodynamic power versus speed curve; it could also show the image of the PredimRC
  geometry drawing exported from the workbook.
  Reference: the PredimRC page `3-Geometrie` (screenshot of 2026-10-14): blocks Aile,
  Stabilisateur, Fuselage, Réglages, geometry view, "Performances en palier (plané)"
  (sink rate, L/D and C_z versus V_x) and "Performances à vitesse imposée" (V_x 1, V_x 2,
  aerodynamic power and L/D versus C_z).
- **Rationale:** The designer reads these two views in PredimRC today; the tool must look
  familiar to be adopted.
- **Priority:** Must (layout), Could (image export)
- **Status:** Implemented (2026-10-15) for the layout; image export not done (Could)
- **Verification:** Inspection against the screenshot; Example — PNG exported from the
  reference case (Could).
- **Satisfied by:** INC2-005, INC2-009

### REQ-AERO-009 — The PredimRC workbook is chosen by folder and profile name

- **Statement:** The user shall give the folder of the PredimRC workbooks (one workbook
  per wing airfoil); the tool shall list the profiles found with the naming convention
  `PredimRC_<profile>.xls` (also `.xlsx`, `.xlsm`) and open the workbook of the profile
  chosen by name in the GUI and in the project file.
- **Rationale:** Several airfoils must be compared; the MVP knows only SD7003 in a fixed
  folder.
- **Priority:** Must
- **Status:** Implemented (2026-10-14)
- **Verification:** Test — profiles discovered in a temporary folder; unknown profile
  rejected with the list of available ones; the folder is a setting saved outside the
  project file, the profile name is in the project file.
- **Satisfied by:** INC2-005

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
