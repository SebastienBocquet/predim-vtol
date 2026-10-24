"""Feedback of 2026-10-22: drag sources by forms, costs in euros, PredimRC session and cache."""

from __future__ import annotations

import dataclasses
import threading
import time

import numpy as np
import pytest

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft.project import DragSource
from predimrc_wrapper.cost import cost
from predimrc_wrapper.data.prices import default_prices
from predimrc_wrapper.predimrc_wrapper import AeroResults
from predimrc_wrapper.predimrc_wrapper import ExcelThreadBackend
from predimrc_wrapper.predimrc_wrapper import ImposedSpeed
from tests.conftest import PROFILES
from tests.conftest import ROOT
from tests.conftest import requires_excel

APP = ROOT / "src" / "predimrc_wrapper" / "ui" / "app.py"
FILLED = {
    "count": 2,
    "n_blades": 2,
    "blade_chord_mm": 25.0,
    "radius_mm": 150.0,
    "shape": "Mixte",
    "frontal_area_dm2": 0.5,
    "thickness_mm": 12.0,
    "cds_m2": 0.001,
    "diameter_mm": 10.0,
    "length_mm": 300.0,
}


@pytest.fixture
def dv():
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui import drag_view  # noqa: PLC0415

    return drag_view


def test_every_kind_has_a_form_with_its_required_fields(dv):
    assert set(dv.SOURCE_KINDS) == set(dv.SOURCE_FIELDS)
    for kind, names in dv.SOURCE_FIELDS.items():
        assert set(names) <= set(DragSource.model_fields)
        source = dv.new_source(kind, [], "Profilé")
        # Only the fields of the form are filled: the source is then valid.
        source.update({n: FILLED[n] for n in names if n in FILLED and n != "shape"})
        DragSource.model_validate(source)


def test_new_source_names_are_unique(dv):
    first = dv.new_source("body_part", [], "Mixte")
    assert first == {"name": "body part", "kind": "body_part", "shape": "Mixte"}
    assert dv.new_source("body_part", ["body part"], "Mixte")["name"] == "body part 2"


def test_drag_tab_add_fill_remove():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415

    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    at.selectbox(key="0:drag_sources.new_kind").set_value("body_part").run()
    next(b for b in at.button if b.label == "Add").click().run()
    assert not at.exception, at.exception
    sources = at.session_state["app"].data["drag_sources"]
    assert len(sources) == 1
    assert sources[0].items() >= {"name": "body part", "kind": "body_part"}.items()
    at.number_input(key="0.0:drag_sources.0.frontal_area_dm2").set_value(0.8).run()
    assert at.session_state["app"].data["drag_sources"][0]["frontal_area_dm2"] == 0.8
    next(b for b in at.button if b.label == "Remove").click().run()
    assert not at.exception, at.exception
    assert at.session_state["app"].data["drag_sources"] == []


def test_costs_in_euros():
    project = Project.template("quadplane")
    result = cost(AircraftModel(project), 1200.0)
    assert result.currency == "EUR"
    rate = default_prices().usd_per_eur
    motors = next(i for i in result.items if i.item == "tmotor-mn2806-650kv")
    assert motors.unit_price == pytest.approx(46.90 / rate)
    # Rate of the project, then entered prices stay in euros.
    other = cost(
        AircraftModel(
            project.with_overrides({"cost": {"usd_per_eur": 1.0, "frame": 50.0}})
        ),
        1200.0,
    )
    motors = next(i for i in other.items if i.item == "tmotor-mn2806-650kv")
    assert motors.unit_price == pytest.approx(46.90)
    assert other.by_category()["frame"] == 50.0


# --- PredimRC session in its own thread, HDF5 cache -------------------------------------


def _fake_results(settings) -> AeroResults:
    v = np.array([10.0, 12.0, 15.0])
    return AeroResults(
        cz=v / 20,
        cx=v / 300,
        vx=v,
        sink_rate=-v / 30,
        finesse_vx=v,
        drag_n=v / 4,
        power_required_w=v**2 / 4,
        v_min=10.0,
        v_min_power=12.0,
        v_max_finesse=15.0,
        mass_kg=settings.mass / 1000,
        cg=25.0,
        foyer=35.0,
        total_surface=30.0,
        mean_chord=180.0,
        span_aero=1700.0,
        span_total=1740.0,
        aspect_ratio=9.6,
        aspect_ratio_el=9.0,
        power_predimrc_w=v**2 / 4,
        imposed={1: ImposedSpeed(13.9, v / 20, v / 4, v)},
    )


