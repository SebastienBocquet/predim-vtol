# Increment 2 requirements

Requirements new or changed in increment 2. Identifiers are those of the full
specification (`docs/requirements/`), where the same statements are recorded; an MVP
requirement not listed here keeps its MVP statement (`mvp/specs/requirements/`).

Status values: `Proposed` (to review by the owner), `Implemented (2026-10-13)` (coded
after the MVP, described by INC2-001, still to review).

## Areas

| Area | File | Requirements |
|---|---|---|
| AERO | [Aerodynamics](REQ-AERO.md) | 006 (changed), 008, 009, 011 (new) |
| CFG | [Configuration](REQ-CFG.md) | 001, 002, 004 (changed), 010, 011 (new) |
| DATA | [Component and test data](REQ-DATA.md) | 001 (changed), 002, 005, 006 (new) |
| PROP | [Propulsion](REQ-PROP.md) | 004, 005, 007 (changed), 009, 011, 012 (new) |
| MIS | [Mission](REQ-MIS.md) | 008 (new) |
| MDO | [Exploration and optimisation](REQ-MDO.md) | 007, 008, 009 (new) |
| UI | [User interface](REQ-UI.md) | 002, 003 (changed), 008, 009, 010 (new) |
| NFR | [Non-functional](REQ-NFR.md) | 005 (changed), 006 (changed), 007 (new) |

## Glossary (additions)

- **Two-phase evaluation:** hover for a given time, then cruise at a target speed until
  the reserve; the designer's way of computing a flight time.
- **Target speed:** a cruise speed chosen on the aerodynamic power curve (V₁, V₂).
- **Thrust–power test data:** measured thrust, electric power, current and rotation
  speed of one motor + propeller (+ ESC) at one voltage, at several throttle settings.
- **Surrogate:** a fast model fitted on data, here a physics model times a Gaussian-process
  correction, giving a mean and a standard deviation.
- **Motor role:** lift (vertical flight only), cruise (forward flight only) or tilt
  (both, tilting motor), like the ArduPilot motor masks.
- **Power chain:** battery, main cables, power distribution, ESC, phase cables, motor.
- **V-arms:** motor arms attached under the fuselage and going diagonally (in a V seen
  from the front) to the motors.
- **Study:** a stored exploration or optimisation (definition, base project, results).
- **Help entry:** the definition of a quantity shown in the GUI (REQ-UI-010).
