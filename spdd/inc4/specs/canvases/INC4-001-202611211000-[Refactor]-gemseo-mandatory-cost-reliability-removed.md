---
id: INC4-001
title: GEMSEO mandatory, cost and reliability removed
status: Implemented
branch: refactor/gemseo-required-no-cost
requirements: [REQ-NFR-008, REQ-COST-001, REQ-COST-002, REQ-COST-003, REQ-UI-013]
depends_on: [INC3-007]
owner: Sebastien Bocquet
---

# GEMSEO mandatory, cost and reliability removed

## Requirements

- GEMSEO is a main dependency: no optional import, no `mdo` extra, no message asking to
  install it, no test skipped for its absence.
- The cost models (purchase cost, cost of use) and the motor-out reliability are removed
  without deprecation (REQ-COST-001 to -003 deprecated).
- Project files and stored runs written before keep loading (REQ-UI-013): the removed
  inputs are dropped on load, the stored outputs are kept as they are.

## Entities

| Removed | Was |
|---|---|
| `cost/`, `data/prices.py`, `data/prices.yaml` | prices with sources, purchase cost, cost of use (MIC-COST) |
| `reliability.py` | motor-out hover (MIC-REL) |
| `ui/cost_view.py`, tab *Cost and reliability*, cost KPIs of the Results tab | GUI |
| `CostSpec`, `Project.cost`, `MotorSlot.spin` | project inputs (spin only served the yaw balance of the motor-out check) |
| outputs `cost_purchase`, `cost_per_hour`, `motor_out_tw` | `OUTPUTS_TWO_PHASE`, objectives, labels |
| `"prices"` in `provenance.DATA_FILES` | data hash of the price list |
| extra `mdo` | `gemseo[all] >=6` now in `dependencies` |

## Approach

1. `pyproject.toml`: `gemseo[all] >=6` in the dependencies; the requirement files and
   `uv.lock` recompiled without `--upgrade` (the `core` profile gains GEMSEO, no pin of the
   full profile moves).
2. Optional imports removed: `mdo/__init__.py`, `aero/cache.gemseo_available` and the
   uncached branch of `open_backend`, the `MDO` flag of `ui/studies_page.py`, the
   `importorskip("gemseo")` of the tests.
3. Modules, GUI blocks, outputs and glossary entries of cost and reliability deleted; the
   glossary keeps `item` (column of the mass recap) with a definition of its own.
4. `Project._migrate` → `migrate_cost_reliability`: drops `cost` and the `spin` of the
   motors, like `migrate_scenario_mode`.
5. Packaging: `[ui]` instead of `[ui,mdo]` in the Linux installer, the Windows zip and the
   constraints of the release workflow; README and CONTRIBUTING.

## Structure

No new module. `runs/summary.two_phase_outputs` keeps its `project` argument (callers
unchanged).

## Operations

1. Loading a project: `migrate_cost_reliability` after `migrate_scenario_mode`.
2. Reading a stored run: `upgrade_outputs` keeps every stored output, so the `cost_*` and
   `motor_out_tw` columns stay in the run collection for old runs, NaN for new ones.
3. `data_changes`: a source recorded but no longer hashed (`prices`) is not reported.

## Norms

1. Breaking change noted in the CHANGELOG, no alias nor deprecation warning.
2. Line endings LF (files rewritten from Python with explicit bytes).

## Safeguards

1. `tests/test_review_2026_11_18.py`: an old project with `cost` and `spin` loads without
   them; no removed output is produced; the fixture runs `summary_v1` keep their cost
   columns and stay comparable.
2. `tests/runs/test_store.py::test_stored_formats_still_load` unchanged.

## Implementation notes (2026-11-21)

- A folder left with only `__pycache__` after `git rm` is importable as a namespace
  package: no test checks that `predim_vtol.cost` cannot be imported.
- The core profile now resolves to the same numpy, pandas, scipy and pydantic versions as
  the full profile (constrained by GEMSEO).
