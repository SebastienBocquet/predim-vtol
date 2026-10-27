"""CSV import of a thrust–power test into the user data folder (REQ-DATA-005, Could)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import yaml

from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.data.database import DatabaseError
from predimrc_wrapper.data.database import default_database
from predimrc_wrapper.data.propellers import default_propellers
from predimrc_wrapper.data.tests import COLUMNS
from predimrc_wrapper.data.tests import USER_FOLDER
from predimrc_wrapper.data.tests import ThrustTest
from predimrc_wrapper.data.tests import default_tests
from predimrc_wrapper.data.tests import parse_test
from predimrc_wrapper.data.user import user_data_dir

ALIASES = {"throttle": "throttle_pct", "thrust_n": "thrust_g"}
"""CSV header aliases; ``thrust_n`` is converted to grams."""


def csv_table(text: str) -> tuple[list[str], list[list[float | None]]]:
    """Columns (among ``COLUMNS``) and rows of a CSV test (first line = column names).

    The aliases of ``ALIASES`` are accepted; ``thrust_n`` is converted to grams. Empty
    cells are None.
    """
    reader = csv.DictReader(io.StringIO(text))
    header = [n.strip() for n in reader.fieldnames or []]
    names = [ALIASES.get(n, n) for n in header]
    rows = [
        [None if v in ("", None) else float(v) for v in row.values()] for row in reader
    ]
    if "thrust_n" in header:
        i = names.index("thrust_g")
        rows = [
            [*r[:i], None if r[i] is None else r[i] / GRAVITY * 1000.0, *r[i + 1 :]]
            for r in rows
        ]
    columns = [n for n in names if n in COLUMNS]
    keep = [names.index(c) for c in columns]
    return columns, [[r[i] for i in keep] for r in rows]


def import_csv(
    path: str | Path, header: dict[str, Any]
) -> tuple[ThrustTest, dict[str, Any]]:
    """Read a CSV of a test (columns among ``COLUMNS``, or ``thrust_n``) and its header form.

    Args:
        path: The CSV file (comma separated, first line = column names).
        header: id, motor_id, propeller_id, voltage_v, bench, source, retrieved, status,
            and optionally esc, measured_at, temperature_c, notes.

    Returns:
        The validated test and the mapping to write as a YAML file.
    """
    columns, rows = csv_table(Path(path).read_text(encoding="utf-8"))
    raw = {**header, "columns": columns, "rows": rows}
    return parse_test(raw, str(path)), raw


def write_user_test(raw: dict[str, Any], folder: str | Path | None = None) -> Path:
    """Write a test mapping as ``<folder or user data>/thrust_tests/<id>.yaml``."""
    target = Path(folder) if folder is not None else user_data_dir() / USER_FOLDER
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{raw['id']}.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def add_user_test(
    raw: dict[str, Any], folder: str | Path | None = None
) -> tuple[ThrustTest, Path]:
    """Validate a test of known motor and propeller, write it in the user tests.

    The thrust–power surrogate is fitted again on its next use (cache keyed by the test
    data hash).

    Args:
        raw: The test mapping (as a YAML file); the fields of ``USER_DEFAULTS`` may be
            left out.
        folder: The folder of the user tests.

    Raises:
        DatabaseError: When the test is invalid, its id already exists, or its motor or
            propeller is not in the databases.
    """
    raw = {k: v for k, v in raw.items() if v not in (None, "")}
    if "rows" in raw:  # plain floats for the YAML file (the rows may hold numpy values)
        raw["rows"] = [
            [None if v is None else float(v) for v in r] for r in raw["rows"]
        ]
    test = parse_test(raw, "new test", user=True)
    try:
        default_database().motor(test.motor_id)
        default_propellers().propeller(test.propeller_id)
    except KeyError as error:
        raise DatabaseError(error.args[0]) from None
    if test.id in default_tests().records:
        msg = f"The test id '{test.id}' already exists"
        raise DatabaseError(msg)
    path = write_user_test(raw, folder)
    default_tests.cache_clear()
    return test, path
