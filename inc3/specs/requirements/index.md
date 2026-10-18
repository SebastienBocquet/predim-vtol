# Increment 3 requirements

Requirements new or changed in increment 3. Identifiers are those of the full
specification (`docs/requirements/`), where the same statements are recorded; a
requirement not listed here keeps its previous statement (`inc2/`, `mvp/`).

Status values: `Proposed`, `Implemented (date)`.

## Areas

| Area | File | Requirements |
|---|---|---|
| AERO | [Aerodynamics](REQ-AERO.md) | 009 (changed) |
| CFG | [Configuration](REQ-CFG.md) | 002, 004 (changed), 013, 014 (new) |
| PROP | [Propulsion](REQ-PROP.md) | 007, 009 (changed) |
| MIS | [Mission](REQ-MIS.md) | 009 (new) |
| UI | [User interface](REQ-UI.md) | 002, 008, 010 (changed), 011 (new) |
| NFR | [Non-functional](REQ-NFR.md) | 002 (changed), 008 (new) |
| COST | [Cost and reliability](REQ-COST.md) | 001, 002, 003 (new area) |

## Glossary (additions)

- **Tilt mask:** the set of motors that tilt between hover and cruise (ArduPilot
  `Q_TILT_MASK`); a tilting motor lifts in hover and pushes in cruise.
- **Propulsion unit type:** one motor + propeller + ESC combination; every motor of the
  layout references one, so motors can differ (e.g. 12 in front, 10 in rear).
- **User template:** a project file saved from the GUI and offered as a starting
  configuration.
- **Diagonal boom:** a straight boom from an anchor under the fuselage to one lift motor.
- **Frontal area:** area of a body projected on the plane normal to the flow.
- **Power sink:** where battery power goes: useful aerodynamic power, propeller, motor,
  ESC, cables, battery internal resistance, avionics.
- **Cost of use:** wear cost of a flight hour: battery, motor and propeller replacement.
- **Motor-out:** loss of one motor in hover; survivable when the others can still balance
  the forces and moments within their thrust limits.
