# MVP — Mission (MIS)

### REQ-MIS-001 — A hover time gives the remaining cruise endurance

- **Statement:** Given only a hover time, the system shall return the flight time and
  range of the scenario "vertical climb, hover, transition, cruise at best range until
  reserve, transition, vertical descent".
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — zero hover time gives the pure-cruise endurance.
- **Satisfied by:** MVP-005

### REQ-MIS-002 — A scenario is a list of segments

- **Statement:** A scenario shall be an ordered list of segments of kinds hover,
  vertical climb, vertical descent, transition, cruise and loiter, given by duration,
  distance or altitude change; cruise and loiter speed is a value, `optimal_endurance`
  or `optimal_range`; one segment may be `until_reserve`. In the MVP, vertical climb and
  descent are computed at hover power.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — scenario energy equals the sum of segment energies.
- **Satisfied by:** MVP-005
- **Deferred:** vertical climb by momentum theory, inclined climb, imposed speed checks
  with `margin_speed` (REQ-MIS-007).

### REQ-MIS-003 — Mission results are detailed per segment

- **Statement:** The system shall return flight time, range, energy, peak battery power
  and current per segment, remaining energy and feasibility.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — segment table sums to the totals.
- **Satisfied by:** MVP-005

### REQ-MIS-004 — Optimal cruise speeds are computed at battery level

- **Statement:** The system shall compute the best-endurance speed (minimum battery
  power) and the best-range speed (minimum battery energy per distance), above 1.2 ×
  the minimum polar speed and within motor limits; for the multicopter, from the
  forward-flight power model.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — with constant efficiencies and a parabolic polar,
  V_r / V_e = 3^0.25 within the grid step.
- **Satisfied by:** MVP-005

### REQ-MIS-005 — An energy reserve is enforced

- **Statement:** A reserve (default 20 % of the usable energy) shall never be consumed;
  an `until_reserve` segment keeps the energy of the segments that follow it.
- **Priority:** Must
- **Status:** Accepted (MVP)
- **Verification:** Test — the reserve is left exactly after the scenario.
- **Satisfied by:** MVP-005
