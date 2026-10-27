# Increment 3 — Propulsion (PROP)

### REQ-PROP-007 — The propeller pitch is sized for the two target speeds (changed)

- **Statement:** As in increment 2, with the units split in two sections: the **cruise
  motors** (units with a cruise or tilting motor) sized at V₁ and V₂ with the efficiency
  versus pitch chart, and the **lift motors** (lift-only units) sized in hover, shown
  apart. A lift-only unit is never presented as a cruise motor.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** App test — for a quadplane 4+1 the cruise section lists only the
  pusher unit.
- **Satisfied by:** INC2-009, INC3-002

### REQ-PROP-009 — The power chain gives the losses of each segment (changed)

- **Statement:** As in increment 2, plus: the cable lengths follow the booms (diagonal
  booms: along each boom from the anchor); a change of the ESC topology (4-in-1 or
  separate) or of the motor list after a Run never fails: the hover currents of an
  outdated result are not used.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** App test — Run, switch to a 4-in-1 ESC, the tab renders.
- **Satisfied by:** INC2-004, INC3-002, INC3-003
