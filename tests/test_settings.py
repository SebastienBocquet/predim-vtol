"""The tool folder ``~/.predim_vtol`` and the migration from the former name."""

from __future__ import annotations

from pathlib import Path

from predim_vtol.settings import LEGACY_HOME
from predim_vtol.settings import home_dir


def test_legacy_folder_is_renamed(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy = tmp_path / LEGACY_HOME
    (legacy / "data").mkdir(parents=True)
    (legacy / "settings.yaml").write_text("studies_root: x\n", encoding="utf-8")
    home = home_dir()
    assert home == tmp_path / ".predim_vtol"
    assert (home / "settings.yaml").read_text(encoding="utf-8") == "studies_root: x\n"
    assert (home / "data").is_dir()
    assert not legacy.exists()


def test_existing_folder_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / LEGACY_HOME).mkdir()
    (tmp_path / ".predim_vtol").mkdir()
    assert home_dir() == tmp_path / ".predim_vtol"
    assert (tmp_path / LEGACY_HOME).is_dir()


def test_no_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert home_dir() == tmp_path / ".predim_vtol"
    assert not (tmp_path / ".predim_vtol").exists()
