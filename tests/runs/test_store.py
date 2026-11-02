"""Stored runs: save, reload, compare, provenance, backward compatibility (REQ-UI-013)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.provenance import data_changes
from predimrc_wrapper.provenance import reproducibility_metadata
from predimrc_wrapper.runs import RunStore
from predimrc_wrapper.runs import load_runs
from predimrc_wrapper.runs.summary import OUTPUTS_TWO_PHASE
from predimrc_wrapper.runs.summary import flatten_inputs
from tests.aircraft.test_configurations import V1_MULTICOPTER

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def stored(tmp_path_factory):
    """Four tricopter runs: 4S and 6S, 400 g and 600 g batteries."""
    store = RunStore(tmp_path_factory.mktemp("runs"))
    base = Project.template("tricopter")
    for cells in (4, 6):
        for mass in (400.0, 600.0):
            project = base.with_overrides({
                "battery.n_series": cells,
                "battery.mass_g": mass,
            })
            store.save(project, evaluate_two_phase(project), f"tri {cells}S {mass:g} g")
    return store


def test_flatten_inputs_round_trip():
    project = Project.template("quadplane")
    inputs = flatten_inputs(project.to_dict())
    assert "name" not in inputs
    assert "architecture" not in inputs
    assert inputs["motors.0.unit"] == project.motors[0].unit
    assert inputs["aero.wing.length_mm.1"] == project.aero.wing.length_mm[1]
    same = project.with_overrides(inputs)
    assert same.to_dict() == project.to_dict()


def test_save_list_load_rename_delete(stored, tmp_path):
    listing = stored.list()
    assert len(listing) == 4
    assert listing[0]["name"] == "tri 6S 600 g"  # newest first
    assert {r["architecture"] for r in listing} == {"multicopter"}
    run = stored.load(listing[0]["id"])
    assert set(run.summary["outputs"]) == set(OUTPUTS_TWO_PHASE)
    assert run.project().battery.n_series == 6
    assert run.result["cruise"][0]["v_m_s"] > 0
    assert {"tool_version", "data_hashes", "format_version"} <= set(run.metadata)
    assert run.data_changes() == []
    # A copy: rename and delete do not touch the module fixture.
    store = RunStore(tmp_path / "runs")
    shutil.copytree(stored.root, store.root)
    store.rename(listing[0]["id"], "renamed")
    assert store.load(listing[0]["id"]).name == "renamed"
    store.delete(listing[1]["id"])
    assert len(store.list()) == 3
    assert not list(store.root.glob(".*.tmp"))


def test_collection_families_and_figures(stored):
    pytest.importorskip("plotly")
    runs = stored.collection()
    assert list(runs.varying_inputs().index) == ["battery.n_series", "battery.mass_g"]
    families = runs.families(along="battery.mass_g")
    assert len(families) == 2
    four = families.get(**{"battery.n_series": 4})
    times = list(four.summaries["outputs.flight_time_v1"])
    assert times[1] > times[0]  # a heavier battery flies longer here
    figures = families.visualize()
    assert "outputs_vs_battery.mass_g[battery.n_series=4]" in figures
    assert all(f.data for f in figures.values())
    assert len(runs.filter(name_contains="6s")) == 2
    assert len(load_runs(stored.root, architecture="multicopter")) == 4


def test_rerun(stored, tmp_path):
    store = RunStore(tmp_path / "runs")
    shutil.copytree(stored.root, store.root)
    first = store.list()[0]
    again = store.load(store.rerun(first["id"]).name)
    assert again.name == f"{first['name']} (re-run)"
    old = store.load(first["id"])
    assert again.summary["outputs"]["flight_time_v1"] == pytest.approx(
        old.summary["outputs"]["flight_time_v1"]
    )


def test_data_changes(monkeypatch, tmp_path):
    meta = reproducibility_metadata(Project.template("multicopter"))
    assert data_changes(meta) == []
    user = tmp_path / "user_data"
    user.mkdir()
    monkeypatch.setenv("PREDIMRC_USER_DATA", str(user))
    meta = reproducibility_metadata(None)
    (user / "motors.yaml").write_text("motors: []\n", encoding="utf-8")
    assert data_changes(meta) == ["user_data"]
    # Metadata of an older version (no data_hashes): no false alarm.
    old = {k: v for k, v in meta.items() if k != "data_hashes"}
    assert data_changes(old) == []


def test_old_project_format_is_migrated(stored, tmp_path):
    store = RunStore(tmp_path / "runs")
    shutil.copytree(stored.root, store.root)
    run_id = store.list()[0]["id"]
    (store.root / run_id / "project.yaml").write_text(
        yaml.safe_dump(V1_MULTICOPTER), encoding="utf-8"
    )
    row = store.collection().summaries.set_index("run_id").loc[run_id]
    assert row["project_loadable"]
    assert row["inputs.motors.5.unit"] == "lift"
    assert "inputs.lift_rotors.n_rotors" not in row.index


def test_project_no_longer_loading_falls_back_to_stored_inputs(stored, tmp_path):
    store = RunStore(tmp_path / "runs")
    shutil.copytree(stored.root, store.root)
    run_id = store.list()[0]["id"]
    file = store.root / run_id / "project.yaml"
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    data["removed_field"] = 1
    file.write_text(yaml.safe_dump(data), encoding="utf-8")
    row = store.collection().summaries.set_index("run_id").loc[run_id]
    assert not row["project_loadable"]
    assert row["inputs.battery.n_series"] == 6


@pytest.mark.parametrize("folder", sorted(p.name for p in FIXTURES.iterdir()))
def test_stored_formats_still_load(folder):
    """Runs stored by earlier versions load, filter and plot (add one per format change)."""
    pytest.importorskip("plotly")
    runs = load_runs(FIXTURES / folder)
    assert len(runs) >= 1
    assert runs.summaries["project_loadable"].all()
    assert len(runs.filter(architecture=list(runs.summaries["architecture"]))) == len(
        runs
    )
    assert runs.visualize()
