"""MVP-006: GEMSEO discipline, design parameters and examples."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

pytest.importorskip("gemseo")

from predimrc_wrapper.aircraft import Project  # noqa: E402
from predimrc_wrapper.api import evaluate_two_phase  # noqa: E402
from predimrc_wrapper.mdo import OUTPUTS  # noqa: E402
from predimrc_wrapper.mdo import Parameter  # noqa: E402
from predimrc_wrapper.mdo import PresizingDiscipline  # noqa: E402
from predimrc_wrapper.mdo import build_design_space  # noqa: E402
from predimrc_wrapper.mdo import categorical  # noqa: E402
from predimrc_wrapper.mdo import from_database  # noqa: E402
from tests.conftest import ROOT  # noqa: E402
from tests.conftest import requires_excel  # noqa: E402
from tests.helpers import ParabolicAero  # noqa: E402

EXAMPLES = ROOT / "examples" / "mvp"


@pytest.fixture
def parameters():
    return [
        Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 1500.0),
        Parameter("n_series", "battery.n_series", "integer", 4, 6),
        from_database("lift_motor", "propulsion_units.lift.motor_id", role="lift"),
    ]


def test_categorical_round_trip():
    p = categorical("motor", "propulsion_units.lift.motor_id", ["a", "b", "c"])
    assert p.bounds() == (0, 2)
    for label in "abc":
        assert p.to_project_value(np.array([p.to_design_value(label)])) == label
    assert p.to_project_value(np.array([1.4])) == "b"
    with pytest.raises(ValueError, match="outside"):
        p.to_project_value(np.array([3.0]))
    with pytest.raises(ValueError, match="needs labels"):
        Parameter("x", "y", "categorical")


def test_design_space_types_and_bounds(parameters):
    space = build_design_space(parameters, {"battery_mass_g": 700.0})
    assert list(space.variable_names) == ["battery_mass_g", "n_series", "lift_motor"]
    assert space.get_type("battery_mass_g") == "float"
    assert space.get_type("n_series") == "integer"
    assert space.get_type("lift_motor") == "integer"
    assert (
        space.get_upper_bound("lift_motor")[0] == len(parameters[2].mapping.labels) - 1
    )
    assert space.get_current_value(["battery_mass_g"])[0] == 700.0


def test_discipline_matches_evaluate(parameters):
    base = Project.template("multicopter")
    disc = PresizingDiscipline(base, parameters)
    assert set(disc.output_grammar.names) == set(OUTPUTS)
    x = {
        "battery_mass_g": np.array([900.0]),
        "n_series": np.array([4.0]),
        "lift_motor": np.array([
            float(parameters[2].mapping.index("tmotor-mn2806-400kv"))
        ]),
    }
    out = disc.execute(x)
    ref = evaluate_two_phase(
        base.with_overrides({
            "battery.mass_g": 900.0,
            "battery.n_series": 4,
            "propulsion_units.lift.motor_id": "tmotor-mn2806-400kv",
        })
    )
    assert out["flight_time_v1"][0] == pytest.approx(ref.cruise[0].flight_time_s)
    assert out["range_v1"][0] == pytest.approx(ref.cruise[0].range_m)
    assert out["mass_total"][0] == pytest.approx(ref.metadata["mass_total_kg"])
    assert out["margin_battery_c"][0] == pytest.approx(ref.margins["battery_c"])
    assert out["feasible"][0] == float(ref.feasible)


def test_default_inputs_are_base_project(parameters):
    base = Project.template("multicopter")
    disc = PresizingDiscipline(base, parameters)
    values = disc.initial_values()
    assert values["battery_mass_g"] == base.battery.mass_g
    assert disc.project_for(disc.default_input_data) == base


def test_cache_hit(parameters, monkeypatch):
    from predimrc_wrapper import api  # noqa: PLC0415

    calls = []
    original = api.evaluate_two_phase
    monkeypatch.setattr(
        api, "evaluate_two_phase", lambda *a, **k: calls.append(1) or original(*a, **k)
    )
    disc = PresizingDiscipline(Project.template("multicopter"), parameters)
    disc.execute({"battery_mass_g": np.array([800.0])})
    disc.execute({"battery_mass_g": np.array([800.0])})
    assert len(calls) == 1
    import multiprocessing  # noqa: PLC0415

    assert not multiprocessing.active_children()


def test_failure_gives_nan(parameters, monkeypatch):
    from predimrc_wrapper import api  # noqa: PLC0415

    def boom(*args, **kwargs):
        msg = "injected"
        raise RuntimeError(msg)

    monkeypatch.setattr(api, "evaluate_two_phase", boom)
    out = PresizingDiscipline(Project.template("multicopter"), parameters).execute()
    assert np.isnan(out["flight_time_v1"][0])
    assert out["feasible"][0] == 0.0


def test_quadplane_with_fake_backend():
    backend = ParabolicAero()
    params = [Parameter("span_t2_mm", "aero.wing.length_mm.1", "float", 250.0, 350.0)]
    disc = PresizingDiscipline(Project.template("quadplane"), params, backend=backend)
    out = disc.execute({"span_t2_mm": np.array([300.0])})
    assert out["flight_time_v1"][0] > 0
    assert backend.calls >= 1
    disc.close()  # the injected backend is not owned: nothing to close


def test_optim_multicopter_example(tmp_path):
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / "optim_multicopter.py"), "5", "2"],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(
        (EXAMPLES / "outputs" / "optim_multicopter.json").read_text(encoding="utf-8")
    )
    assert summary["best"]["outputs"]["flight_time_v1"] > 0
    assert "propulsion_units.lift.motor_id" in summary["best"]["choice"]


@pytest.mark.slow
@requires_excel
def test_optim_quadplane_example():
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / "optim_quadplane.py"), "5"],
        capture_output=True,
        text=True,
        timeout=1800,
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(
        (EXAMPLES / "outputs" / "optim_quadplane.json").read_text(encoding="utf-8")
    )
    assert summary["best"]["outputs"]["flight_time_v1"] > 0


def test_optimise_loop_and_best_design():
    from predimrc_wrapper.mdo.optimise import available_algorithms  # noqa: PLC0415
    from predimrc_wrapper.mdo.optimise import optimise  # noqa: PLC0415

    assert "SLSQP" in available_algorithms()
    project = Project.template("multicopter")
    continuous = [Parameter("battery_mass_g", "battery.mass_g", "float", 400.0, 1200.0)]
    summary = optimise(
        project, continuous, {"battery.n_series": [4, 6]}, algo="COBYQA", max_iter=8
    )
    assert len(summary.runs) == 2
    assert all(r.history and not r.error for r in summary.runs)
    best = summary.best
    assert best.outputs["flight_time_v1"] == max(
        r.outputs["flight_time_v1"] for r in summary.runs if r.feasible
    )
    overrides = summary.best_overrides(continuous)
    assert set(overrides) == {"battery.n_series", "battery.mass_g"}
    applied = evaluate_two_phase(project.with_overrides(overrides))
    assert applied.cruise[0].flight_time_s == pytest.approx(
        best.outputs["flight_time_v1"]
    )


def test_optimise_drops_not_applicable_constraints():
    """No maximum take-off mass: margin_mass is NaN and must not stop the optimiser."""
    from predimrc_wrapper.mdo.optimise import optimise  # noqa: PLC0415

    project = Project.template("tricopter")
    continuous = [Parameter("battery_mass_g", "battery.mass_g", "float", 250.0, 700.0)]
    run = optimise(project, continuous, algo="COBYQA", max_iter=10).runs[0]
    assert "margin_mass" not in run.constraints
    assert run.feasible
    assert run.outputs["margin_thrust_to_weight"] >= -1e-3


def test_calibrated_base_is_kept_for_variants():
    disc = PresizingDiscipline(
        Project.template("tricopter"),
        [Parameter("battery_mass_g", "battery.mass_g", "float", 300.0, 900.0)],
    )
    assert disc.calibration_report.points[0].point == "hover"
    assert disc.base_project.calibration is None
    k_h = disc.base_project.mission.hover_power_factor
    assert k_h != 1.0
    assert (
        disc.project_for({
            "battery_mass_g": np.array([700.0])
        }).mission.hover_power_factor
        == k_h
    )
