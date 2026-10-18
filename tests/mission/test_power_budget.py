"""Power budget: the sinks add up to the chemical power (REQ-MIS-009, MIC-MIS-BUDGET)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.mission.power_budget import budget_rows
from predimrc_wrapper.mission.power_budget import power_budget
from tests.helpers import ParabolicAero


@pytest.mark.parametrize("name", ["tricopter", "multicopter", "quadplane", "tiltrotor"])
def test_sinks_add_up_to_the_chemical_power(name):
    project = Project.template(name)
    backend = ParabolicAero() if project.architecture == "quadplane" else None
    result = evaluate_two_phase(project, backend=backend)
    budgets = power_budget(AircraftModel(project, aero_backend=backend), result)
    assert [b.phase for b in budgets] == ["hover", "V1", "V2"]
    for b in budgets:
        assert abs(b.closure_w) <= 1e-9 * b.chemical_w, (b.phase, b.closure_w)
        assert all(v >= -1e-9 for v in b.sinks.values()), b.sinks
        assert b.sinks["avionics"] == pytest.approx(project.mission.avionics_power_w)


def test_hover_useful_power_is_the_ideal_induced_power():
    project = Project.template("multicopter")
    result = evaluate_two_phase(project)
    hover = power_budget(AircraftModel(project), result)[0]
    aircraft = AircraftModel(project)
    import numpy as np  # noqa: PLC0415

    from predimrc_wrapper.core.units import INCH  # noqa: PLC0415

    area = np.pi * (project.propulsion_units["lift"].prop_diameter_in * INCH) ** 2 / 4
    expected = sum(m.thrust_n**1.5 for m in result.hover.motors) / np.sqrt(
        2 * aircraft.rho * area
    )
    assert hover.sinks["useful aerodynamic"] == pytest.approx(expected)


def test_budget_rows_total():
    project = Project.template("tricopter")
    result = evaluate_two_phase(project)
    rows = budget_rows(power_budget(AircraftModel(project), result))
    assert rows[-1]["power sink"] == "battery chemical power (total)"
    for phase in ("hover", "V1", "V2"):
        total = sum(r[f"{phase} (W)"] or 0.0 for r in rows[:-1])
        assert total == pytest.approx(rows[-1][f"{phase} (W)"], abs=0.5)
