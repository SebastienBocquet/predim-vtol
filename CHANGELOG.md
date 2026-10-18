# Changelog

All notable changes are listed here, newest first. Format: [Keep a Changelog](https://keepachangelog.com),
versions from git tags (setuptools-scm).

## Unreleased

### Added
- Project tooling as in vimseo: tox (tox-uv), ruff, pre-commit, coverage, GitHub Actions, compiled
  requirements.

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
