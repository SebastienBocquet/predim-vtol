"""Base classes of all MVP models.

A model declares, at class level, its input and output ports, its parameters and the
relations it is expected to satisfy. ``evaluate`` is pure: a mapping of SI values in,
a mapping of SI values out, no state and no file I/O. numpy arrays are accepted for
vectorised evaluations.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from types import MappingProxyType
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping

Bounds = tuple[float | None, float | None]
"""Physical bounds ``(lower, upper)``; ``None`` means unbounded."""

_NO_DEFAULT = object()


@dataclass(frozen=True)
class Port:
    """An input or output of a model."""

    name: str
    """Name, with a unit suffix when ambiguous (e.g. ``torque_nm``)."""

    symbol: str
    """Mathematical symbol."""

    unit: str
    """SI unit, ``"—"`` when dimensionless."""

    description: str
    """Short description."""

    physical_bounds: Bounds = (None, None)
    """Physical bounds."""


@dataclass(frozen=True)
class Param:
    """A parameter of a model, describing the modelled component."""

    name: str
    """Name, with a unit suffix when ambiguous."""

    symbol: str
    """Mathematical symbol."""

    unit: str
    """SI unit, ``"—"`` when dimensionless."""

    description: str
    """Short description."""

    default: Any = _NO_DEFAULT
    """Default value, if any."""

    origin: str = ""
    """Where the value comes from when there is no default (e.g. ``"database"``)."""

    bounds: Bounds = (None, None)
    """Physical bounds."""

    source: str = ""
    """Source of the default value or of the data."""

    @property
    def has_default(self) -> bool:
        """Whether the parameter has a default value."""
        return self.default is not _NO_DEFAULT

    @property
    def default_or_origin(self) -> str:
        """The default value, or the origin of the value, as text."""
        return repr(self.default) if self.has_default else (self.origin or "required")


def ports(*items: Port) -> MappingProxyType:
    """Return an immutable name → port mapping."""
    return MappingProxyType({p.name: p for p in items})


def params(*items: Param) -> MappingProxyType:
    """Return an immutable name → parameter mapping."""
    return MappingProxyType({p.name: p for p in items})


def _check_bounds(name: str, value: Any, bounds: Bounds) -> None:
    lower, upper = bounds
    values = (
        np.atleast_1d(np.asarray(value, dtype=float)) if _is_numeric(value) else None
    )
    if values is None:
        return
    if lower is not None and np.any(values < lower):
        msg = f"{name} = {value} is below its physical lower bound {lower}."
        raise ValueError(msg)
    if upper is not None and np.any(values > upper):
        msg = f"{name} = {value} is above its physical upper bound {upper}."
        raise ValueError(msg)


def _is_numeric(value: Any) -> bool:
    try:
        np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class ScalingLaw:
    """An expected power law ``output ∝ input ** exponent``, other inputs fixed."""

    output: str
    input: str
    exponent: float
    fixed: Mapping[str, Any] = field(default_factory=dict)
    lower: float = 1.0
    upper: float = 10.0
    tol: float = 1e-6
    params: Mapping[str, Any] = field(default_factory=dict)
    """Parameter values used to build the model for the check."""

    def slope(self, model: Model) -> float:
        """Return the log-log slope of the output with respect to the input."""
        x = np.geomspace(self.lower, self.upper, 12)
        y = np.array([
            float(
                np.asarray(model.evaluate({**self.fixed, self.input: xi})[self.output])
            )
            for xi in x
        ])
        return float(np.polyfit(np.log(x), np.log(y), 1)[0])


@dataclass(frozen=True)
class Invariant:
    """An expected relation checked by a function of the model."""

    description: str
    check: Callable[[Model], bool]
    params: Mapping[str, Any] = field(default_factory=dict)
    """Parameter values used to build the model for the check."""


REGISTRY: dict[str, type[Model]] = {}
"""All concrete models, by MIC identifier; used by the generic tests."""


class Model(ABC):
    """Base class of all models.

    Args:
        **values: The parameter values; missing ones take their default.

    Raises:
        ValueError: When a parameter without default is missing, unknown or outside
            its physical bounds.
    """

    mic_id: ClassVar[str] = ""
    inputs: ClassVar[Mapping[str, Port]] = MappingProxyType({})
    outputs: ClassVar[Mapping[str, Port]] = MappingProxyType({})
    parameters: ClassVar[Mapping[str, Param]] = MappingProxyType({})
    expected_forms: ClassVar[list[ScalingLaw | Invariant]] = []
    check: bool = False
    """Check inputs and outputs against their physical bounds (debug, slower)."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # __abstractmethods__ is not yet computed here: test evaluate directly.
        if not getattr(cls.evaluate, "__isabstractmethod__", False):
            if not cls.mic_id:
                msg = f"{cls.__name__} must define mic_id to be registered."
                raise TypeError(msg)
            REGISTRY.setdefault(cls.mic_id, cls)

    def __init__(self, **values: Any) -> None:
        unknown = set(values) - set(self.parameters)
        if unknown:
            msg = f"{type(self).__name__}: unknown parameters {sorted(unknown)}."
            raise ValueError(msg)
        resolved = {}
        for name, param in self.parameters.items():
            if name in values:
                value = values[name]
            elif param.has_default:
                value = param.default
            else:
                msg = f"{type(self).__name__}: parameter '{name}' is required."
                raise ValueError(msg)
            _check_bounds(name, value, param.bounds)
            resolved[name] = value
        self.p = SimpleNamespace(**resolved)

    def __call__(self, x: Mapping[str, Any]) -> dict[str, Any]:
        """Evaluate, checking the bounds when ``check`` is true."""
        if self.check:
            self.check_io(x, None)
        y = self.evaluate(x)
        if self.check:
            self.check_io(None, y)
        return y

    @abstractmethod
    def evaluate(self, x: Mapping[str, Any]) -> dict[str, Any]:
        """Evaluate the model.

        Args:
            x: The input values (SI), by port name.

        Returns:
            The output values (SI), by port name.
        """

    def check_io(
        self, x: Mapping[str, Any] | None, y: Mapping[str, Any] | None
    ) -> None:
        """Check inputs and outputs against their physical bounds."""
        for values, declared in ((x, self.inputs), (y, self.outputs)):
            if values is None:
                continue
            for name, port in declared.items():
                if name in values:
                    _check_bounds(name, values[name], port.physical_bounds)

    @classmethod
    def describe(cls):
        """Return the Interface tables of the MIC card of the model."""
        from predimrc_wrapper.core.mic import MicInterface  # noqa: PLC0415

        return MicInterface.from_model(cls)


class CompositeModel(Model, ABC):
    """A model made of named sub-models with an explicit data flow.

    Args:
        submodels: The sub-models, by name.
        **values: The parameter values of the composite itself.
    """

    def __init__(
        self, submodels: Mapping[str, Model] | None = None, **values: Any
    ) -> None:
        super().__init__(**values)
        self.submodels = dict(submodels or {})
