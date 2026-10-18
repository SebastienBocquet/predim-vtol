# predimrc_wrapper — Increment 3: feedback of 2026-10-17, configurations, cost and reliability

Increment 2 (`inc2/`) gave the designer's workflow in one GUI. The designer's review of
2026-10-17 asks for bug fixes, clearer GUI, more configurations (any tilt mask, diagonal
booms), costs and reliability metrics, and a project template like vimseo. Requirement
identifiers are those of the full specification (`docs/requirements/`); this folder holds
the increment statements and the REASONS canvases.

Status: **specification** (2026-10-18). INC3-001 (tooling) is implemented on `main`; the
other packages are proposed, one git branch each, merged in order A → B → C.

## Feedback of 2026-10-17 and where it goes

| Feedback | Requirement | Canvas |
|---|---|---|
| Project template like vimseo (uv, tox, ruff, pre-commit, tests, CI) | REQ-NFR-008 | INC3-001 |
| Bug: IndexError with a 4-in-1 ESC in the Power chain tab | REQ-PROP-009 | INC3-002 |
| Pitch sizing shows the rear (lift-only) motor although the cruise motors are the front ones | REQ-PROP-007 | INC3-002 |
| Thrust in N with kg in parentheses, speeds in km/h, pitch in inches, other units unchanged | REQ-NFR-002 | INC3-002 |
| Test data tab: clearer explanation, sketch and formulas; multicopter cruise is the in-house drag model, not PredimRC | REQ-UI-011 | INC3-002 |
| Results: recap of every power sink (aero, propeller, motor, ESC, cables, battery, avionics) | REQ-MIS-009 | INC3-002 |
| Drag tab before Hover; Exploration / Optimisation / Studies on their own sidebar page | REQ-UI-008 | INC3-002 |
| PredimRC folder (file `PredimRC_<profile>.xls`) visible in the first tab | REQ-AERO-009 | INC3-002 |
| Tilting motors chosen by a mask (ArduPilot Q_TILT_MASK), e.g. tricopter with only the rear motor tilting; neutral template names; fix the stale tilt table | REQ-CFG-002 | INC3-003 |
| Save the current configuration as a user template from the GUI | REQ-CFG-013 | INC3-003 |
| Explain the propulsion unit types ("New unit type name") | REQ-UI-010 | INC3-003 |
| Wing / stabiliser / fuselage geometry in the first tab | REQ-UI-008 | INC3-003 |
| Motor positions: reference point and dimensions on a drawing; clearer propeller overlap error | REQ-UI-002, REQ-CFG-002 | INC3-003 |
| Diagonal booms from an anchor under the fuselage, one straight boom per lift motor; section profiled / square / round chosen in the first tab; drag from the frontal area, shown in the Drag tab; cables along the booms | REQ-CFG-004, REQ-CFG-014 | INC3-003 |
| Cost models (motors, ESC, frame, cables, battery) in a dedicated tab; price and cost of use (motor, propeller, battery replacement) | REQ-COST-001, -002 | INC3-004 |
| Reliability: motor-out redundancy | REQ-COST-003 | INC3-004 |

## Definition of done

1. `tox -e check` and `tox -e py312` pass; CI runs them on Linux and Windows (Excel tests
   skip themselves without Excel).
2. Switching a tricopter to a 4-in-1 ESC after a Run raises no error; the propeller sizing
   tab shows the cruise motors (pitch versus V₁ / V₂) apart from the lift-only motors.
3. Every thrust is shown as `12.3 N (1.25 kg)`, every speed in km/h; pitches stay in inches.
4. The Results tab shows, for hover, V₁ and V₂, the power of each sink; their sum equals
   the battery chemical power to 1e-9 relative.
5. "Tricopter with wing" with the tilt mask {3} (rear motor only) evaluates; the drawing
   and the motor table agree after every change of the mask.
6. A configuration saved as a user template is listed in the Configuration selector and
   reloads identically.
7. Diagonal round booms: the frontal area, C_d·sin²θ and drag of each boom match a hand
   calculation; the Drag tab lists them; the cable lengths follow the booms.
8. The Cost and reliability tab gives the purchase cost with the source of every price, the
   cost per flight hour, and for each lift motor whether hover survives its loss.

## Work packages (in order)

| Canvas | Branch | Package | Exit criterion |
|---|---|---|---|
| INC3-001 | `main` | [Chore] tooling — tox, ruff, pre-commit, coverage, CI, requirements | DoD 1 |
| INC3-002 | `fix/gui-feedback` | [Fix] ui — bugs, units, explanations, power budget, navigation | DoD 2–4 |
| INC3-003 | `feat/configurations` | [Feat] cfg — tilt mask, user templates, positions drawing, diagonal booms | DoD 5–7 |
| INC3-004 | `feat/cost-reliability` | [Feat] cost — prices, cost of use, motor-out reliability | DoD 8 |

```mermaid
flowchart LR
  T1[INC3-001 tooling] --> A2[INC3-002 GUI feedback]
  A2 --> B3[INC3-003 configurations]
  B3 --> C4[INC3-004 cost and reliability]
```

Each branch is rebased on the previous one before merging (they all touch `ui/app.py`).

## Decisions taken (2026-10-17)

- Tooling on `main` first, then the three branches A → B → C.
- The PredimRC workbooks (`profiles/*.xls`) are not committed (third-party); the folder is
  a setting.
- Units: only thrust (N, with kg in parentheses) and speeds (km/h) change in the GUI;
  pitch stays in inches; SI inside.
- A template is a complete project file. No template per tilt mask: the mask is a project
  input; user templates are saved from the GUI.
- Diagonal booms: one straight boom per lift motor from an anchor under the fuselage. Drag
  by the cross-flow principle on the frontal area (Hoerner).
- Prices copied from manufacturer and retailer pages, with URL, date and currency.
- Reliability starts with the motor-out hover check.
- xlwings floor relaxed to 0.30: `gemseo[all]` caps it at 0.33.16 (2026-10-18).

## Out of increment 3

Transition and climb, wind, ESC thermal model, failure rates (MTBF) beyond the motor-out
check, battery sizing mode, coaxial motors.
