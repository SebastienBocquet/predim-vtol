"""Shared test fixtures: Excel availability and the PredimRC reference case."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"


def _excel_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg  # noqa: PLC0415

        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application")
    except OSError:
        return False
    return (PROFILES / "PredimRC_SD7003.xls").is_file()


EXCEL = _excel_available()
requires_excel = pytest.mark.skipif(
    not EXCEL, reason="Excel and PredimRC workbook required"
)


@pytest.fixture(scope="session")
def predimrc():
    """One PredimRC session shared by the slow tests."""
    if not EXCEL:
        pytest.skip("Excel and PredimRC workbook required")
    from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper  # noqa: PLC0415

    with PredimRCWrapper(profile="SD7003", template_dir=PROFILES) as wrapper:
        yield wrapper


@pytest.fixture
def reference_case():
    """The tricoptere_short_2 geometry of the PredimRC screenshot."""
    from predimrc_wrapper.predimrc_wrapper import FuselageGeometry  # noqa: PLC0415
    from predimrc_wrapper.predimrc_wrapper import Settings  # noqa: PLC0415
    from predimrc_wrapper.predimrc_wrapper import StabGeometry  # noqa: PLC0415
    from predimrc_wrapper.predimrc_wrapper import WingGeometry  # noqa: PLC0415

    return {
        "wing": WingGeometry(
            root_chord=200.0,
            tip_chord=[200.0, 185.0, 140.0, 50.0],
            length=[285.0, 300.0, 180.0, 105.0],
            le_offset=[0.0, 7.0, 40.0, 150.0],
            twist=[0.0, 0.0, 0.0, 0.0],
            dihedral=[0.0, 1.0, 1.0, 20.0],
        ),
        "stab": StabGeometry(
            root_chord=140.0,
            tip_chord=[100.0],
            length=[320.0],
            le_offset=[170.0],
            lever=360.0,
            stab_height=0.0,
            profile="Biconvexe fin",
            opening="120",
            lateral_gap=20.0,
        ),
        "fus": FuselageGeometry(
            length=760.0,
            width=85.0,
            height=115.0,
            nose_lever=270.0,
            shape="Profilée",
            beam="Normale",
            wing_pos="médiane",
            incidence="aile",
            accessory_surface=0.6,
            accessory_shape="Non profilé",
        ),
        "settings": Settings(mass=1920.0, static_margin=5.0, cz_reg=0.30),
    }
