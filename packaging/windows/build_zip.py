"""Build the one-click Windows installer zip: ``python packaging/windows/build_zip.py``.

The zip holds the project wheel, the locked and hashed dependencies, ``uv.exe`` and the
install scripts; Python and the dependencies are downloaded at installation.

PredimRC is left out by default: its terms are not consistent (THIRD_PARTY_NOTICES.md).
``--predimrc-dir DIR --predimrc-notice FILE`` adds the workbooks of ``DIR``, together with
a notice of their author and terms (the release note of PredimRC, or a written agreement
of its author), shipped as ``LICENSES/PredimRC-<file name>``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TEXT_FILES = ("install.bat", "install.ps1", "uninstall.bat", "README.txt")
"""Files of this folder written with the Windows line endings that ``cmd.exe`` needs."""
LICENCE_FILES = ("LICENSE.txt", "THIRD_PARTY_NOTICES.md")
WORKBOOK_SUFFIXES = (".xls", ".xlsx", ".xlsm", ".xlsb")


def crlf(content: bytes) -> bytes:
    """Convert the line endings to CRLF, whatever the checkout produced."""
    return content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def check_wheel(wheel: Path) -> None:
    """Refuse a wheel carrying a workbook: workbooks only come with their notice."""
    with zipfile.ZipFile(wheel) as archive:
        workbooks = [
            name for name in archive.namelist() if name.endswith(WORKBOOK_SUFFIXES)
        ]
    if workbooks:
        msg = f"The wheel must not contain workbooks: {workbooks}"
        raise SystemExit(msg)


def select_workbooks(folder: Path | None, notice: Path | None) -> list[Path]:
    """The workbooks to bundle, only together with the notice of their author and terms."""
    if folder is None and notice is None:
        return []
    if folder is None or notice is None:
        msg = "--predimrc-dir and --predimrc-notice go together."
        raise SystemExit(msg)
    if not notice.is_file():
        msg = f"Notice file not found: {notice}"
        raise SystemExit(msg)
    workbooks = sorted(
        path
        for path in folder.glob("PredimRC_*")
        if path.suffix.lower() in WORKBOOK_SUFFIXES
        # Same rule as ``discover_profiles``: no dot in the profile name (excludes backups).
        and "." not in path.stem
    )
    if not workbooks:
        msg = f"No PredimRC_<profile>.xls workbook in {folder}"
        raise SystemExit(msg)
    return workbooks


def run(*command: str) -> None:
    """Run a build command from the repository root."""
    subprocess.run(command, cwd=ROOT, check=True)


def build(output: Path, workbooks: list[Path], notice: Path | None, uv: str) -> Path:
    """Build the zip in ``output`` and return its path."""
    with tempfile.TemporaryDirectory() as tmp:
        wheels = Path(tmp) / "wheel"
        run(uv, "build", "--wheel", "--out-dir", str(wheels))
        wheel = next(wheels.glob("*.whl"))
        check_wheel(wheel)
        requirements = Path(tmp) / "requirements.txt"
        run(
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--extra",
            "mdo",
            "--extra",
            "ui",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
            "--quiet",
        )
        version = wheel.name.split("-")[1]
        output.mkdir(parents=True, exist_ok=True)
        path = output / f"predimrc_wrapper-{version}-windows.zip"
        prefix = path.stem
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in TEXT_FILES:
                archive.writestr(f"{prefix}/{name}", crlf((HERE / name).read_bytes()))
            archive.write(wheel, f"{prefix}/{wheel.name}")
            archive.write(requirements, f"{prefix}/requirements.txt")
            archive.write(uv, f"{prefix}/uv.exe")
            for name in LICENCE_FILES:
                archive.write(ROOT / name, f"{prefix}/{name}")
            for licence in sorted((ROOT / "LICENSES").iterdir()):
                archive.write(licence, f"{prefix}/LICENSES/{licence.name}")
            for workbook in workbooks:
                archive.write(workbook, f"{prefix}/predimrc/{workbook.name}")
            if notice is not None:
                archive.write(
                    notice,
                    f"{prefix}/LICENSES/PredimRC-{notice.name.removeprefix('PredimRC_')}",
                )
    return path


def main() -> None:
    """Parse the command line and build the zip."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--predimrc-dir", type=Path)
    parser.add_argument(
        "--predimrc-notice",
        type=Path,
        help="Author and terms of PredimRC (release note or written agreement), "
        "shipped with the workbooks.",
    )
    args = parser.parse_args()
    if sys.platform != "win32":
        msg = "Build on Windows: the zip ships the local uv.exe."
        raise SystemExit(msg)
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv not found: https://docs.astral.sh/uv/"
        raise SystemExit(msg)
    workbooks = select_workbooks(args.predimrc_dir, args.predimrc_notice)
    path = build(args.output, workbooks, args.predimrc_notice, uv)
    size = path.stat().st_size / 1e6
    print(f"{path} ({size:.0f} MB, {len(workbooks)} PredimRC workbook(s))")


if __name__ == "__main__":
    main()
