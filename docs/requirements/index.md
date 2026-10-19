# predimrc_wrapper requirements

This section states **what the pre-sizing tool must do**, independently of how a given
feature implements it. The requirements are stable: they outlive the branches and the
features that satisfy them.

The *how* lives in the SPDD specifications (REASONS canvases) in `spdd/prompt/`. Each
canvas lists the requirements it satisfies, and each requirement lists the canvases
that satisfy it. The strategic analysis is in
`spdd/analysis/SPEC-000-202610101144-[Analysis]-vtol-presizing-tool.md`.

## Scope

Pre-sizing of electric RC aircraft with vertical take-off: **quadplane** (dedicated lift
rotors + cruise propulsion), **pure multicopter** and **tilt-rotor**. The aerodynamics
of the wing-borne configurations come from the PredimRC Excel workbook, driven in the
loop. The main outputs are flight time (endurance), range and optimal flight speeds for
a user-defined flight scenario. The model is wrapped as a GEMSEO discipline for
exploration and optimisation, and a Streamlit GUI helps entering the inputs.

## Areas

| Area | File | Scope |
|---|---|---|
| AERO | [Aerodynamics](REQ-AERO.md) | PredimRC wrapper: geometry, settings, polars, drag |
| PROP | [Propulsion](REQ-PROP.md) | battery, motor, propeller, hover and cruise operating points |
| DATA | [Component data](REQ-DATA.md) | motor and propeller databases, provenance |
| CFG | [Configuration](REQ-CFG.md) | VTOL architectures, rotor layout, mass budget, parasitic drag |
| MIS | [Mission](REQ-MIS.md) | flight scenarios, endurance, range, optimal speeds |
| MDO | [Exploration and optimisation](REQ-MDO.md) | GEMSEO discipline, DOE, optimisation |
| UI | [User interface](REQ-UI.md) | Streamlit input forms, geometry preview, results |
| NFR | [Non-functional](REQ-NFR.md) | platform, units, tests, reproducibility, validation |
| COST | [Cost and reliability](REQ-COST.md) | purchase cost, cost of use, motor-out hover |

## Specifications

| Id | Canvas | Depends on |
|---|---|---|
| SPEC-001 | [Fix] aero — PredimRC wrapper hardening | — |
| SPEC-002 | [Feat] prop — battery, motor, propeller models | — |
| SPEC-003 | [Feat] data — motor and propeller database | SPEC-002 |
| SPEC-004 | [Feat] aircraft — VTOL configuration, mass budget, drag sources | SPEC-001, SPEC-002, SPEC-003 |
| SPEC-005 | [Feat] mission — flight scenario solver | SPEC-004 |
| SPEC-006 | [Feat] mdo — GEMSEO discipline | SPEC-005 |
| SPEC-007 | [Feat] ui — Streamlit application | SPEC-005 |

### Increment 2 — the designer's workflow (2026-10-14)

Two-phase flight time (hover from thrust–power test data through a Gaussian-process
surrogate, cruise from the PredimRC aerodynamic power at two target speeds), power
chain, V-arms, stored studies, help on every quantity. Scope, decisions and open
questions: [`spdd/inc2/README.md`](../../spdd/inc2/README.md); canvases in `spdd/inc2/specs/canvases/`.

| Id | Canvas | Depends on |
|---|---|---|
| INC2-001 | [Sync] post-MVP code (motor list, sizing, calibration, pitch, optimisation) | MVP-007 |
| INC2-002 | [Feat] data — propellers, thrust–power tests, flight test points | INC2-001 |
| INC2-003 | [Feat] prop — thrust–power surrogate (physics × Gaussian process) | INC2-002 |
| INC2-004 | [Feat] prop — power chain and cables | INC2-001 |
| INC2-005 | [Feat] aero — PredimRC profiles, iso-model curve, accessories off | INC2-001 |
| INC2-006 | [Feat] cfg — drag sources with V-arms | INC2-001 |
| INC2-007 | [Feat] mission — two-phase flight time | INC2-003, -004, -005, -006 |
| INC2-008 | [Feat] mdo — exploration, optimisation, studies | INC2-007 |
| INC2-009 | [Feat] ui — workflow tabs, propeller sizing, test data, MIC page, help | INC2-007, INC2-008 |

## Writing a requirement

A requirement is identified by `REQ-<AREA>-<NNN>`. An identifier is never reused nor
renumbered: a requirement which no longer applies is marked `Deprecated`, with the
identifier of the requirement replacing it, if any.

```markdown
### REQ-PROP-003 — The motor operating point is computed from its constants

- **Statement:** The system shall ...
- **Rationale:** Why it matters for the designer.
- **Priority:** Must | Should | Could
- **Status:** Proposed | Accepted | Implemented | Deprecated
- **Verification:** Test | Example | Inspection — where it is checked.
- **Satisfied by:** SPEC-NNN, ...
```

Guidelines:

- One requirement states one need, with "shall" (Must) or "should" (Should, Could).
- State the need of the user, not the design. The design goes in the canvas.
- A requirement is verifiable: name the test, the runnable example or the inspection
  which checks it.
- `Satisfied by` lists the canvases (`SPEC-NNN`) implementing it, in both directions.

## Lifecycle

1. A requirement is added as `Proposed`, usually by a `/spdd-analysis` of a new need.
2. It becomes `Accepted` when reviewed by the owner.
3. It becomes `Implemented` when a canvas satisfying it is `Implemented` and its
   verification passes.

## Glossary

- **Quadplane:** fixed-wing aircraft with dedicated vertical lift rotors (stopped in
  cruise) and a separate cruise propulsion unit (stopped or idle in hover).
- **Tilt-rotor:** fixed-wing aircraft whose rotors tilt; the same propulsion units
  provide lift in hover and thrust in cruise.
- **Multicopter:** wingless rotorcraft (quad, hexa, octo), lift and propulsion by
  rotors only.
- **Propulsion unit:** one motor + one propeller + one ESC.
- **Figure of merit (FM):** ratio of ideal induced power to actual shaft power of a
  rotor in hover.
- **Drag source:** an element adding parasitic drag (booms, stopped rotors, landing
  gear, payload pod...).
- **Scenario:** an ordered list of flight segments (hover, transition, cruise...).
- **Endurance:** flight time achievable with the usable battery energy.
- **Project file:** the YAML file holding all the inputs of one design study.

### Increment 3 — feedback of 2026-10-17, configurations, cost and reliability (2026-10-18)

Project tooling (vimseo template), GUI fixes and clarity (units, power budget, test data
explanation, navigation), tilt mask, user templates, diagonal booms with frontal-area
drag, cost models and motor-out reliability. Scope and decisions:
[`spdd/inc3/README.md`](../../spdd/inc3/README.md); canvases in `spdd/inc3/specs/canvases/`.

| Id | Canvas | Depends on |
|---|---|---|
| INC3-001 | [Chore] tooling — tox, ruff, pre-commit, coverage, CI | INC2-009 |
| INC3-002 | [Fix] ui — bugs, units, explanations, power budget, navigation | INC3-001 |
| INC3-003 | [Feat] cfg — tilt mask, user templates, positions drawing, diagonal booms | INC3-002 |
| INC3-004 | [Feat] cost — prices, cost of use, motor-out reliability | INC3-003 |
| INC3-005 | [Fix] ui — motor layout box, two-phase only with calibration, CG check | INC3-004 |
