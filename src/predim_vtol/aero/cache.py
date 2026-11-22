"""Persistent cache of the PredimRC evaluations (``joblib.Memory``).

An Excel evaluation takes about 0.3 s and starting Excel about 7 s; the same geometry, mass,
environment and imposed speeds are evaluated again and again across Runs, studies and
sessions. ``CachedBackend`` wraps any PredimRC backend: an evaluation already stored is read
from the cache folder without starting Excel.

The key of an evaluation is ``joblib.hash`` of the fields of ``WingGeometry``,
``StabGeometry``, ``FuselageGeometry`` and ``Settings``, numbers as floats (``2500`` and
``2500.0`` give the same entry), and of the workbook key (profile, content hash of the
workbook, ``CACHE_VERSION``): a modified workbook or a new version of the wrapper outputs
gives new entries instead of reusing stale results. The result, an ``AeroResults``, is
stored by pickle. joblib also empties the cache when the code of ``_evaluate`` changes.

Windows limits paths to 260 characters and joblib nests its entries
(``<folder>/<module>/<function>/<hash>/output.pkl.<temporary name>``), silently giving up
caching beyond: hence the short module name of ``_evaluate`` and no sub-folder per
workbook.

Several processes may share the folder (a script and the GUI): joblib writes each entry
under a temporary name then renames it, so an entry is never read half-written; at worst
the same point is computed twice.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from joblib import Memory

from predim_vtol.aero.predimrc import ExcelThreadBackend
from predim_vtol.aero.predimrc import workbook_path

if TYPE_CHECKING:
    from typing_extensions import Self

    from predim_vtol.aero.base import AeroBackend
    from predim_vtol.aero.base import AeroResults
    from predim_vtol.aero.base import FuselageGeometry
    from predim_vtol.aero.base import Settings
    from predim_vtol.aero.base import StabGeometry
    from predim_vtol.aero.base import WingGeometry

CACHE_VERSION = 3
"""Increment when the outputs read from the workbook change: the old entries are then ignored.

3: ``joblib.Memory`` folder instead of the GEMSEO HDF5 file (version 2)."""


def default_cache_path() -> Path:
    """The cache folder of the settings, ``~/.predim_vtol/predimrc_cache`` by default.

    A setting naming the HDF5 file of the former cache (``*.h5``) gives the folder of the
    same name without the suffix.
    """
    from predim_vtol.settings import Settings  # noqa: PLC0415
    from predim_vtol.settings import home_dir  # noqa: PLC0415

    path = Settings.load().predimrc_cache
    path = Path(path) if path else home_dir() / "predimrc_cache"
    return path.with_suffix("") if path.suffix == ".h5" else path


def _value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_value(v) for v in value)
    if value is None or isinstance(value, str):
        return value
    return float(value)


def evaluation_key(*inputs: Any) -> tuple:
    """The fields of the inputs, numbers as floats: what the cache entry depends on."""
    return tuple(
        (type(i).__name__, f.name, _value(getattr(i, f.name)))
        for i in inputs
        for f in fields(i)
    )


def _evaluate(
    backend: AeroBackend,
    key: tuple,  # noqa: ARG001 - the only argument hashed by joblib
    wing: WingGeometry,
    stab: StabGeometry,
    fus: FuselageGeometry,
    settings: Settings,
) -> AeroResults:
    return backend.evaluate(wing=wing, stab=stab, fus=fus, settings=settings)


_evaluate.__module__ = (
    "predimrc"  # joblib folder <cache>/predimrc/_evaluate (short paths)
)


IGNORED = ["backend", "wing", "stab", "fus", "settings"]
"""Arguments of ``_evaluate`` left out of the hash: the backend, and the inputs, which
``key`` represents."""


def workbook_key(profile: str, template_dir: str | Path) -> str:
    """Key of a workbook: profile, content hash of the file, cache version."""
    path = workbook_path(template_dir, profile)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{profile}_{digest}_v{CACHE_VERSION}"


class CachedBackend:
    """A PredimRC backend whose evaluations are stored in a cache folder.

    Args:
        backend: The backend evaluating the cache misses (Excel is only started by them
            with an ``ExcelThreadBackend``).
        cache_path: The cache folder.
        node: The key of the workbook (``workbook_key``), part of every entry key.
    """

    name = "predimrc"

    def __init__(self, backend: AeroBackend, cache_path: str | Path, node: str) -> None:
        self.backend = backend
        self.cache_path = Path(cache_path)
        self.node = node
        self._evaluate = Memory(self.cache_path, verbose=0).cache(
            _evaluate, ignore=IGNORED
        )
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def evaluate(
        self,
        wing: WingGeometry,
        stab: StabGeometry,
        fus: FuselageGeometry,
        settings: Settings,
    ) -> AeroResults:
        args = (self.backend, (self.node, *evaluation_key(wing, stab, fus, settings)))
        args += (wing, stab, fus, settings)
        # Several GUI threads share this backend: the check and the call go together.
        with self._lock:
            if self._evaluate.check_call_in_cache(*args):
                self.hits += 1
            else:
                self.misses += 1
            return self._evaluate(*args)

    run = evaluate

    @property
    def last_eval_seconds(self) -> float:
        return getattr(self.backend, "last_eval_seconds", float("nan"))

    def is_alive(self) -> bool:
        is_alive = getattr(self.backend, "is_alive", None)
        return True if is_alive is None else is_alive()

    def close(self) -> None:
        self.backend.close()


def open_backend(
    profile: str,
    template_dir: str | Path,
    cache_path: str | Path | None = None,
) -> AeroBackend:
    """The PredimRC backend of the tool: Excel in its own thread, behind the cache.

    Args:
        profile: The wing airfoil.
        template_dir: The folder of the PredimRC workbooks.
        cache_path: The cache folder; the one of the settings by default.

    Returns:
        The backend, to close after use.
    """
    excel = ExcelThreadBackend(profile, template_dir)
    return CachedBackend(
        excel, cache_path or default_cache_path(), workbook_key(profile, template_dir)
    )
