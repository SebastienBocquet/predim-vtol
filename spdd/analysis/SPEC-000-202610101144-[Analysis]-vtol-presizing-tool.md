---
id: SPEC-000
title: Pre-sizing tool for RC VTOL aircraft and multicopters, built on PredimRC
status: Draft
requirements: [REQ-AERO-001, REQ-PROP-001, REQ-DATA-001, REQ-CFG-001, REQ-MIS-001, REQ-MDO-001, REQ-UI-001, REQ-NFR-001]
depends_on: []
owner: Sebastien Bocquet
---

# SPDD Analysis: Pre-sizing tool for RC VTOL aircraft and multicopters

## Original Business Requirement

> je souhaite créer dans ce projet un outil de pre dimensionnement avion rc. Le modèle
> aéro vient de predim-rc, dont un wrapper est déjà ébauché. Je souhaite ajouter la
> possibilité de predimensionnement d'un avion VTOL, voir d'un multi coptère. Donc,
> modèle de batterie (énergie massique) lipo, li ion, décharge max, conso en
> stationnaire en fonction du type d'hélice, de données moteurs dispo sur internet
> (choisir quelques gammes de moteur), charge utile. L'utilisateur peut rentrer la masse
> de la structure liée au système VTOL, et des sources de trainée parasites (trainée
> résolue par modèle dédié ou via predim-rc qui peut prnedre en compte des appendices).
> Le type d'hélice optimal peut être défini automtiquement ou surchargé par
> l'utilisateur. La géométrie est spécifiée par l'utilisateur. Une IHM peut aider à
> rentrer tous les paramètres et avoir une première vue de la géométrie (qui peut être
> capturé depuis la visualisation de predim-rc, si c'es techniquement possible). Les
> sorties d'intéret sont le temps de vol, vitesse optimale de vol. L'utilisateur peut
> rentrer le temps de vol en stationnaire, ou mieux un scénario de vol. Une fois le
> modèle stabilisé, il est wrappé dans une discipline GEMSEO pour de l'exploration
> (plusieurs scénarios de vol, variation de paramètres (catégoriel, discret ou
> continu), et lancer de l'optimisation. Utilise le spdd pour capture la spec. Crée
> aussi un dossier de requirements. spdd est installé

Attached: screenshot of the PredimRC sheet `3-Geometrie` for the case
`tricoptere_short_2` (wing 4 trapezes, root chord 200 mm, span 1825 mm, SD7003, mass
1920 g, wing loading 62.3 g/dm², static margin 5 %, Cz trim 0.30).

Decisions taken with the owner (2026-10-10):

- Architectures of the first milestone: quadplane (lift + cruise), pure multicopter,
  tilt-rotor. Tailsitter out of scope.
- PredimRC Excel stays **in the loop** (no Python re-implementation, no surrogate in
  the first milestone).
- GUI technology: Streamlit.
- This step produces the specification only; code is generated canvas by canvas with
  `/spdd-generate`.

### Derived acceptance criteria

| AC# | Description |
|---|---|
| 1 | Battery model LiPo / Li-ion with specific energy and maximum discharge |
| 2 | Hover consumption as a function of the propeller |
| 3 | Motor data from a few commercial ranges found on the internet |
| 4 | Payload, VTOL structure mass entered by the user |
| 5 | Parasitic drag sources, by a dedicated model or by PredimRC appendices |
| 6 | Optimal propeller automatic, overridable by the user |
| 7 | Geometry specified by the user |
| 8 | GUI for all parameters with a geometry preview (PredimRC capture if feasible) |
| 9 | Outputs: flight time and optimal flight speed |
| 10 | Input: hover time, or better a flight scenario |
| 11 | GEMSEO discipline: several scenarios, continuous/discrete/categorical variables, optimisation |
| 12 | Specification captured with spdd and a requirements folder |

## Domain Concept Identification

### Existing Concepts (from codebase)

- **WingGeometry** (`src/predimrc_wrapper/predimrc_wrapper.py`): wing as up to 5
  trapezes (root chord, tip chord, length, sweep, twist, dihedral) in PredimRC units —
  the user-specified geometry of every wing-borne architecture.
- **StabGeometry**: horizontal tail trapezes, lever arm, height, profile, V-opening,
  lateral gap — completes the PredimRC geometry.
- **FuselageGeometry**: fuselage dimensions and shapes, plus one *accessory* surface
  and shape — the existing hook for appendages drag (AC 5).
- **Settings**: mass, static margin, trim Cz, reference speed — the coupling point
  where the mass budget enters PredimRC.
- **AeroResults**: speed polar (speed, sink rate, L/D, Cz) and Cz polar (power, L/D),
  CG/neutral point, wing metrics — the aero input of the mission; it lacks an explicit
  drag.
- **PredimRCWrapper**: Excel/xlwings session on one airfoil workbook, `run()` and
  `run_parametric()` — the aero backend to keep in the loop.
- **PROFILE_FILES**: airfoil → workbook registry, hard-coded, one file missing.

### New Concepts Required

- **BatteryChemistry / Battery**: LiPo or Li-ion pack (series cells, capacity, mass,
  energy, maximum current, internal resistance) — energy store of the mission, part of
  the mass budget.
- **Motor**: brushless motor constants (Kv, Rm, I0, limits, mass) — taken from the
  component database.
- **Propeller**: diameter, pitch, mass, CT/CP versus advance ratio — taken from the
  database; drives hover power.
- **PropulsionUnit**: motor + propeller + ESC efficiency; computes operating points
  (hover thrust, cruise thrust at speed) — shared by lift rotors, cruise unit and
  tilt-rotors.
- **ComponentDatabase**: motors and propellers with provenance, shipped + user folder.
- **VtolConfiguration**: architecture (quadplane, multicopter, tilt-rotor), lift rotor
  count and layout, cruise unit, download factor — owns the propulsion units.
- **MassBudget**: list of mass items (user and computed), total mass — couples
  configuration, battery and PredimRC.
- **DragSource**: parasitic drag element, either dedicated (equivalent area) or routed
  to the PredimRC accessory — feeds cruise drag.
- **FlightSegment / Scenario**: ordered segments (hover, vertical climb/descent,
  transition, climb, cruise, loiter, until-reserve) — the mission definition.
- **MissionResult**: per-segment time, distance, energy, peak power and current;
  totals; optimal speeds; margins — the outputs of interest.
- **Project**: aggregate of all inputs, serialised to one YAML file — single source of
  truth for API, GUI and GEMSEO.
- **PresizingDiscipline**: GEMSEO discipline over a base project, parameter overrides
  as inputs, mission outputs per scenario.

### Key Business Rules

- Lift balance in hover: total rotor thrust = weight × download factor (wing download
  of quadplanes/tilt-rotors) — governs PropulsionUnit, VtolConfiguration.
- Level cruise: wing lift = weight (PredimRC), propulsive thrust = aero drag +
  parasitic drag — governs PropulsionUnit, DragSource, AeroResults.
- In a quadplane, lift rotors are stopped in cruise and add drag; the cruise unit is
  idle in hover. In a tilt-rotor, the same units serve both phases, so one propeller
  must compromise between hover and cruise — governs the propeller selection.
- A multicopter has no wing: no PredimRC call, forward flight by rotor tilt with a
  body drag area.
- Usable energy = nominal energy × usable fraction; a reserve (default 20 %) is not
  available to the scenario.
- Battery power is limited by its maximum discharge rate; motor current by its
  maximum current; thrust-to-weight of the lift system ≥ 1.5 for control authority.
- The total mass depends on the battery mass, and every power depends on the total
  mass: sizing the battery for a scenario is a fixed-point problem.
- Implicit: the PredimRC "Flèche /BA" values (0, 7, 40, 150 for the reference case)
  are leading-edge offsets in mm, not angles in degrees as documented in the wrapper.
- Implicit: PredimRC computes its polar at the mass given in `Settings`; the mass
  written must be the closed total mass, so each mass change requires a new PredimRC
  evaluation.

## Strategic Approach

### Solution Direction

- Keep the existing dataclass style and the `PredimRCWrapper` as the aero backend;
  harden it first (it currently corrupts its template and ignores settings).
- Add the physics as pure-Python packages independent of Excel: propulsion, component
  data, aircraft (configuration, mass, drag, project), mission. Excel is reached only
  through one aero adapter.
- Data flow: Project file → configuration and mass budget → PredimRC polar at total
  mass (wing-borne) or body-drag model (multicopter) → propulsion operating points per
  segment → mission integration → MissionResult. A sizing loop wraps it when the
  battery is sized.
- GEMSEO and Streamlit are thin layers over the same `evaluate(project)` entry point;
  they never call PredimRC directly.

### Key Design Decisions

- **Excel in the loop** (owner decision): faithful but ~1 s per evaluation, Windows
  only, sequential → one Excel session per process, work on a temporary copy of the
  workbook, GEMSEO cache, gradient-free optimisers or DOE; a backend interface leaves
  room for a surrogate later without changing callers.
- **Propeller model**: CT/CP tables when available (APC publishes them for its whole
  range; T-Motor publishes thrust/power tables convertible to static CT/CP), FM and
  constant efficiency fallback otherwise → covers the database without blocking on
  missing data.
- **Motor model**: classic 3-constant model (Kv, Rm, I0) → enough at pre-sizing level
  and published by all target ranges.
- **Battery model**: specific energy + internal resistance sag, no Peukert → simple,
  explains why Li-ion suffers in hover through voltage sag and C limits.
- **Project file in YAML** with dataclasses (no new validation framework) → consistent
  with the existing code; validation in `__post_init__`.
- **Categorical variables in GEMSEO** as integer indexes with a label mapping →
  GEMSEO design spaces are numeric.
- **Database as YAML/CSV files in the package** plus a user folder → editable without
  code, versionable, provenance per entry.

### Alternatives Considered

- Re-implementing PredimRC in Python: faster and portable, but rejected by the owner
  for the first milestone (fidelity to the reference workbook).
- Surrogate of PredimRC: deferred; the backend interface keeps it possible.
- Qt GUI: heavier for the same forms; rejected for Streamlit.
- Blade-element propeller model: needs blade geometry not published by manufacturers.

## Risk & Gap Analysis

### Requirement Ambiguities

- Which motor ranges exactly: proposal T-Motor MN + Antigravity, SunnySky X (lift),
  T-Motor AT (cruise); the owner may prefer others.
- Tilt-rotor transition and tilt mechanism mass: modelled as user mass items and a
  transition segment at hover power; no transition aerodynamics.
- "Vitesse optimale de vol": both max-endurance and max-range speeds are returned.
- Where the screenshot shows a stabiliser "Ouverture (°) 120" in a drop-down: the
  allowed openings must be read from the workbook validation lists.

### Edge Cases

- Battery sizing loop diverging (heavier battery costs more hover energy than it
  brings): detect non-convergence and report the design as infeasible.
- PredimRC polar not covering the requested cruise speed or stall: clip to the polar
  range and report.
- Propeller larger than the layout clearance: excluded from automatic selection,
  error if imposed.
- Required voltage above the battery voltage under load: operating point infeasible.
- Multicopter with no forward segments: endurance = hover endurance.
- Coaxial lift pairs: thrust/power penalty of the lower rotor (default factor).

### Technical Risks

- Excel COM: only one calculation at a time, popup dialogs, zombie Excel processes →
  `display_alerts = False`, context manager with guaranteed quit, timeouts.
- Wrapper defects found: template saved on exit, `cz_reg` never written, `vx1` written
  to `3-Geometrie!AB29` while documented in `Calculs1`, debug `print`, drop-downs passed
  as ints in `sandbox/main.py`, `lever` passed as a list, `static_margin` 0.05 vs 5 %,
  `PROFILE_FILES` pointing to a missing workbook, `.xls` legacy format. To fix in
  SPEC-001 before anything is built on top.
- No drag output: drag must be derived from required power / speed or read from
  additional cells; the cell mapping of PredimRC must be explored with Excel open.
- PredimRC geometry capture: possible through xlwings (export of the chart/shape range
  to PNG) but depends on how the workbook draws the plane; to prototype.
- Internet data: access to manufacturer pages may fail or change; data stored with
  provenance and `estimated` status when not checked.
- Optimisation cost: 100–500 evaluations × ~1–3 s (more with battery sizing loop) →
  minutes to tens of minutes; acceptable for DOE, gradient-based optimisation by
  finite differences discouraged.

### Acceptance Criteria Coverage

| AC# | Description | Addressable? | Gaps/Notes |
|---|---|---|---|
| 1 | Battery LiPo / Li-ion | Yes | REQ-PROP-001/002, SPEC-002 |
| 2 | Hover consumption vs propeller | Yes | REQ-PROP-004/005, SPEC-002 |
| 3 | Motor ranges from internet | Yes | REQ-DATA-001..004, SPEC-003; data fetched at generation |
| 4 | Payload, VTOL structure mass | Yes | REQ-CFG-003, SPEC-004 |
| 5 | Parasitic drag, dedicated or PredimRC | Yes | REQ-CFG-004, REQ-AERO-006; single PredimRC accessory slot |
| 6 | Automatic / imposed propeller | Yes | REQ-PROP-007, REQ-UI-005 |
| 7 | User geometry | Yes | REQ-AERO-001, REQ-CFG-002 |
| 8 | GUI + geometry preview | Partial | REQ-UI-001..005; PredimRC capture is "Could" (REQ-AERO-008) |
| 9 | Flight time, optimal speed | Yes | REQ-MIS-003/004 |
| 10 | Hover time or scenario | Yes | REQ-MIS-001/002 |
| 11 | GEMSEO, variable types, optimisation | Yes | REQ-MDO-001..005; Excel cost |
| 12 | spdd + requirements folder | Yes | `spdd/`, `docs/requirements/` |
