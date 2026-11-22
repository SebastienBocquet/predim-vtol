"""Review of 2026-11-18 (INC4-001): GEMSEO mandatory, cost and reliability removed."""

from __future__ import annotations

from pathlib import Path

import pytest

from predim_vtol.aircraft import Project
from predim_vtol.runs import load_runs
from predim_vtol.runs.summary import OUTPUTS_TWO_PHASE

FIXTURES = Path(__file__).parent / "runs" / "fixtures"
REMOVED_OUTPUTS = ("cost_purchase", "cost_per_hour", "motor_out_tw")


def test_cost_and_spin_of_an_old_project_are_dropped():
    data = Project.template("quadplane").to_dict()
    data["cost"] = {"frame": 50.0, "overrides": {"esc": 12.0}, "usd_per_eur": 1.1}
    data["motors"][0]["spin"] = "cw"
    project = Project.model_validate(data)
    assert "cost" not in project.to_dict()
    assert all("spin" not in m for m in project.to_dict()["motors"])
    assert "cost" in data, "the data given is not changed"


def test_no_cost_nor_reliability_output():
    assert not set(REMOVED_OUTPUTS) & set(OUTPUTS_TWO_PHASE)


def test_runs_stored_with_cost_outputs_keep_them():
    pytest.importorskip("plotly")
    runs = load_runs(FIXTURES / "summary_v1")
    columns = set(runs.summaries.columns)
    assert {f"outputs.{name}" for name in REMOVED_OUTPUTS} <= columns
    assert runs.compare_to(runs.ids[0], ["flight_time_v1"]).shape == (len(runs), 1)
