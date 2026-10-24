# Changelog

All notable changes are listed here, newest first. Format: [Keep a Changelog](https://keepachangelog.com),
versions from git tags (setuptools-scm).

## Unreleased

### Fixed
- GUI: every Run of a winged configuration restarted Excel (~7 s, "Could not close the PredimRC
  workbook cleanly" / "Could not quit Excel cleanly"): Streamlit runs each rerun in a new thread
  and COM objects only work in theirs. The PredimRC session now lives in its own thread
  (`ExcelThreadBackend`) and is kept between Runs.
- PredimRC evaluation 1.4 s → 0.25 s: raw COM writes on cached sheets (1 ms per cell instead of
  20 ms through xlwings), unchanged inputs not written again, outputs read in three block reads.
- Rotor model 7× faster (a quadplane Run 11.7 s → 4.8 s, then 0.7 s once the propeller
  surrogate is fitted): the induced-velocity and rotation-speed bisections (~50 iterations
  each, nested) are replaced by a bracketed regula falsi (Illinois); same results to 1e-9.

### Added
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
