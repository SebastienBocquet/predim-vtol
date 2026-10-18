"""CSV import of a thrust–power test into the user data folder (REQ-DATA-005, Could)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from predimrc_wrapper.data.tests import COLUMNS
from predimrc_wrapper.data.tests import ThrustTest
from predimrc_wrapper.data.tests import parse_test
from predimrc_wrapper.data.user import user_data_dir

ALIASES = {"throttle": "throttle_pct", "thrust_n": "thrust_g"}
"""CSV header aliases; ``thrust_n`` is converted to grams."""


def import_csv(path: str | Path, header: dict[str, Any]) -> tuple[ThrustTest, dict[str, Any]]:
    """Read a CSV of a test (columns among ``COLUMNS``, or ``thrust_n``) and its header form.

    Args:
        path: The CSV file (comma separated, first line = column names).
        header: id, motor_id, propeller_id, voltage_v, bench, source, retrieved, status,
            and optionally esc, measured_at, temperature_c, notes.

    Returns:
        The validated test and the mapping to write as a YAML file.
    """
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        names = [ALIASES.get(n.strip(), n.strip()) for n in reader.fieldnames or []]
        rows = []
        for row in reader:
            values = [None if v in ("", None) else float(v) for v in row.values()]
            rows.append(values)
    if "thrust_g" in names and "thrust_n" in [n.strip() for n in reader.fieldnames]:
        i = names.index("thrust_g")
        rows = [[*r[:i], None if r[i] is None else r[i] / 9.81 * 1000.0, *r[i + 1:]] for r in rows]
    columns = [n for n in names if n in COLUMNS]
    keep = [names.index(c) for c in columns]
    raw = {**header, "columns": columns, "rows": [[r[i] for i in keep] for r in rows]}
    return parse_test(raw, str(path)), raw


def write_user_test(raw: dict[str, Any], folder: str | Path | None = None) -> Path:
    """Write a test mapping as ``<folder or user data>/thrust_tests/<id>.yaml``."""
    target = Path(folder) if folder is not None else user_data_dir() / "thrust_tests"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{raw['id']}.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
