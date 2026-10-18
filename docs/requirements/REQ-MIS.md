# Mission requirements (MIS)

### REQ-MIS-001 — A hover time gives the remaining cruise endurance

- **Statement:** The user shall be able to give only a total hover time; the system
  then returns the cruise endurance and range at the optimal speeds with the remaining
  usable energy.
- **Rationale:** Quick first answer without describing a scenario.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — zero hover time gives the pure-cruise endurance.
- **Satisfied by:** SPEC-005

### REQ-MIS-002 — A flight scenario is a list of segments

- **Statement:** The user shall describe a scenario as an ordered list of segments:
  hover, vertical climb, vertical descent, transition, climb, cruise and loiter, each
  given by a duration, a distance or an altitude change, and a speed (fixed or
  "optimal"); the last segment may be "until reserve".
- **Rationale:** VTOL missions mix phases with very different powers.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — energy of a scenario equals the sum of segment energies.
- **Satisfied by:** SPEC-005

### REQ-MIS-003 — The mission results are detailed per segment

- **Statement:** The system shall return the total flight time, range, energy and
  peak battery power and current per segment, the remaining energy, and whether the
  scenario is feasible with the reserve.
- **Rationale:** The designer must see which segment drives the battery.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — results table sums to totals.
- **Satisfied by:** SPEC-005

### REQ-MIS-004 — Optimal cruise speeds are computed at battery level

- **Statement:** The system shall compute the speed of maximum endurance (minimum
  battery power) and of maximum range (minimum battery energy per distance),
  including propulsion efficiencies and parasitic drag, within the flight envelope
  (above stall speed margin, within motor limits).
- **Rationale:** The aero optimum differs from the battery optimum when propeller
  efficiency varies with speed.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — with constant efficiencies, the speeds equal the aero
  minimum-power and maximum-L/D speeds.
- **Satisfied by:** SPEC-005

### REQ-MIS-005 — An energy reserve is enforced

- **Statement:** The system shall keep an energy reserve (default 20 % of the usable
  energy, user-settable) not available to the scenario.
- **Rationale:** Safe landing and battery health.
- **Priority:** Must
- **Status:** Proposed
- **Verification:** Test — "until reserve" segment stops at the reserve.
- **Satisfied by:** SPEC-005

### REQ-MIS-006 — Scenarios are reusable files

- **Statement:** Scenarios should be storable as named entries of the project file and
  as standalone files, so that one design can be evaluated against several scenarios.
- **Rationale:** Exploration compares designs over a set of missions.
- **Priority:** Should
- **Status:** Proposed
- **Verification:** Test — a standalone scenario file is loaded and run.
- **Satisfied by:** SPEC-005

## Added by increment 2 (2026-10-14)

### REQ-MIS-008 — Two-phase flight time (hover + cruise at target speeds)

- **Statement:** The main evaluation shall reproduce the designer's process: a hover time
  t_h at the hover battery power P_h (REQ-PROP-005, REQ-PROP-009), then cruise at each
  target speed V_k at the cruise battery power P_c(V_k), until the reserve:
  t_c,k = (E_avail − P_h·t_h) / P_c(V_k), flight time t_h + t_c,k, range V_k·t_c,k.
  E_avail = (1 − reserve)·E_nom, reserve 20 % by default, E_nom = n_s·V_nom·C the
  nominal energy (decision 2026-10-14: 80 % of the nominal energy; the usable fraction
  is not applied); E_nom and E_avail are displayed. The target speeds
  default to the minimum-power and maximum-L/D speeds of the aerodynamic power curve,
  are editable, and are written into the PredimRC Vx 1 / Vx 2 inputs. Results give,
  for each target speed, P_h, P_c, energies, flight time, range, the uncertainty
  propagated from the surrogate, and the margins.
- **Rationale:** The designer adopts the tool only if it computes the flight time the
  way he does, so that he can check it by hand.
- **Priority:** Must
- **Status:** Implemented (2026-10-15)
- **Verification:** Test — flight time equals the formula from the displayed powers to
  1e-9; zero hover time gives the cruise-only endurance; Example — designer's tricopter
  and quadplane template.
- **Satisfied by:** INC2-007
- **Note:** the MVP segment scenarios (REQ-MIS-002) remain an advanced mode.

## Added by increment 3 (2026-10-18)

### REQ-MIS-009 — The power budget lists every power sink

- **Statement:** For hover and each target speed, the system shall split the battery
  chemical power into: useful aerodynamic power (hover: Σ T^1.5/√(2ρA); cruise: D·V),
  propeller losses (shaft − useful), motor losses (copper I²R_m and no-load I₀·U),
  ESC losses, cable losses (main, DC, phase), battery internal losses and avionics. The
  sinks sum to the chemical power. The Results tab shows them as a table and a stacked
  bar chart.
- **Priority:** Must
- **Status:** Implemented (2026-10-18)
- **Verification:** Test — the sum of the sinks equals the chemical power to 1e-9
  relative for the tricopter and the quadplane.
- **Satisfied by:** INC3-002
