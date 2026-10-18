"""Design parameters of a GEMSEO study: project paths, kinds and bounds (REQ-MDO-002)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal

from gemseo.algos.design_space import DesignSpace

from predimrc_wrapper.data import default_database


@dataclass(frozen=True)
class CategoricalMapping:
    """Integer index ↔ label mapping of a categorical parameter."""

    labels: tuple[str, ...]

    def index(self, label: str) -> int:
        return self.labels.index(label)

    def label(self, index: int) -> str:
        if not 0 <= index < len(self.labels):
            msg = f"Index {index} outside [0, {len(self.labels) - 1}] for {list(self.labels)}."
            raise ValueError(msg)
        return self.labels[index]


@dataclass(frozen=True)
class Parameter:
    """A design parameter bound to a project field.

    Args:
        name: The GEMSEO variable name.
        path: The dotted path in the project (``Project.with_overrides``).
        kind: ``float``, ``integer`` or ``categorical``.
        lower: The lower bound (float, integer).
        upper: The upper bound (float, integer).
        mapping: The labels (categorical).
    """

    name: str
    path: str
    kind: Literal["float", "integer", "categorical"] = "float"
    lower: float = 0.0
    upper: float = 1.0
    mapping: CategoricalMapping | None = field(default=None)

    def __post_init__(self) -> None:
        if self.kind == "categorical" and not self.mapping:
            msg = f"Categorical parameter '{self.name}' needs labels."
            raise ValueError(msg)

    def bounds(self) -> tuple[float, float]:
        if self.kind == "categorical":
            return 0, len(self.mapping.labels) - 1
        return self.lower, self.upper

    def to_project_value(self, x: Any) -> Any:
        """Convert a design value (array of size 1) to the project value."""
        value = float(x[0]) if hasattr(x, "__len__") else float(x)
        if self.kind == "float":
            return value
        index = round(value)
        return index if self.kind == "integer" else self.mapping.label(index)

    def to_design_value(self, value: Any) -> float:
        """Convert a project value to the design value."""
        if self.kind == "categorical":
            return float(self.mapping.index(value))
        return float(value)


def categorical(name: str, path: str, labels: list[str]) -> Parameter:
    """A categorical parameter over explicit labels."""
    return Parameter(
        name, path, "categorical", mapping=CategoricalMapping(tuple(labels))
    )


def from_database(name: str, path: str, role: str | None = None) -> Parameter:
    """A categorical parameter over the motor ids of the database."""
    return categorical(name, path, default_database().ids(role))


PROPELLER_SUFFIX = ".propeller"
"""Categorical path ``propulsion_units.<unit>.propeller``: a database propeller id."""


def expand_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    """Expand ``propulsion_units.<unit>.propeller`` into its id, diameter and pitch."""
    out = {}
    for path, value in overrides.items():
        if path.endswith(PROPELLER_SUFFIX):
            from predimrc_wrapper.data import default_propellers  # noqa: PLC0415

            base = path[: -len(PROPELLER_SUFFIX)]
            prop = default_propellers().propeller(value)
            out.update({
                f"{base}.propeller_id": prop.id,
                f"{base}.prop_diameter_in": prop.diameter_in,
                f"{base}.prop_pitch_in": prop.pitch_in,
            })
        else:
            out[path] = value
    return out


def current_choice(project: Any, path: str) -> Any:
    """Value of a categorical path in a project (the propeller id for ``.propeller`` paths)."""
    from predimrc_wrapper.mdo.discipline import _get_path  # noqa: PLC0415

    if path.endswith(PROPELLER_SUFFIX):
        return _get_path(project, path[: -len(PROPELLER_SUFFIX)] + ".propeller_id")
    return _get_path(project, path)


def build_design_space(
    parameters: list[Parameter], values: dict[str, float] | None = None
) -> DesignSpace:
    """Build the GEMSEO design space; categorical and integer parameters are integers."""
    space = DesignSpace()
    for p in parameters:
        lower, upper = p.bounds()
        kwargs = {"lower_bound": lower, "upper_bound": upper}
        if values and p.name in values:
            kwargs["value"] = values[p.name]
        space.add_variable(
            p.name, type_="float" if p.kind == "float" else "integer", **kwargs
        )
    return space
