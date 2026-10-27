"""Thrust–power test data of motor + propeller pairs (REQ-DATA-005, REQ-DATA-003).

One YAML file per test (manufacturer units: thrust in g, rpm, %), converted to SI on
load. ``measured_at`` tells where the electric power was measured: ``esc_input`` when the
table names the ESC used (its loss is inside the power), ``motor_input`` otherwise.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path

import numpy as np
import yaml

from predimrc_wrapper.core.units import GRAVITY
from predimrc_wrapper.data.database import DatabaseError
from predimrc_wrapper.data.user import user_data_dir

USER_FOLDER = "thrust_tests"
"""Folder of the user tests in the user data folder."""

REQUIRED = (
    "id",
    "motor_id",
    "propeller_id",
    "voltage_v",
    "bench",
    "source",
    "retrieved",
    "status",
    "columns",
    "rows",
)
COLUMNS = (
    "throttle_pct",
    "voltage_v",
    "current_a",
    "power_w",
    "thrust_g",
    "rpm",
    "torque_nm",
)
MANDATORY_COLUMNS = ("current_a", "power_w", "thrust_g")
USER_DEFAULTS = {
    "bench": "user",
    "source": "user entry",
    "retrieved": "",
    "status": "estimated",
}
"""Values of the fields a user test may leave out: no computation uses them."""


@dataclass(frozen=True)
class ThrustTest:
    """One test table: arrays in SI (NaN where the table gives no value)."""

    id: str
    motor_id: str
    propeller_id: str
    esc: str | None
    measured_at: str
    """``esc_input`` or ``motor_input``."""
    voltage_v: float
    """Nominal voltage of the table (V)."""
    bench: str
    source: str
    retrieved: str
    status: str
    throttle: np.ndarray
    """Throttle (fraction)."""
    voltage: np.ndarray
    """Voltage of each row (V); the nominal voltage when the table gives one value."""
    current_a: np.ndarray
    power_w: np.ndarray
    thrust_n: np.ndarray
    rpm: np.ndarray
    torque_nm: np.ndarray
    temperature_c: float | None = None
    notes: str = ""
    origin: str = ""

    @property
    def pair(self) -> tuple[str, str]:
        return self.motor_id, self.propeller_id

    @property
    def max_thrust_n(self) -> float:
        return float(np.nanmax(self.thrust_n))


def parse_test(raw: dict, origin: str, user: bool = False) -> ThrustTest:
    """Validate a test mapping (file content) and convert it to SI.

    A user test (``user``) may leave out the fields of ``USER_DEFAULTS``.
    """
    if user:
        raw = {**USER_DEFAULTS, **{k: v for k, v in raw.items() if v not in (None, "")}}
    for key in REQUIRED:
        if raw.get(key) in (None, "", []) and not (user and key in USER_DEFAULTS):
            msg = f"{origin}: {raw.get('id', '?')}: missing {key}"
            raise DatabaseError(msg)
    if raw["status"] not in ("verified", "estimated"):
        msg = f"{origin}: {raw['id']}: status must be verified or estimated"
        raise DatabaseError(msg)
    esc = raw.get("esc")
    measured_at = raw.get("measured_at") or ("esc_input" if esc else "motor_input")
    if measured_at not in ("esc_input", "motor_input"):
        msg = f"{origin}: {raw['id']}: measured_at must be esc_input or motor_input"
        raise DatabaseError(msg)
    columns = list(raw["columns"])
    unknown = set(columns) - set(COLUMNS)
    missing = [c for c in MANDATORY_COLUMNS if c not in columns]
    if unknown or missing:
        msg = f"{origin}: {raw['id']}: unknown columns {sorted(unknown)}, missing {missing}"
        raise DatabaseError(msg)
    table = np.array(
        [[np.nan if v is None else float(v) for v in row] for row in raw["rows"]],
        dtype=float,
    )
    if table.ndim != 2 or table.shape[1] != len(columns):
        msg = f"{origin}: {raw['id']}: every row needs {len(columns)} values"
        raise DatabaseError(msg)

    def col(name: str) -> np.ndarray:
        return (
            table[:, columns.index(name)]
            if name in columns
            else np.full(len(table), np.nan)
        )

    thrust, power, current = (
        col("thrust_g") * GRAVITY / 1000.0,
        col("power_w"),
        col("current_a"),
    )
    if np.any(~(thrust > 0)) or np.any(~(power > 0)) or np.any(~(current > 0)):
        msg = f"{origin}: {raw['id']}: thrust, power and current must be positive"
        raise DatabaseError(msg)
    voltage = col("voltage_v")
    voltage = np.where(np.isfinite(voltage), voltage, float(raw["voltage_v"]))
    retrieved = raw["retrieved"]
    return ThrustTest(
        id=raw["id"],
        motor_id=raw["motor_id"],
        propeller_id=raw["propeller_id"],
        esc=esc,
        measured_at=measured_at,
        voltage_v=float(raw["voltage_v"]),
        bench=raw["bench"],
        source=raw["source"],
        retrieved=retrieved.isoformat()
        if isinstance(retrieved, date)
        else str(retrieved),
        status=raw["status"],
        throttle=col("throttle_pct") / 100.0,
        voltage=voltage,
        current_a=current,
        power_w=power,
        thrust_n=thrust,
        rpm=col("rpm"),
        torque_nm=col("torque_nm"),
        temperature_c=None
        if raw.get("temperature_c") is None
        else float(raw["temperature_c"]),
        notes=raw.get("notes", ""),
        origin=origin,
    )


class TestDatabase:
    """All the thrust–power tests (shipped files, then user files overriding by id)."""

    __test__ = False  # not a pytest class

    def __init__(
        self,
        tests: dict[str, ThrustTest],
        warnings: list[str] | None = None,
        digest: str = "",
    ) -> None:
        self.records = tests
        self.warnings = warnings or []
        self._digest = digest

    @classmethod
    def load(cls, folders: list[Path] | None = None) -> TestDatabase:
        """Load the YAML files of the folders (default: shipped, then ``<user data>/thrust_tests``)."""
        if folders is None:
            shipped = files("predimrc_wrapper.data").joinpath("thrust_tests")
            sources = [
                (f.name, f.read_text(encoding="utf-8"), False)
                for f in sorted(shipped.iterdir(), key=lambda f: f.name)
                if f.name.endswith(".yaml")
            ]
            user = user_data_dir() / USER_FOLDER
            if user.is_dir():
                sources += [
                    (str(p), p.read_text(encoding="utf-8"), True)
                    for p in sorted(user.glob("*.yaml"))
                ]
        else:
            sources = [
                (str(p), p.read_text(encoding="utf-8"), False)
                for d in folders
                for p in sorted(Path(d).glob("*.yaml"))
            ]
        tests, warnings = {}, []
        digest = hashlib.sha256()
        for origin, text, is_user in sources:
            test = parse_test(yaml.safe_load(text), origin, user=is_user)
            if test.id in tests:
                warnings.append(
                    f"{origin} overrides the test {test.id} of {tests[test.id].origin}"
                )
            tests[test.id] = test
            digest.update(text.encode("utf-8"))
        return cls(tests, warnings, digest.hexdigest()[:16])

    def tests(
        self, motor_id: str | None = None, propeller_id: str | None = None
    ) -> list[ThrustTest]:
        """Tests of a motor, a propeller or a pair (all when both are None)."""
        return [
            t
            for t in self.records.values()
            if (motor_id is None or t.motor_id == motor_id)
            and (propeller_id is None or t.propeller_id == propeller_id)
        ]

    def pairs(self) -> list[tuple[str, str]]:
        """Tested (motor, propeller) pairs, sorted."""
        return sorted({t.pair for t in self.records.values()})

    def hash(self) -> str:
        """Content hash of the loaded files (recorded with results and studies)."""
        return self._digest


@cache
def default_tests() -> TestDatabase:
    """The shipped and user tests (cached)."""
    return TestDatabase.load()
