# Model Identity Cards (MIC)

Every model of predim-vtol has a card here. PredimRC, the optional aerodynamic backend
of the winged configurations (the default being MIC-AERO-SIMPLE), is an external model
used as is and has no card.

## Format

Cards follow **MIC Core** (IRT SystemX / prostep ivip,
<https://mic-core.github.io/MIC-Core/main/>) with its five groups: administrative data,
purpose and objectives, subject information, implementation, verification and
validation. MIC Core does not standardise ports and parameters, so each card adds an
**Interface** section (taken from the original MIC) and a **Traceability** section
(development only, hidden in the application).

- The **Interface** section lies between `<!-- interface:start -->` and
  `<!-- interface:end -->`. It is **generated** from the `Model` declarations
  (`python -m predim_vtol.core.sync_mic`) and is not edited by hand.
- The descriptive sections are written by hand and kept up to date with the code.
- Users do not edit the cards; they override parameter values in the project file.

Each parameter is described by: name, symbol, unit, description, default value or
origin, physical bounds, source.

## Common administrative data

| Attribute | Value |
|---|---|
| Release | 0.1.0-mvp |
| Release date | 2026-10-12 |
| Release type | specification (pre-release) |
| Model supplier | predim_vtol — Sebastien Bocquet |
| Confidentiality level | 0 — public |
| Legal restriction | LGPL-3.0 (code); data from cited public sources |
| Environment | Python ≥ 3.10, numpy, scipy; no Excel |

## Cards

| Identifier | Model |
|---|---|
| [MIC-AERO-SIMPLE](MIC-AERO-SIMPLE.md) | Simple aerodynamic model of the winged aircraft |
| [MIC-ATM-ISA](MIC-ATM-ISA.md) | ISA atmosphere |
| [MIC-PROP-BAT](MIC-PROP-BAT.md) | Battery pack |
| [MIC-PROP-MOT](MIC-PROP-MOT.md) | Brushless motor, 3 constants |
| [MIC-PROP-PRP](MIC-PROP-PRP.md) | Propeller, momentum theory (MVP) |
| [MIC-PROP-BEM](MIC-PROP-BEM.md) | Propeller, blade elements with momentum inflow (pitch study) |
| [MIC-PROP-SUR](MIC-PROP-SUR.md) | Thrust–power surrogate, physics × Gaussian process |
| [MIC-PROP-CHAIN](MIC-PROP-CHAIN.md) | Power chain battery – cables – ESC – cables – motors |
| [MIC-MIS-TWO](MIC-MIS-TWO.md) | Two-phase flight time (hover, cruise at target speeds) |
| [MIC-MIS-BUDGET](MIC-MIS-BUDGET.md) | Power budget: power sinks per phase |
| [MIC-COST](MIC-COST.md) | Purchase cost and cost of use |
| [MIC-REL](MIC-REL.md) | Motor-out hover (redundancy) |
| [MIC-PROP-UNIT](MIC-PROP-UNIT.md) | Propulsion unit, constant ESC efficiency (MVP) |
| [MIC-CFG-MASS](MIC-CFG-MASS.md) | Mass budget |
| [MIC-CFG-DRAG](MIC-CFG-DRAG.md) | Parasitic drag and drag polar |
| [MIC-MIS-SEG](MIC-MIS-SEG.md) | Segment powers and multicopter cruise speed sweep |
| [MIC-CFG-SIZ](MIC-CFG-SIZ.md) | Motor power law (pre-selection from a target mass) |
| [MIC-CAL-REF](MIC-CAL-REF.md) | Calibration on measured hover and cruise points (procedure) |

## Model chain

```mermaid
flowchart LR
  P[Project YAML] --> MASS[MIC-CFG-MASS]
  P --> DRAG[MIC-CFG-DRAG]
  MASS -->|mass| PR[(MIC-AERO-SIMPLE or PredimRC, quadplane)]
  PR -->|speed polar| DRAG
  ATM[MIC-ATM-ISA] --> SEG[MIC-MIS-SEG]
  BAT[MIC-PROP-BAT] --> UNIT[MIC-PROP-UNIT]
  MOT[MIC-PROP-MOT] --> UNIT
  PRP[MIC-PROP-PRP] --> UNIT
  UNIT --> SEG
  DRAG --> SEG
  MASS --> SEG
  SEG -->|multicopter cruise| TWO[MIC-MIS-TWO]
  BAT --> TWO
  SIZ[MIC-CFG-SIZ] -.->|motor choice| P
  CAL[MIC-CAL-REF] -.->|factors| P
  TWO -.-> CAL
  BEM[MIC-PROP-BEM] -.->|pitch study| P
```
