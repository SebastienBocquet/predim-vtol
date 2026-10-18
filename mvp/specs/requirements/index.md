# MVP requirements

These are the requirements of the MVP scope only (42 items). Identifiers are those of
the full specification (`docs/requirements/`). When the MVP covers a requirement only
partly, the statement below is the **MVP statement** and the deferred part is listed
under "Deferred".

## Areas

| Area | File | Requirements |
|---|---|---|
| AERO | [Aerodynamics](REQ-AERO.md) | 001, 002, 003, 004, 005, 007 |
| PROP | [Propulsion](REQ-PROP.md) | 001, 002, 003, 004, 005, 006, 008 |
| DATA | [Component data](REQ-DATA.md) | 001, 003 |
| CFG | [Configuration](REQ-CFG.md) | 001, 002, 003, 004, 006, 007, 008, 009 |
| MIS | [Mission](REQ-MIS.md) | 001, 002, 003, 004, 005 |
| MDO | [Exploration and optimisation](REQ-MDO.md) | 001, 002, 004, 005 |
| UI | [User interface](REQ-UI.md) | 001, 002, 003, 004, 006, 007 |
| NFR | [Non-functional](REQ-NFR.md) | 001, 002, 003, 006 |

## Format

```markdown
### REQ-<AREA>-<NNN> — Title

- **Statement:** The system shall ...
- **Priority:** Must | Should | Could
- **Status:** Accepted (MVP)
- **Verification:** Test | Example | Inspection — where it is checked.
- **Satisfied by:** MVP-00N
- **Deferred:** part of the full requirement left after the MVP (if any).
```

## Glossary

- **Quadplane:** fixed wing with dedicated lift rotors, stopped in cruise, and a separate
  cruise propulsion unit.
- **Multicopter:** wingless rotorcraft with 4, 6 or 8 rotors.
- **Propulsion unit:** one ESC + one motor + one propeller.
- **FM:** figure of merit of a rotor in hover.
- **Scenario:** ordered list of flight segments.
- **Project file:** the YAML file holding all inputs of one design.
- **MIC card:** Model Identity Card (MIC Core format + Interface + Traceability).
