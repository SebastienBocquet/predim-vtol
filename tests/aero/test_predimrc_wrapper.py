"""Tests of the PredimRC wrapper (MVP-001)."""

from __future__ import annotations

import copy
import hashlib

import numpy as np
import pytest

from predimrc_wrapper.predimrc_wrapper import PredimRCError
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import WingGeometry
from predimrc_wrapper.predimrc_wrapper import derive_drag
from tests.conftest import PROFILES
from tests.conftest import requires_excel


def test_derive_drag():
    """D·V equals m·g·|Vz| and speeds are converted from km/h."""
    vx, drag, power = derive_drag(np.array([36.0, 72.0]), np.array([-0.5, -1.0]), 2.0)
    np.testing.assert_allclose(vx, [10.0, 20.0])
    np.testing.assert_allclose(power, [2.0 * 9.81 * 0.5, 2.0 * 9.81 * 1.0])
    np.testing.assert_allclose(drag * vx, power, rtol=1e-12)


def test_too_many_panels():
    with pytest.raises(ValueError, match="at most 5 panels"):
        WingGeometry(200.0, [1] * 6, [1] * 6, [1] * 6, [1] * 6, [1] * 6)


@pytest.mark.slow
@requires_excel
def test_reference_case(predimrc, reference_case):
    """tricoptere_short_2 reproduced within 0.5 %."""
    result = predimrc.run(**reference_case)
    assert result.total_surface == pytest.approx(30.795, rel=5e-3)
    assert result.span_total == pytest.approx(1825.0, rel=5e-3)
    assert result.aspect_ratio == pytest.approx(9.831, rel=5e-3)
    assert result.cg == pytest.approx(30.1, rel=5e-3)
    assert result.static_margin == pytest.approx(5.0)
    assert result.foyer - result.cg == pytest.approx(result.static_margin)
    assert result.tail_volume == pytest.approx(0.4203, rel=5e-3)
    assert result.stab_incidence_deg == pytest.approx(0.511, abs=0.01)
    assert result.longitudinal_dihedral_deg == pytest.approx(1.245, abs=0.01)
    assert result.vx.size > 5
    np.testing.assert_allclose(result.drag_n * result.vx, result.power_required_w)
    assert result.v_min < result.v_min_power < result.v_max_finesse


@pytest.mark.slow
@requires_excel
def test_settings_written(predimrc, reference_case):
    case = copy.deepcopy(reference_case)
    case["settings"] = Settings(mass=2400.0, static_margin=10.0, cz_reg=0.40)
    predimrc.run(**case)
    geom = predimrc._geom
    assert geom["C33"].value == 2400.0
    assert geom["D29"].value == pytest.approx(0.10)
    assert geom["F30"].value == pytest.approx(0.40)


@pytest.mark.slow
@requires_excel
def test_mass_changes_polar(predimrc, reference_case):
    light = predimrc.run(**reference_case)
    case = copy.deepcopy(reference_case)
    case["settings"] = Settings(mass=2880.0, static_margin=5.0, cz_reg=0.30)
    heavy = predimrc.run(**case)
    assert heavy.v_min_power > light.v_min_power
    assert heavy.power_required_w.min() > light.power_required_w.min()


@pytest.mark.slow
@requires_excel
def test_invalid_label(predimrc, reference_case):
    case = copy.deepcopy(reference_case)
    case["fus"].shape = "Ronde"
    with pytest.raises(PredimRCError, match="Allowed"):
        predimrc.run(**case)


@pytest.mark.slow
@requires_excel
def test_cz_reg_resolution(predimrc, reference_case):
    case = copy.deepcopy(reference_case)
    case["settings"] = Settings(mass=1920.0, static_margin=5.0, cz_reg=0.32)
    with pytest.raises(ValueError, match=r"multiple of 0\.05"):
        predimrc.run(**case)


@pytest.mark.slow
@requires_excel
def test_template_unchanged(reference_case):
    from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper  # noqa: PLC0415

    path = PROFILES / "PredimRC_SD7003.xls"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with PredimRCWrapper(template_dir=PROFILES) as wrapper:
        wrapper.run(**reference_case)
    case = copy.deepcopy(reference_case)
    case["stab"].profile = "unknown"
    with (
        pytest.raises(PredimRCError),
        PredimRCWrapper(template_dir=PROFILES) as wrapper,
    ):
        wrapper.run(**case)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
