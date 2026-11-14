"""Stored runs and their comparison (REQ-UI-013).

A run is a two-phase evaluation of a project saved on demand; the collection of the runs
filters them (metadata, dates, queries), lists the varying inputs, groups the runs into
families differing by one input, tabulates and superposes them::

    from predim_vtol.runs import load_runs

    runs = load_runs(architecture="multicopter", since="2026-10-01")
    runs.varying_inputs()
    families = runs.families(along="battery.n_parallel")
    families.to_dataframe(["flight_time_v1", "mass_total"])
    figures = families.visualize()
"""

from predim_vtol.runs.collection import Families
from predim_vtol.runs.collection import FamilyKey
from predim_vtol.runs.collection import RunResults
from predim_vtol.runs.store import RunStore
from predim_vtol.runs.store import StoredRun
from predim_vtol.runs.store import load_runs

__all__ = [
    "Families",
    "FamilyKey",
    "RunResults",
    "RunStore",
    "StoredRun",
    "load_runs",
]
