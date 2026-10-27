"""Display units of the GUI (REQ-NFR-002)."""

from __future__ import annotations

import math

import pytest

from predimrc_wrapper.ui import units


def test_thrust_text_n_and_kg():
    assert units.thrust_text(9.81) == "9.81 N (1.00 kg)"
    assert units.thrust_text(float("nan")) == "—"
    assert units.thrust_text(None) == "—"


def test_speeds_km_h():
    assert units.kmh(10.0) == pytest.approx(36.0)
    assert units.m_s(54.0) == pytest.approx(15.0)
    assert units.speed_text(15.0) == "54 km/h"
    assert units.speed_text(math.inf) == "—"


def test_airspeed_fields_in_km_h():
    pytest.importorskip("streamlit")
    from predimrc_wrapper.ui.forms import is_airspeed  # noqa: PLC0415

    assert is_airspeed("speed_m_s")
    assert is_airspeed("cruise_max_speed_m_s")
    assert not is_airspeed("vertical_speed_m_s")
    assert not is_airspeed("v_axial_m_s")
