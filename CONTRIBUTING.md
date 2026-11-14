# Contributing

- Specification first: the SPDD process (`spdd/`: `analysis/`, `prompt/`, then one folder
  per increment `mvp/`, `inc2/`, `inc3/`): requirements, then a REASONS canvas per work
  package, then the code; the canvas records the implementation notes. The stable
  requirements of all increments are in `spdd/requirements/`.
- Environment: `uv venv && uv pip install -e . --group dev` (extras `[mdo,ui]` for GEMSEO and the GUI).
- Tests: `tox -e py312`; the Excel tests run only when Excel and a
  PredimRC workbook are available (folder in the settings or `$PREDIMRC_PROFILES`).
- Style: `tox -e check` (ruff check and format through pre-commit).
- Every model has a MIC card in `src/predim_vtol/mic/` (shipped with the package and shown
  in the application); regenerate the interfaces with
  `python -m predim_vtol.core.sync_mic`.
- Commits: one logical change per commit; branches `fix/...`, `feat/...`, `chore/...`.
