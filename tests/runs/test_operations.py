"""Verbs of the collection of runs on synthetic summaries (REQ-UI-013)."""

from __future__ import annotations

import math
import operator

import pytest
from pandas import DataFrame

from predimrc_wrapper.runs import RunResults
from predimrc_wrapper.runs.query import apply_query


def _runs(rows) -> RunResults:
    return RunResults(DataFrame(rows), operator.itemgetter("run_id"))


def _row(
    i, cells, mass, arch="multicopter", project="quad", date="2026-10-20T10:00:00"
):
    return {
        "run_id": f"r{i}",
        "run_name": f"run {i}",
        "date": date,
        "project_name": project,
        "architecture": arch,
        "feasible": mass < 900,
        "tool_version": "1.0",
        "data_hashes.prices": "a",
        "inputs.battery.n_series": cells,
        "inputs.battery.mass_g": mass,
        "inputs.motors.0.unit": "lift",
        "outputs.flight_time_v1": cells * mass / 10.0,
        "outputs.mass_total": 1.0 + mass / 1000,
    }


@pytest.fixture
def runs():
    return _runs([
        _row(1, 4, 500.0),
        _row(2, 4, 700.0),
        _row(3, 6, 500.0),
        _row(4, 6, 700.0),
        _row(5, 6, 950.0, date="2026-10-25T09:00:00"),
        _row(
            6, 3, 500.0, arch="quadplane", project="glider", date="2026-10-01T09:00:00"
        ),
    ])


def test_varying_inputs_and_ignoring(runs):
    varying = runs.varying_inputs()
    assert list(varying.index) == ["battery.n_series", "battery.mass_g"]
    assert varying.loc["battery.mass_g", "values"] == [500.0, 700.0, 950.0]
    assert list(runs.ignoring("battery.n_series").varying_inputs().index) == [
        "battery.mass_g"
    ]


def test_input_missing_in_some_runs_varies():
    rows = [_row(1, 4, 500.0), _row(2, 4, 500.0)]
    rows[1]["inputs.motors.4.unit"] = "cruise"
    assert "motors.4.unit" in _runs(rows).varying_inputs().index


def test_families(runs):
    families = runs.families(along="battery.mass_g")
    assert len(families) == 2
    four = families.get(**{"battery.n_series": 4})
    assert four.ids == ["r1", "r2"]
    six = families[("battery.n_series", 6),]
    assert list(six.summaries["inputs.battery.mass_g"]) == [500.0, 700.0, 950.0]
    assert families.ungrouped.ids == ["r6"]
    table = families.to_dataframe(["flight_time_v1"])
    assert list(table.columns) == ["battery.mass_g", "flight_time_v1", "family"]
    assert set(table["family"]) == {"battery.n_series=4", "battery.n_series=6"}


def test_filters(runs):
    assert runs.filter(architecture="quadplane").ids == ["r6"]
    assert len(runs.filter(project_name=["quad", "glider"])) == 6
    assert runs.filter(since="2026-10-21").ids == ["r5"]
    assert runs.filter(until="2026-10-01").ids == ["r6"]  # the whole day
    assert runs.filter(name_contains="GLI").ids == ["r6"]
    assert runs.filter(failed=True).ids == ["r5"]
    assert runs.filter(
        "`inputs.battery.n_series` == 6 and `outputs.flight_time_v1` > 300"
    ).ids == ["r4", "r5"]
    with pytest.raises(KeyError):
        runs.filter(unknown=1)
    with pytest.raises(ValueError, match="Python variables"):
        apply_query(runs.summaries, "`inputs.battery.mass_g` > @x")


def test_duplicates_table_and_labels(runs):
    rows = [_row(1, 4, 500.0), _row(2, 4, 500.0), _row(3, 6, 500.0)]
    duplicates = _runs(rows).duplicates()
    assert list(duplicates["run_id"]) == ["r1", "r2"]
    table = runs.to_dataframe(["run_name", "battery.n_series", "mass_total"])
    assert list(table.columns) == ["run_name", "battery.n_series", "mass_total"]
    assert table.index.name == "run_id"
    assert runs[:2].labels() == ["battery.mass_g = 500", "battery.mass_g = 700"]


def test_compare_to_and_provenance(runs):
    errors = runs.compare_to("r1", ["flight_time_v1"])
    assert errors.loc["r1", "flight_time_v1"] == 0
    assert errors.loc["r2", "flight_time_v1"] == pytest.approx(0.4)
    assert math.isnan(
        runs.compare_to({"flight_time_v1": 0.0}).loc["r1", "flight_time_v1"]
    )
    assert runs.provenance().empty
    rows = [_row(1, 4, 500.0), _row(2, 4, 700.0)]
    rows[1]["data_hashes.prices"] = "b"
    assert list(_runs(rows).provenance().index) == ["prices"]
