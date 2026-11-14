"""The simple aerodynamic model (MIC-AERO-SIMPLE): geometry, physics, PredimRC comparison."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from predim_vtol.aero import backend_status
from predim_vtol.aero import open_aero_backend
from predim_vtol.aero import profiles
from predim_vtol.aero.airfoils import airfoil
from predim_vtol.aero.airfoils import airfoils
from predim_vtol.aero.base import FuselageGeometry
from predim_vtol.aero.base import Settings
from predim_vtol.aero.base import StabGeometry
from predim_vtol.aero.base import WingGeometry
from predim_vtol.aero.simple import BEAMS
from predim_vtol.aero.simple import FUSELAGE_SHAPES
from predim_vtol.aero.simple import STAB_PROFILES
from predim_vtol.aero.simple import SimpleAeroBackend
from predim_vtol.aero.simple import SimpleAeroError
from predim_vtol.aero.simple import planform

REFERENCE = json.loads(
    (Path(__file__).parent / "data" / "predimrc_reference.json").read_text(
        encoding="utf-8"
    )
)["cases"]


def _case(inputs: dict) -> dict:
    return {
        "wing": WingGeometry(**inputs["wing"]),
        "stab": StabGeometry(**inputs["stab"]),
        "fus": FuselageGeometry(**inputs["fus"]),
        "settings": Settings(**inputs["settings"]),
    }


def _metrics(r) -> dict[str, float]:
    """The comparison metrics of the reference file (parabolas around the optima)."""
    v, p, f = r.vx, r.power_required_w, r.finesse_vx
    i = int(np.clip(np.argmin(p), 1, len(p) - 2))
    c = np.polyfit(v[i - 1 : i + 2], p[i - 1 : i + 2], 2)
    j = int(np.clip(np.argmax(f), 1, len(f) - 2))
    cf = np.polyfit(v[j - 1 : j + 2], f[j - 1 : j + 2], 2)
    return {
        "S": r.total_surface,
        "mac": r.mean_chord,
        "foyer": r.foyer,
        "Vt": r.tail_volume,
        "vmin": r.v_min,
        "v_pmin": -c[1] / (2 * c[0]),
        "p_min": float(np.polyval(c, -c[1] / (2 * c[0]))),
        "f_max": float(np.polyval(cf, -cf[1] / (2 * cf[0]))),
        "p15": float(np.interp(15.0, v, p)),
    }


@pytest.fixture(scope="module")
def backend():
    return SimpleAeroBackend("SD7003")


@pytest.fixture(scope="module")
def results(backend):
    return {
        name: (backend.evaluate(**_case(c["inputs"])), c["outputs"])
        for name, c in REFERENCE.items()
    }


# --- geometry -------------------------------------------------------------------------


def test_trapezoid_planform():
    p = planform(200.0, [100.0], [800.0], [100.0])
    assert p.area == pytest.approx(240000.0)
    assert p.span == pytest.approx(1600.0)
    assert p.mac == pytest.approx(2 / 3 * 200 * (1 + 0.5 + 0.25) / 1.5)
    y_mac = 800 / 3 * (1 + 2 * 0.5) / 1.5
    assert p.x_le_mac == pytest.approx(100.0 * y_mac / 800.0)


def test_geometry_as_predimrc(results):
    """Area, MAC, spans, aspect ratio and tail volume are those of PredimRC."""
    for name, (r, ref) in results.items():
        assert r.total_surface == pytest.approx(ref["S"], rel=1e-6), name
        assert r.mean_chord == pytest.approx(ref["mac"], rel=1e-6), name
        assert r.span_aero == pytest.approx(ref["span_aero"]), name
        assert r.span_total == pytest.approx(ref["span_total"]), name
        assert r.aspect_ratio == pytest.approx(ref["aspect_ratio"], rel=1e-5), name
        assert r.tail_volume == pytest.approx(ref["Vt"], abs=6e-3), name


# --- comparison with PredimRC (documented gaps of the MIC card) ------------------------

OUTLIERS = {"fus_beam_Jet (entrées air latérales)": 8.0, "sweep_le_300": 6.0}
"""Neutral point gaps (% MAC) of the configurations known to differ (MIC card)."""


def test_neutral_point_close_to_predimrc(results):
    gaps = {name: r.foyer - ref["foyer"] for name, (r, ref) in results.items()}
    for name, gap in gaps.items():
        assert abs(gap) <= OUTLIERS.get(name, 4.0), (name, gap)
    assert np.mean(np.abs(list(gaps.values()))) < 1.5


def test_performance_gaps_to_predimrc(results):
    """The simple model is less draggy than PredimRC at high lift (MIC card): the gaps stay
    in the documented bands."""
    rel = {
        k: np.array([_metrics(r)[k] / ref[k] - 1.0 for r, ref in results.values()])
        for k in ("vmin", "p_min", "f_max", "p15")
    }
    assert np.all((rel["vmin"] > -0.20) & (rel["vmin"] < 0.0))
    assert np.all((rel["p_min"] > -0.40) & (rel["p_min"] < -0.05))
    assert np.all((rel["f_max"] > 0.0) & (rel["f_max"] < 0.35))
    assert np.all(np.abs(rel["p15"]) < 0.40)
    assert abs(np.mean(rel["p_min"]) + 0.25) < 0.05
    assert abs(np.mean(rel["f_max"]) - 0.14) < 0.05


def test_reference_case_regression(results):
    """Pinned outputs of the reference geometry: any model change shows here."""
    m = _metrics(results["reference"][0])
    assert m["foyer"] == pytest.approx(40.80, abs=0.05)
    assert m["vmin"] == pytest.approx(9.66, abs=0.02)
    assert m["p_min"] == pytest.approx(11.72, rel=5e-3)
    assert m["f_max"] == pytest.approx(20.19, rel=5e-3)


# --- physics ---------------------------------------------------------------------------


def test_level_flight_consistency(results):
    r, _ = results["reference"]
    np.testing.assert_allclose(r.drag_n * r.vx, r.power_required_w, rtol=1e-12)
    np.testing.assert_allclose(r.sink_rate * r.mass_kg * 9.81, -r.power_required_w)
    np.testing.assert_allclose(r.power_predimrc_w, r.power_required_w)
    assert np.all(np.diff(r.vx) > 0)
    assert r.v_min < r.v_min_power < r.v_max_finesse
    assert r.cg_mm == pytest.approx(
        r.neutral_point_mm - r.static_margin / 100 * r.mac_mm, rel=1e-9
    )


def test_pitch_equilibrium(backend):
    """The stabiliser lift balances the moments about the CG at every polar point."""
    case = _case(REFERENCE["reference"]["inputs"])
    rho, mu = 1.2, 1.8e-5
    ac = backend._aircraft(case["wing"], case["stab"], case["fus"], rho, mu)  # noqa: SLF001
    x_cg = ac.x_np - 0.05 * ac.wing.mac
    cl_w = np.linspace(0.1, 0.8, 8)
    cl_t, cl_tot, _ = backend._trim(ac, cl_w, x_cg, 0.3)  # noqa: SLF001
    eta = 0.9
    moment = (
        cl_w * ac.wing.area * (x_cg - ac.wing.x_ac)
        + ac.wing_airfoil.cm0 * ac.wing.area * ac.wing.mac
        + ac.m_alpha_fus * (cl_w - 0.3) / ac.a_w
        + eta * ac.stab_airfoil.cm0 * ac.stab.area * ac.stab.mac
        - eta * cl_t * ac.stab.area * (ac.x_ac_t - x_cg)
    )
    np.testing.assert_allclose(moment, 0.0, atol=1e-6 * ac.wing.area * ac.wing.mac)
    np.testing.assert_allclose(cl_tot, cl_w + eta * ac.stab.area / ac.wing.area * cl_t)


def _vary(backend, **changes):
    case = _case(copy.deepcopy(REFERENCE["reference"]["inputs"]))
    for path, value in changes.items():
        part, attr = path.split("__")
        setattr(case[part], attr, value)
    return backend.evaluate(**case)


def test_sensitivities(backend, results):
    ref, _ = results["reference"]
    heavy = _vary(backend, settings__mass=3000.0)
    assert heavy.v_min == pytest.approx(ref.v_min * math.sqrt(3000 / 1920), rel=0.03)
    assert _vary(backend, stab__lever=500.0).foyer > ref.foyer
    assert _vary(backend, fus__nose_lever=400.0).foyer < ref.foyer
    assert _vary(backend, stab__opening="100").foyer < ref.foyer
    box = _vary(backend, fus__shape="Caisse")
    assert np.max(box.finesse_vx) < np.max(ref.finesse_vx)
    high = _vary(backend, settings__altitude_m=2000.0, settings__temperature_c=2.0)
    assert high.rho < ref.rho
    assert high.v_min > ref.v_min


def test_imposed_speed_blocks(backend):
    r = _vary(backend, settings__vx1_kmh=45.0, settings__vx2_kmh=60.0)
    assert set(r.imposed) == {1, 2}
    block = r.imposed[1]
    assert block.vx_m_s == pytest.approx(12.5)
    # The block at the polar point nearest 45 km/h gives the polar drag there.
    cz = float(np.interp(12.5, r.vx, r.cz))
    drag, power = block.at_cz(cz, float(r.cz.max()))
    assert drag == pytest.approx(float(np.interp(12.5, r.vx, r.drag_n)), rel=0.02)
    assert power == pytest.approx(drag * 12.5)


@pytest.mark.parametrize("label", list(STAB_PROFILES))
def test_stab_labels(backend, label):
    assert np.isfinite(_vary(backend, stab__profile=label).v_min_power)


@pytest.mark.parametrize(
    ("field", "labels"), [("fus__shape", FUSELAGE_SHAPES), ("fus__beam", BEAMS)]
)
def test_fuselage_labels(backend, field, labels):
    for label in labels:
        assert np.isfinite(_vary(backend, **{field: label}).v_min_power)


def test_unknown_label(backend):
    with pytest.raises(SimpleAeroError, match=r"fuselage.shape"):
        _vary(backend, fus__shape="Sphère")
    with pytest.raises(SimpleAeroError, match="opening"):
        _vary(backend, stab__opening="V")


# --- airfoils --------------------------------------------------------------------------


def test_shipped_airfoils():
    assert {"SD7003", "ClarkY", "NACA2412"} <= set(airfoils("wing"))
    sd = airfoil("sd7003")
    assert sd.drag(np.array([0.5]), 2e5)[0] == pytest.approx(0.0095, abs=0.0015)
    # Thinner boundary layer at higher Reynolds numbers, drag rise towards the stall.
    assert sd.drag(np.array([0.5]), 4e5)[0] < sd.drag(np.array([0.5]), 1e5)[0]
    assert sd.drag(np.array([1.2]), 2e5)[0] > 2 * sd.drag(np.array([0.5]), 2e5)[0]
    assert 1.0 < sd.cl_max(2e5) < 1.4


def test_user_airfoil(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDIM_VTOL_USER_DATA", str(tmp_path))
    (tmp_path / "airfoils.yaml").write_text(
        "wing:\n  MyFoil:\n    thickness: 0.1\n    polars:\n"
        "    - {re: 200000, cl_max: 1.1, alpha0_deg: -2, cl_alpha: 6.2, cm0: -0.05,\n"
        "       cl: [0.0, 0.5, 1.0], cd: [0.010, 0.009, 0.015]}\n",
        encoding="utf-8",
    )
    assert "MyFoil" in profiles("simple", tmp_path)
    assert airfoil("myfoil").drag(np.array([0.5]), 2e5)[0] == pytest.approx(0.009)
    with pytest.raises(KeyError, match="Available"):
        airfoil("Nope")


# --- backend selection -----------------------------------------------------------------


def _aero(backend: str = "simple", profile: str = "SD7003"):
    from predim_vtol.aircraft import Project  # noqa: PLC0415

    aero = Project.template("quadplane").aero
    return aero.model_copy(update={"backend": backend, "profile": profile})


def test_simple_is_the_default():
    from predim_vtol.aircraft import Project  # noqa: PLC0415

    assert Project.template("quadplane").aero.backend == "simple"
    assert backend_status(_aero(), "nowhere") == ("simple", None)
    assert open_aero_backend(_aero(), "nowhere").name == "simple"


def test_predimrc_unavailable_falls_back(tmp_path):
    backend, message = backend_status(_aero("predimrc"), tmp_path)
    assert backend == "simple"
    assert "PredimRC unavailable" in message
    assert open_aero_backend(_aero("predimrc"), tmp_path).name == "simple"


def test_unknown_airfoil_of_the_simple_model():
    backend, message = backend_status(_aero(profile="Mystery"), "nowhere")
    assert backend == "simple"
    assert "no airfoil 'Mystery'" in message
    with pytest.raises(KeyError):
        open_aero_backend(_aero(profile="Mystery"), "nowhere")


def test_quadplane_without_excel():
    """End to end: the quadplane template is evaluated with the simple model."""
    from predim_vtol.aircraft import Project  # noqa: PLC0415
    from predim_vtol.api import evaluate_two_phase  # noqa: PLC0415

    result = evaluate_two_phase(Project.template("quadplane"))
    assert result.metadata["aero_backend"] == "simple"
    assert result.iso_check.passed
    assert all(np.isfinite(p.aero_power_w) for p in result.cruise)
    assert all(p.source.startswith("imposed speed") for p in result.cruise)
