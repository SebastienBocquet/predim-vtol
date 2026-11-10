"""The Windows package: PredimRC only with the notice of its author and terms."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "packaging" / "windows" / "build_zip.py"
spec = importlib.util.spec_from_file_location("build_zip", SCRIPT)
build_zip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_zip)


def test_no_workbook_by_default():
    assert build_zip.select_workbooks(None, None) == []


@pytest.mark.parametrize("given", ["folder", "notice"])
def test_workbooks_and_notice_go_together(tmp_path, given):
    folder = tmp_path if given == "folder" else None
    notice = tmp_path / "ok.txt" if given == "notice" else None
    with pytest.raises(SystemExit, match="go together"):
        build_zip.select_workbooks(folder, notice)


def test_missing_notice_file_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="Notice file not found"):
        build_zip.select_workbooks(tmp_path, tmp_path / "missing.txt")


def test_backups_are_not_bundled(tmp_path):
    for name in ("PredimRC_SD7003.xls", "PredimRC_SD7003.old.bak.xls", "other.xls"):
        (tmp_path / name).touch()
    notice = tmp_path / "ok.txt"
    notice.touch()
    selected = build_zip.select_workbooks(tmp_path, notice)
    assert [path.name for path in selected] == ["PredimRC_SD7003.xls"]


def test_wheel_with_a_workbook_is_refused(tmp_path):
    wheel = tmp_path / "w.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pkg/PredimRC_SD7003.xls", b"")
    with pytest.raises(SystemExit, match="must not contain workbooks"):
        build_zip.check_wheel(wheel)


@pytest.mark.parametrize("content", [b"a\nb\n", b"a\r\nb\r\n"])
def test_crlf(content):
    assert build_zip.crlf(content) == b"a\r\nb\r\n"
