"""The tool folder ``~/.predim_vtol`` and the migration from the former name."""

from __future__ import annotations

from pathlib import Path

import pytest

from predim_vtol.settings import LEGACY_HOME
from predim_vtol.settings import home_dir


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.delenv("PREDIM_VTOL_HOME")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_legacy_folder_is_copied(home):
    legacy = home / LEGACY_HOME
    (legacy / "data").mkdir(parents=True)
    (legacy / "data" / "motors.yaml").write_text("motors: []\n", encoding="utf-8")
    (legacy / "settings.yaml").write_text("studies_root: x\n", encoding="utf-8")
    (legacy / "predimrc_cache.h5").write_bytes(b"cache")
    new = home_dir()
    assert new == home / ".predim_vtol"
    assert (new / "settings.yaml").read_text(encoding="utf-8") == "studies_root: x\n"
    assert (new / "data" / "motors.yaml").is_file()
    assert not (new / "predimrc_cache.h5").exists()
    # The former version, maybe still installed, keeps its folder.
    assert (legacy / "settings.yaml").is_file()
    assert (legacy / "predimrc_cache.h5").is_file()


def test_existing_folder_wins(home):
    (home / LEGACY_HOME).mkdir()
    (home / LEGACY_HOME / "settings.yaml").write_text("old\n", encoding="utf-8")
    (home / ".predim_vtol").mkdir()
    assert home_dir() == home / ".predim_vtol"
    assert not (home / ".predim_vtol" / "settings.yaml").exists()


def test_no_folder(home):
    assert home_dir() == home / ".predim_vtol"
    assert not (home / ".predim_vtol").exists()


def test_home_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDIM_VTOL_HOME", str(tmp_path / "portable"))
    assert home_dir() == tmp_path / "portable"


def test_tests_do_not_touch_the_user_folder():
    """The session fixture gives the tests a tool folder of their own."""
    assert home_dir() != Path.home() / ".predim_vtol"
