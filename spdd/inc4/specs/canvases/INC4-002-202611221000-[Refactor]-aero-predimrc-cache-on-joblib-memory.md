---
id: INC4-002
title: PredimRC cache on joblib.Memory
status: Implemented
branch: refactor/joblib-aero-cache
requirements: [REQ-MDO-005, REQ-AERO-007]
depends_on: [INC4-001]
owner: Sebastien Bocquet
---

# PredimRC cache on `joblib.Memory`

## Requirements

- A geometry already evaluated is read from the cache without starting Excel, across
  Runs, studies and sessions (REQ-MDO-005).
- A modified workbook or a new reading of the outputs never reuses stale results.
- A script and the GUI may use the cache at the same time.
- No adapter turning the PredimRC dataclasses into arrays (review of 2026-11-18, option B).

## Entities

| Element | Role |
|---|---|
| `evaluation_key(*inputs)` | fields of `WingGeometry`, `StabGeometry`, `FuselageGeometry`, `Settings`; numbers as floats, lists as tuples |
| `_evaluate(backend, key, wing, stab, fus, settings)` | the function cached by joblib; only `key` is hashed |
| `CachedBackend` | same interface as a backend (proxy): lock, `hits` / `misses`, `Memory(cache_path).cache(_evaluate)` |
| `workbook_key` | profile, SHA-256 of the workbook, `CACHE_VERSION` (now 3); part of every key |
| `default_cache_path` | setting `predimrc_cache`, default `~/.predim_vtol/predimrc_cache`; a `.h5` setting gives the folder without the suffix |

Removed: `encode_inputs`, `decode_inputs`, `encode_outputs`, `decode_outputs`,
`output_names`, `UNSET`, the GEMSEO `PredimRCDiscipline` and its `HDF5Cache`.

## Approach

1. joblib hashes the arguments by pickle: the key is built from plain floats, strings,
   `None` and tuples, so `2500` and `2500.0` give one entry, as the float arrays did.
2. Hit or miss: `check_call_in_cache` before the call, both under the `threading.Lock`
   (several GUI threads share the backend).
3. The workbook key enters the hashed key instead of naming a sub-folder, and
   `_evaluate.__module__` is `"predimrc"`: entries are
   `<cache>/predimrc/_evaluate/<hash>/output.pkl`.
4. The former HDF5 file is not migrated (about 30 s of Excel for 102 entries).

## Structure

`aero/cache.py` only; the setting, its GUI help and the docstrings follow the folder.

## Operations

1. `open_backend(profile, folder, cache_path)` → `CachedBackend(ExcelThreadBackend, …)`.
2. `evaluate`: key → hit (read `output.pkl`) or miss (Excel, then joblib writes the entry
   under a temporary name and renames it).

## Norms

1. Breaking change in the CHANGELOG (cache location and removed functions).
2. `CLAUDE.md`: the `if __name__ == "__main__":` rule no longer applies to PredimRC
   scripts (no `multiprocessing.Manager` any more).

## Safeguards

1. `test_evaluation_key`: accents, `None`, padded panels, int and float give one key.
2. `test_cache_returns_stored_results_without_the_backend`: hit from another thread, read
   back by a new session (NaN, imposed speeds), another workbook key misses, path length.
3. `test_former_cache_file_setting_gives_a_folder`; `test_gui_backend_from_several_threads`
   with Excel.

## Implementation notes (2026-11-22)

- Windows paths are limited to 260 characters and joblib nests
  `<folder>/<module path>/<function>/<hash>/output.pkl.<temporary name>`; beyond, it only
  emits a `CacheWarning` and caches nothing. With the module path of the package and a
  sub-folder per workbook, the pytest temporary folder overflowed. Short module name and no
  sub-folder: 65 characters inside the cache folder for the final files.
- joblib empties the cache when the body of `_evaluate` changes, not when lines above it
  move (checked with joblib 1.6).
