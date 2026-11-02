# Changelog

All notable changes are listed here, newest first. Format: [Keep a Changelog](https://keepachangelog.com),
versions from git tags (setuptools-scm).

## Unreleased

### Changed
- Static rotation speed of the blade-element propeller in closed form: C_T does not depend
  on n at V = 0, so n = √(T / (ρ C_T0 D⁴)) with one evaluation instead of about 13 (halvings,
  then regula falsi). Same result to 1e-15. `evaluate_two_phase` about 4 times faster on a
  tricopter with a hover calibration, where the static search took 80 % of the time
  (13.7 → 3.1 s, both versions alternated on the same machine). Forward flight keeps the
  root finding.

### Fixed
- Cruise power at the target speeds (two-phase): near the stall edge V₁ could be overestimated
  by 10–40 % (−12 % reported between the curve and V₁ on a quadplane with large drag sources).
  The PredimRC imposed-speed grid (airfoil Cz step 0.15) keeps one node in the stall drag rise,
  beyond the end of the polar, and the linear interpolation towards it biased every Cz above
  the previous node. The block is now read by a parabola on its nodes up to the last Cz of
  the polar; beyond them the polar value is used, with a warning. The trimmed wing Cz now
  includes the stabiliser lift (from the PredimRC polar rows; +0.3 to +2.4 % in Cz on the
  easyglider quadplane). A warning is given when the interpolated curve and the block differ
  by more than 3 % (`IsoCheck.warnings`); a target point read on the polar says so
  (`TargetPoint.source`).
- Thrust-power surrogate: each test table now carries its own measurement noise (log variance
  of its P vs U·I disagreement) instead of one noise for all. With the MT2216 tables (up to
  5 % disagreement) the 95 % interval covered 87.5 % of the points (guarantee: 90–99 %); it
  covers 91 % now (LOO mean error 1.6 %). The quadplane template hover (MN2806-650 at
  13.8 V, tested at 15.3 V) stays flagged untrusted: σ 5.2 % for a 5 % threshold.
- Prices of the T-Motor MT2216 KV1100 and KV900 (US$60, `search` status, the KV900 price
  assumed equal to the KV1100 one); help entry of "motor current with T/W min (A)".
- Data tests: a source may be a document supplied by the user (data/README.md), and the
  P = U·I check of those tables allows 6 % (the T-Motor MT2216 tables disagree by up to 5 %).
- Two-phase calibration: a reference point the model cannot reach (e.g. a mass in g typed as
  kg) failed with a SciPy "function value is NaN" error; it now names the point and the mass.
- GUI: every Run of a winged configuration restarted Excel (~7 s, "Could not close the PredimRC
  workbook cleanly" / "Could not quit Excel cleanly"): Streamlit runs each rerun in a new thread
  and COM objects only work in theirs. The PredimRC session now lives in its own thread
  (`ExcelThreadBackend`) and is kept between Runs.
- GUI tables (mass items, test data, wiring overrides, motors, cost overrides): a value often
  had to be entered several times, the editor getting its own edited rows back at each rerun.
  It now keeps the table it was first given (`forms.editor_base`).
- Masses and battery tab: the mass breakdown, the mass recap and the battery text follow the
  edits at once, without Run.
- Sidebar: "Save as template" pre-fills the current user template (else the configuration
  name), says "Update template '<name>'" when that template exists (the "Replace if it exists"
  box is removed) and selects the saved template in the template list. The project
  "Save as" becomes "Project file" / "Save project file", each section saying how it differs
  from the other.
- "Configuration" named two things: the template list becomes "Start from a template" and
  the "Configuration name" field (the project name) becomes "Project name".
- PredimRC evaluation 1.4 s → 0.25 s: raw COM writes on cached sheets (1 ms per cell instead of
  20 ms through xlwings), unchanged inputs not written again, outputs read in three block reads.
- Rotor model 7× faster (a quadplane Run 11.7 s → 4.8 s, then 0.7 s once the propeller
  surrogate is fitted): the induced-velocity and rotation-speed bisections (~50 iterations
  each, nested) are replaced by a bracketed regula falsi (Illinois); same results to 1e-9.

### Added
- Yaw by tilting motors (Mission tab): `yaw_tilt` = none, front (the lift motors ahead of the
  CG, tilt-rotor) or rear (behind the CG, tricopter rear rotor), and the maximum yaw tilt
  `yaw_tilt_max_deg` δ. Worst case: front, differential tilt about the transition axis, one
  side at θ − δ (vertical component sin(θ − δ)) and the other at θ + δ, both ways; rear,
  lateral tilt, sin θ · cos δ; each motor keeps its hover vertical share F and gives
  T = F / k. Rows in the hover table of Results, margin `yaw_tilt` (feasibility),
  `TwoPhaseResult.yaw_cases`.
- Stored runs (REQ-UI-013): Results tab, "Save run" stores the result with a copy of the
  project under `<studies folder>/runs/<date>-<name>/` (`project.yaml`, `summary.json`,
  `result.json`, `metadata.json`). New "Runs" page: filters (architecture, project, dates,
  name, query, feasible only), table of the runs, varying inputs, comparison table, relative
  differences to a reference run, figures superposing the runs or the families of runs
  differing by one input; rename, delete, open the project of a run, re-run it with the
  current data. API `predimrc_wrapper.runs` (`load_runs`, `RunStore`, `RunResults`:
  `filter`, `varying_inputs`, `families`, `to_dataframe`, `compare_to`, `visualize`), ported
  from the results collections of VIMSEO. The inputs of a stored run are recomputed from its
  project migrated to the current format; a project that no longer loads falls back to the
  stored inputs.
- Provenance (`predimrc_wrapper.provenance`): studies and runs record a hash per source of
  reference data (motors, propellers, prices, drag shapes, boom sections, thrust tests, user
  data folder, PredimRC workbook); `data_changes` names the sources changed since, and the
  Runs page warns when the compared runs do not share the same data or tool version.
- Custom motors: the motor database merges the user file `<user data>/motors.yaml`
  (`$PREDIMRC_USER_DATA`, else `~/.predimrc_wrapper/data`) with the shipped motors, as for
  the propellers. Configuration tab, "Add a custom motor to the database": a form that saves
  the motor there (`add_user_motor`) and can set it as the motor of a propulsion unit type;
  the motor is then offered in the motor lists of the unit types. Only the fields used by the
  computations are required for a user motor (id, role, Kv, Rm, I0, Imax, Pmax, mass);
  manufacturer, product line, source, date and status are optional.
- Hover tab, under the test data: "Add a propeller to the database" (user file
  `<user data>/propellers.yaml`, `add_user_propeller`) and "Add a thrust–power test" (motor,
  propeller, voltage, table typed or filled from a CSV; written in `<user data>/thrust_tests/`
  by `add_user_test`, which checks that the motor and the propeller exist). The surrogate is
  fitted again on the shipped and user tests at the next Run (cache keyed by the test data
  hash). An empty power is voltage × current. For user propellers and tests too, the fields
  no computation uses (manufacturer, name, bench, source, date, status) are optional.
- `csv_table`: the CSV reading of `import_csv`, from a text.
- Propulsion unit types can be renamed (the motors follow) or removed, their motors
  taking the type chosen (a type used by motors could not be removed).
- Results tab: the hover table also lists the tilting motors at the transition tilt
  (T = F / sin θ), with a phase column and the motor current margin; the hover and cruise
  tables are stacked instead of side by side. The margin descriptions say whether the tilt is
  included (transition, hover thrust within test data, battery C) or not (thrust-to-weight,
  motor power, motor current).
- Results tab, hover table: margins with the safety factor T/W min (Mission tab), per motor:
  thrust with T/W min, margin with T/W min against the motor limits (its worst hover row is
  the thrust-to-weight tile) and against the test data, motor current with T/W min and its
  current margin (1 − I / I_max). A caption separates them from the
  margins without safety factor.
- Cruise tab: longitudinal stability read from PredimRC (centrage, foyer, marge statique,
  volume de stab, calage stab, Vé longi.) with the PredimRC descriptions of each quantity.
- Persistent cache of the PredimRC evaluations: GEMSEO discipline with an HDF5 cache
  (`aero_cache`, file `~/.predimrc_wrapper/predimrc_cache.h5`, setting `predimrc_cache` or
  `$PREDIMRC_CACHE`); a cached evaluation does not start Excel. Entries are keyed by the
  workbook content, so a modified workbook starts new entries. Without GEMSEO, no cache.
- Drag tab: one form per drag source with only the fields of its type, a type list and an
  Add button, a Remove button per source (replaces the table).
- Costs in euros: database prices (USD) converted at the ECB rate of the price list,
  `cost.usd_per_eur` to change it; frame, avionics and overrides entered in euros.
- Vertical phases: climb to the transition altitude, hover, transition (tilting motors at a
  tilt angle, vertical thrust T·sin θ, transition margin), descent; table of the phases.
- Cable mass (copper + silicone) in the mass budget and the Power chain tab; mass recap by
  component; battery mass ↔ capacity shown with the specific energy.
- CG check: the PredimRC CG for the static margin entered is shown next to the CG entered,
  with a warning above 2 % of the MAC and a button to use it.
- Two-phase calibration on a measured hover point (motor powers of the test data) and cruise
  point (drag factor), applied by every Run and study.
- Project tooling as in vimseo: tox (tox-uv), ruff, pre-commit, coverage, GitHub Actions, compiled
  requirements.
- Results: power budget, every power sink per phase (MIC-MIS-BUDGET).
- Test data tab: explanation with an energy chain sketch and the formulas of each phase.
- Studies page in the sidebar (exploration, optimisation, stored studies).
- PredimRC folder in the first tab of winged configurations.

- Tilt mask (ArduPilot Q_TILT_MASK): any set of tilting motors, e.g. tricopter with wing and only
  the rear motor tilting; quick choices front / rear / all / none.
- User templates: save the current project as a template, rename and delete them.
- Booms set in the first tab: parallel or diagonal (one per lift motor from an anchor under the
  fuselage), section round / square / profiled; drag on the frontal area (cross-flow, Hoerner)
  shown in the Drag tab; cables along the booms.
- Motor positions drawing with the reference point and the dimensions of each motor.

- Cost and reliability tab: purchase cost from a price list with sources (MIC-COST), cost of
  use per flight and per flight hour, motor-out hover check and single points of failure
  (MIC-REL); KPIs in Results; outputs and objectives for exploration and optimisation.

### Changed
- `pandas` is a dependency (collection of the runs). The outputs of the two-phase mode
  (`OUTPUTS_TWO_PHASE`, `two_phase_outputs`) live in `predimrc_wrapper.runs.summary`, shared
  by the GEMSEO discipline and the stored runs.
- Stopped rotor drag: new `blade_position` of the source (`aligned` / `random` / `crosswind`,
  default `random`). The single C_d,b 0.05 ("blades aligned") is replaced by
  `blade_cd_aligned` 0.015 (skin friction) and `blade_cd_crosswind` 0.15 (sections at their
  pitch angle, worst case); a random stop takes their mean, 0.0825. **Breaking:** the
  `blade_cd` parameter of `DragModel` is removed, and the default stopped-rotor drag rises
  by 65 %.
- 4-in-1 ESC: the power chain is consistent with the board. New wiring options
  `cruise_on_four_in_one` (the cruise motors driven by the board, no separate cruise ESC) and
  `four_in_one_mass_g` (board mass, required with a 4-in-1) and `four_in_one_efficiency`
  (constant-efficiency ESC model, default 0.95, for every channel of the board: chain, hover
  and cruise powers, ESC-input test data). A board drives 4 motors at most, an error
  otherwise. The board mass appears in the
  Masses tab and the mass budget, and replaces the ESC mass of the motors it drives; its loss
  is a new "4-in-1 ESC" bar of the power budget (the ESC bar keeps the separate ESCs only);
  wiring, cost and reliability follow the cruise option.
- **Breaking**: the ESC mass of a propulsion unit type (`esc_mass_g`) has no default (was
  30 g); it is required only for the types with separate ESCs, an error naming the types
  otherwise. Format-1 projects keep 30 g on migration.
- First tab: motor layout in a collapsed box under the wing geometry; the layout generator is
  removed. Battery defined by its mass or its capacity, only the matching field shown.
- The GUI keeps only the two-phase flight time; the scenario mode stays in the Python API.
- Tricopter-with-wing template: units `front` / `rear`, CG = PredimRC CG, rear motor on a tail
  boom at 600 mm with the front motor.
- Wing, stabiliser and fuselage entered in the first tab (the Cruise tab shows the results).
- Propeller overlap error names the motors, their diameters and the distance missing.
- Templates: the manual boom drag sources become the booms of the configuration (same drag).
- Thrust shown in N with kg in parentheses, speeds in km/h (pitch stays in inches).
- Tab order: Cruise and Drag before Hover.
- Propeller sizing: cruise motors (V1 / V2) apart from the lift-only motors (hover).

### Fixed
- Hover chart: surrogate curves drawn in grams while the points were in N.
- Cable gauges sized for the motor maximum current (the cruise chain used thinner cables).
- IndexError in the Power chain tab when motors were removed after a Run.

## 0.2.0 — increment 2 (2026-10-15)

### Added
- Motor list with roles and tilting motors; tricopter and winged tricopter templates.
- Thrust–power surrogate (physics × Gaussian process) on manufacturer tables, with error guarantee.
- Power chain (battery, cables, ESC, motors) with losses per segment.
- PredimRC profiles by folder, iso-model cruise curve at two target speeds, accessory drag off.
- Two-phase flight time (hover, then cruise at V1 / V2) and its GUI (hover, cruise, drag, power chain,
  propeller sizing, test data, exploration, optimisation, studies, MIC cards, glossary).

## 0.1.0 — MVP (2026-10-12)

### Added
- PredimRC wrapper, propulsion / aircraft / mission models, GEMSEO discipline, Streamlit GUI.
