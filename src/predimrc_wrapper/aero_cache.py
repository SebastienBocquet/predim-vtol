"""Persistent cache of the PredimRC evaluations (GEMSEO discipline with an HDF5 cache).

An Excel evaluation takes about 0.3 s and starting Excel about 7 s; the same geometry, mass,
environment and imposed speeds are evaluated again and again across Runs, studies and
sessions. ``CachedBackend`` wraps any PredimRC backend: each evaluation goes through
``PredimRCDiscipline``, whose ``HDF5Cache`` returns the stored outputs when the inputs were
already evaluated, without starting Excel.

The inputs are the fields of ``WingGeometry``, ``StabGeometry``, ``FuselageGeometry`` and
``Settings`` (lists padded to the 5 panels, labels as UTF-8 codes, ``None`` as ``UNSET``); the
outputs the fields of ``AeroResults`` (the imposed-speed blocks as ``imposed.<k>.<field>``,
empty when not computed). The node of the HDF5 file is named after the profile, the
content hash of its workbook and ``CACHE_VERSION``: a modified workbook or a new version of
the wrapper outputs starts a new node instead of reusing stale results.

GEMSEO is optional (``mdo`` extra): without it, ``open_backend`` returns the uncached backend.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from predimrc_wrapper.predimrc_wrapper import AeroResults
from predimrc_wrapper.predimrc_wrapper import ExcelThreadBackend
from predimrc_wrapper.predimrc_wrapper import FuselageGeometry
from predimrc_wrapper.predimrc_wrapper import ImposedSpeed
from predimrc_wrapper.predimrc_wrapper import Settings
from predimrc_wrapper.predimrc_wrapper import StabGeometry
from predimrc_wrapper.predimrc_wrapper import WingGeometry
from predimrc_wrapper.predimrc_wrapper import workbook_path

if TYPE_CHECKING:
    from typing_extensions import Self

    from predimrc_wrapper.predimrc_wrapper import AeroBackend

LOGGER = logging.getLogger(__name__)

CACHE_VERSION = 2
"""Increment when the outputs read from the workbook change: the old entries are then ignored."""

UNSET = -1.0e300
"""Input value standing for ``None`` (NaN would never match: NaN != NaN)."""

INPUT_CLASSES = {
    "wing": WingGeometry,
    "stab": StabGeometry,
    "fus": FuselageGeometry,
    "settings": Settings,
}
IMPOSED_KEYS = (1, 2)
IMPOSED_FIELDS = ("vx_m_s", "cz_wing", "drag_n", "power_w")


def default_cache_path() -> Path:
    """The cache file of the settings, ``~/.predimrc_wrapper/predimrc_cache.h5`` by default."""
    from predimrc_wrapper.settings import Settings  # noqa: PLC0415

    path = Settings.load().predimrc_cache
    return (
        Path(path) if path else Path.home() / ".predimrc_wrapper" / "predimrc_cache.h5"
    )


def _is_list(cls: type, name: str) -> bool:
    return "list" in str(cls.__dataclass_fields__[name].type)


def encode_inputs(
    wing: WingGeometry, stab: StabGeometry, fus: FuselageGeometry, settings: Settings
) -> dict[str, np.ndarray]:
    """The PredimRC inputs as named arrays."""
    data = {}
    for group, value in zip(INPUT_CLASSES, (wing, stab, fus, settings), strict=True):
        for f in fields(value):
            v = getattr(value, f.name)
            if isinstance(v, str):
                # UTF-8 codes: the HDF5 cache writes strings as ASCII (labels are accented).
                data[f"{group}.{f.name}"] = np.frombuffer(v.encode(), dtype=np.uint8)
            else:
                items = v if isinstance(v, list) else [v]
                data[f"{group}.{f.name}"] = np.array([
                    UNSET if x is None else float(x) for x in items
                ])
    return data


def decode_inputs(data: dict[str, np.ndarray]) -> dict[str, Any]:
    """The keyword arguments of ``evaluate`` from the named arrays."""
    out = {}
    for group, cls in INPUT_CLASSES.items():
        kwargs = {}
        for f in fields(cls):
            array = data[f"{group}.{f.name}"]
            if str(f.type) == "str":
                kwargs[f.name] = bytes(array.astype(np.uint8)).decode()
                continue
            values = [None if x == UNSET else float(x) for x in array]
            kwargs[f.name] = values if _is_list(cls, f.name) else values[0]
        out[group] = cls(**kwargs)
    return out


def output_names() -> list[str]:
    names = [f.name for f in fields(AeroResults) if f.name != "imposed"]
    names += [f"imposed.{k}.{n}" for k in IMPOSED_KEYS for n in IMPOSED_FIELDS]
    return names


def encode_outputs(result: AeroResults) -> dict[str, np.ndarray]:
    """The results as named arrays."""
    data = {}
    for f in fields(result):
        if f.name != "imposed":
            data[f.name] = np.atleast_1d(
                np.asarray(getattr(result, f.name), dtype=float)
            )
    for k in IMPOSED_KEYS:
        block = result.imposed.get(k)
        for n in IMPOSED_FIELDS:
            data[f"imposed.{k}.{n}"] = (
                np.zeros(0)
                if block is None
                else np.atleast_1d(np.asarray(getattr(block, n), dtype=float))
            )
    return data


def decode_outputs(data: dict[str, np.ndarray]) -> AeroResults:
    """The results from the named arrays."""
    kwargs = {}
    for f in fields(AeroResults):
        if f.name == "imposed":
            continue
        array = np.asarray(data[f.name], dtype=float)
        kwargs[f.name] = float(array[0]) if "ndarray" not in str(f.type) else array
    imposed = {}
    for k in IMPOSED_KEYS:
        if data[f"imposed.{k}.vx_m_s"].size:
            block = {n: np.asarray(data[f"imposed.{k}.{n}"]) for n in IMPOSED_FIELDS}
            block["vx_m_s"] = float(block["vx_m_s"][0])
            imposed[k] = ImposedSpeed(**block)
    return AeroResults(**kwargs, imposed=imposed)


def _discipline_class():
    from gemseo.core.discipline import Discipline  # noqa: PLC0415

    class PredimRCDiscipline(Discipline):
        """One PredimRC evaluation; inputs and outputs named as in this module."""

        default_grammar_type = Discipline.GrammarType.SIMPLER

        def __init__(self, backend: AeroBackend, example: dict[str, np.ndarray]):
            """
            Args:
                backend: The backend evaluating the cache misses.
                example: Inputs giving the input names and types.
            """  # noqa: D205, D212
            super().__init__(name="PredimRC")
            self.backend = backend
            self.n_runs = 0
            self.input_grammar.update_from_data(example)
            self.output_grammar.update_from_names(output_names())

        def _run(self, input_data):
            self.n_runs += 1
            result = self.backend.evaluate(**decode_inputs(input_data))
            return encode_outputs(result)

    return PredimRCDiscipline


def workbook_key(profile: str, template_dir: str | Path) -> str:
    """HDF5 node of a workbook: profile, content hash of the file, cache version."""
    path = workbook_path(template_dir, profile)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{profile}_{digest}_v{CACHE_VERSION}"


class CachedBackend:
    """A PredimRC backend whose evaluations are stored in an HDF5 file.

    Args:
        backend: The backend evaluating the cache misses (Excel is only started by them
            with an ``ExcelThreadBackend``).
        cache_path: The HDF5 file.
        node: The node of the workbook (``workbook_key``).
    """

    def __init__(self, backend: AeroBackend, cache_path: str | Path, node: str) -> None:
        self.backend = backend
        self.cache_path = Path(cache_path)
        self.node = node
        self._discipline = None
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
        inputs = encode_inputs(wing, stab, fus, settings)
        with self._lock:
            if self._discipline is None:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._discipline = _discipline_class()(self.backend, inputs)
                self._discipline.set_cache(
                    self._discipline.CacheType.HDF5,
                    hdf_file_path=self.cache_path,
                    hdf_node_path=self.node,
                )
            n_before = self._discipline.n_runs
            data = self._discipline.execute(inputs)
            if self._discipline.n_runs > n_before:
                self.misses += 1
            else:
                self.hits += 1
        return decode_outputs({n: data[n] for n in output_names()})

    run = evaluate

    @property
    def last_eval_seconds(self) -> float:
        return getattr(self.backend, "last_eval_seconds", float("nan"))

    def is_alive(self) -> bool:
        is_alive = getattr(self.backend, "is_alive", None)
        return True if is_alive is None else is_alive()

    def close(self) -> None:
        self.backend.close()


def gemseo_available() -> bool:
    try:
        import gemseo  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


def open_backend(
    profile: str,
    template_dir: str | Path,
    cache_path: str | Path | None = None,
) -> AeroBackend:
    """The PredimRC backend of the tool: Excel in its own thread, behind the HDF5 cache.

    Args:
        profile: The wing airfoil.
        template_dir: The folder of the PredimRC workbooks.
        cache_path: The HDF5 file; the one of the settings by default.

    Returns:
        The backend (to close after use); without GEMSEO, the uncached Excel backend.
    """
    excel = ExcelThreadBackend(profile, template_dir)
    if not gemseo_available():
        LOGGER.info("GEMSEO not installed: PredimRC evaluations are not cached.")
        return excel
    return CachedBackend(
        excel, cache_path or default_cache_path(), workbook_key(profile, template_dir)
    )
