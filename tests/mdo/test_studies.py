"""Exploration, two-phase optimisation and stored studies (INC2-008)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("gemseo")

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.api import evaluate_two_phase  # noqa: E402
from predimrc_wrapper.mdo import Parameter  # noqa: E402
from predimrc_wrapper.mdo import PresizingDiscipline  # noqa: E402
from predimrc_wrapper.mdo.discipline import OUTPUTS_TWO_PHASE  # noqa: E402
from predimrc_wrapper.mdo.explore import explore  # noqa: E402
from predimrc_wrapper.mdo.explore import pareto_mask  # noqa: E402
from predimrc_wrapper.mdo.explore import samples  # noqa: E402
from predimrc_wrapper.mdo.explore import study_from_optimisation  # noqa: E402
from predimrc_wrapper.mdo.optimise import optimise  # noqa: E402
from predimrc_wrapper.mdo.parameters import expand_overrides  # noqa: E402
from predimrc_wrapper.mdo.studies import StudyStore  # noqa: E402

BATTERY = Parameter("battery_mass_g", "battery.mass_g", "float", 400.0, 1200.0)


def test_two_phase_discipline_matches_api():
    base = Project.template("multicopter")
    disc = PresizingDiscipline(base, [BATTERY], mode="two_phase")
    assert set(disc.output_grammar.names) == set(OUTPUTS_TWO_PHASE)
    out = disc.execute({"battery_mass_g": np.array([900.0])})
    ref = evaluate_two_phase(base.with_overrides({"battery.mass_g": 900.0}))
    assert out["flight_time_v2"][0] == pytest.approx(ref.cruise[1].flight_time_s)
    assert out["hover_power"][0] == pytest.approx(ref.hover.battery_power_w)


def test_propeller_choice_sets_id_diameter_and_pitch():
    overrides = expand_overrides({"propulsion_units.lift.propeller": "tmotor-p12x4", "battery.mass_g": 700})
    assert overrides == {"propulsion_units.lift.propeller_id": "tmotor-p12x4", "propulsion_units.lift.prop_diameter_in": 12.0,
                         "propulsion_units.lift.prop_pitch_in": 4.0, "battery.mass_g": 700}


def test_doe_samples():
    v = [BATTERY, Parameter("d", "propulsion_units.lift.prop_diameter_in", "float", 11.0, 13.0)]
    lhs = samples(v, "lhs", 10, seed=1)
    assert lhs.shape == (10, 2) and np.all(lhs[:, 0] >= 400) and np.all(lhs[:, 1] <= 13)
    assert np.array_equal(lhs, samples(v, "lhs", 10, seed=1))
    assert samples(v, "full_factorial", 9).shape == (9, 2)


def test_exploration_saved_and_reloaded(tmp_path):
    study = explore(Project.template("multicopter"), [BATTERY],
                    {"battery.n_series": [4, 6], "propulsion_units.lift.propeller": ["tmotor-p12x4", "tmotor-p13x4.4"]},
                    n_samples=5, name="quad battery")
    assert len(study.points) == 20 and all("flight_time_v2" in p for p in study.points)
    mask = pareto_mask(study.points, [("flight_time_v2", True), ("mass_total", False)])
    front = [p for p, m in zip(study.points, mask) if m]
    for p in front:  # non-dominated
        assert not any(q["flight_time_v2"] >= p["flight_time_v2"] and q["mass_total"] <= p["mass_total"]
                       and (q["flight_time_v2"] > p["flight_time_v2"] or q["mass_total"] < p["mass_total"])
                       for q in study.points if q.get("feasible"))
    store = StudyStore(tmp_path)
    store.save(study)
    store.save(study)  # same second: a unique second folder
    listing = store.list()
    assert len(listing) == 2 and len({s["id"] for s in listing}) == 2 and listing[0]["points"] == 20
    again = StudyStore(tmp_path).load(listing[0]["id"])
    assert [p["flight_time_v2"] for p in again.points] == pytest.approx([p["flight_time_v2"] for p in study.points],
                                                                        nan_ok=True)
    assert again.points[0]["propulsion_units.lift.propeller"] in ("tmotor-p12x4", "tmotor-p13x4.4")
    assert {"tool_version", "test_data_hash", "motor_database_hash", "date"} <= set(again.metadata)
    assert not StudyStore.data_changed(again)
    store.rename(listing[0]["id"], "renamed")
    assert store.load(listing[0]["id"]).name == "renamed"
    store.delete(listing[1]["id"])
    assert len(store.list()) == 1


def test_two_phase_optimisation_and_study(tmp_path):
    project = Project.template("multicopter")
    summary = optimise(project, [BATTERY], objective="flight_time_v2", algo="COBYQA", max_iter=8, max_sd_rel=0.05)
    run = summary.runs[0]
    assert summary.mode == "two_phase" and "margin_motor_power" in run.constraints and "margin_sd" in run.constraints
    start = evaluate_two_phase(project).cruise[1].flight_time_s
    assert run.outputs["flight_time_v2"] >= start
    study = study_from_optimisation(summary, project, [BATTERY], {}, run.constraints, "COBYQA", 8)
    StudyStore(tmp_path).save(study)
    applied = project.with_overrides(expand_overrides(study.summary["best_overrides"]))
    assert evaluate_two_phase(applied).cruise[1].flight_time_s == pytest.approx(run.outputs["flight_time_v2"])