class FakeWrapper:
    """Records the thread of each call."""

    def __init__(self):
        self.threads = []
        self.calls = 0
        self.last_eval_seconds = 0.1

    def evaluate(self, wing, stab, fus, settings):
        self.threads.append(threading.get_ident())
        self.calls += 1
        return _fake_results(settings)

    def is_alive(self):
        self.threads.append(threading.get_ident())
        return True

    def close(self):
        self.threads.append(threading.get_ident())


def _in_thread(function):
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("out", function()))
    thread.start()
    thread.join()
    return box["out"]


def test_inputs_and_outputs_round_trip(reference_case):
    from predimrc_wrapper import aero_cache  # noqa: PLC0415

    data = aero_cache.encode_inputs(**reference_case)
    assert all(not np.isnan(v).any() for v in data.values() if v.dtype.kind == "f")
    assert aero_cache.decode_inputs(data) == reference_case  # accents, None, panels
    result = _fake_results(reference_case["settings"])
    back = aero_cache.decode_outputs(aero_cache.encode_outputs(result))
    assert back.v_min == result.v_min
    np.testing.assert_array_equal(back.drag_n, result.drag_n)
    assert np.isnan(back.rho)
    assert sorted(back.imposed) == [1]
    assert back.imposed[1].vx_m_s == 13.9
    np.testing.assert_array_equal(back.imposed[1].power_w, result.imposed[1].power_w)


def test_excel_thread_backend_runs_in_one_thread(reference_case):
    fake = FakeWrapper()
    created = []
    backend = ExcelThreadBackend(wrapper_factory=lambda: created.append(1) or fake)
    assert backend.is_alive()  # Excel not started yet
    assert not created
    _in_thread(lambda: backend.evaluate(**reference_case))
    backend.evaluate(**reference_case)
    assert _in_thread(backend.is_alive)
    backend.close()
    backend.close()  # idempotent
    assert created == [1]
    assert len(set(fake.threads)) == 1
    assert fake.threads[0] != threading.get_ident()


def test_cache_returns_stored_results_without_the_backend(reference_case, tmp_path):
    pytest.importorskip("gemseo")
    from predimrc_wrapper.aero_cache import CachedBackend  # noqa: PLC0415

    path = tmp_path / "c.h5"
    fake = FakeWrapper()
    cached = CachedBackend(fake, path, "SD7003_abc_v1")
    first = cached.evaluate(**reference_case)
    again = _in_thread(lambda: cached.evaluate(**reference_case))
    assert fake.calls == 1
    assert (cached.hits, cached.misses) == (1, 1)
    np.testing.assert_array_equal(again.drag_n, first.drag_n)
    heavier = dict(reference_case)
    heavier["settings"] = dataclasses.replace(reference_case["settings"], mass=2500.0)
    cached.evaluate(**heavier)
    assert fake.calls == 2
    # A new session reads the file; another workbook (node) does not reuse it.
    fresh = FakeWrapper()
    assert (
        CachedBackend(fresh, path, "SD7003_abc_v1").evaluate(**heavier).mass_kg == 2.5
    )
    assert fresh.calls == 0
    CachedBackend(fresh, path, "SD7003_other_v1").evaluate(**heavier)
    assert fresh.calls == 1


@requires_excel
def test_gui_backend_from_several_threads(reference_case, tmp_path, caplog):
    pytest.importorskip("gemseo")
    from predimrc_wrapper.aero_cache import open_backend  # noqa: PLC0415

    backend = open_backend("SD7003", PROFILES, tmp_path / "c.h5")
    first = _in_thread(lambda: backend.evaluate(**reference_case))
    assert _in_thread(backend.is_alive)
    start = time.perf_counter()
    again = _in_thread(lambda: backend.evaluate(**reference_case))
    assert time.perf_counter() - start < 1.0
    assert again.v_min == first.v_min
    _in_thread(backend.close)
    assert "cleanly" not in caplog.text
