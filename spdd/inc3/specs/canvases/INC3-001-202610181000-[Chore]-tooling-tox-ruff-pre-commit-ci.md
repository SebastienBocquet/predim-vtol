---
id: INC3-001
title: Tooling — tox, ruff, pre-commit, coverage, CI, compiled requirements (vimseo template)
status: Implemented
requirements: [REQ-NFR-008, REQ-NFR-003]
depends_on: []
owner: Sebastien Bocquet
---

# Project tooling

## Requirements

- Same developer workflow as `../vimseo`: `tox` runs the tests and the checks; ruff lints
  and formats; pre-commit guards every commit; CI runs on every push.
- Tests without Excel pass everywhere; Excel tests skip themselves (REQ-NFR-003).

## Entities

| File | Role |
|---|---|
| `tox.ini` | tox-uv; `py310..py312` (full extras), `core-py3xx` (core deps), `coverage` factor, `check`, `dist`, `update-deps` |
| `requirements/*.txt` | `uv pip compile --universal` of `pyproject.toml` (+ `--all-extras` for `test-full`), `check.in` → `check.txt` |
| `.ruff.toml` | vimseo rules, plus project ignores |
| `.pre-commit-config.yaml` | pre-commit-hooks v6.0.0, ruff-pre-commit v0.17.0 (check + format) |
| `.coveragerc` | covdefaults, `fail_under = 1` |
| `.github/workflows/python-package.yml` | tests (full, core) on Linux and Windows, check job |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE.txt`, `.gitattributes` | as in vimseo |

## Approach

1. Copy the vimseo configuration, adapt the package name and the paths (`src/`, `tests/`,
   `tools/`, `examples/`, `sandbox/` excluded).
2. Universal resolution so the Windows-only `xlwings` keeps its marker on Linux.
3. One configuration commit, then one formatting commit (`ruff format`, `ruff check --fix`,
   line endings normalised by `.gitattributes`), kept apart so the formatting diff can be
   skipped in reviews.

## Structure

No code structure change.

## Operations

1. `tox -e check` = `pre-commit run --all-files`.
2. `tox -e py312` = `pytest` with the full extras; `tox -e py312-coverage` adds coverage.
3. `tox -e update-deps` recompiles the requirement files and updates the hooks.

## Norms

1. Project-specific ruff ignores are commented in `.ruff.toml`: physics symbols in strings
   (RUF001–003), class-level `Port` / `Param` declarations (RUF012), `noqa` comments kept
   (RUF105); exact float comparisons allowed in tests.
2. Conventional commit prefixes: `feat`, `fix`, `chore`, `docs`, `style`, `test`.

## Safeguards

1. The formatting commit changes no behaviour: the full test suite passes before and after.
2. PredimRC workbooks never enter git (`.gitignore`: `profiles/*.xls*`).

## Implementation notes (2026-10-18)

- `gemseo[all]` ≤ 6.3 caps `xlwings` at 0.33.16; the project floor `xlwings >=0.37` made
  the full extras unsatisfiable. Relaxed to `>=0.30` (the wrapper uses only the basic
  xlwings API). Local environments may keep 0.37.
- The `slow` marker filter of vimseo is not used: the Excel tests skip themselves
  (`tests/conftest.py`, `requires_excel`).
- Remote: `https://github.com/SebastienBocquet/predim-vtol.git`, branch `main`.
