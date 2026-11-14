"""GEMSEO integration (MVP-006). Requires the ``[mdo]`` extra."""

try:
    import gemseo  # ruff: ignore[unused-import]
except ModuleNotFoundError as error:  # pragma: no cover
    msg = "predim_vtol.mdo needs GEMSEO: pip install 'predim_vtol[mdo]'."
    raise ImportError(msg) from error

from predim_vtol.mdo.discipline import OUTPUTS
from predim_vtol.mdo.discipline import PresizingDiscipline
from predim_vtol.mdo.parameters import CategoricalMapping
from predim_vtol.mdo.parameters import Parameter
from predim_vtol.mdo.parameters import build_design_space
from predim_vtol.mdo.parameters import categorical
from predim_vtol.mdo.parameters import from_database

__all__ = [
    "OUTPUTS",
    "CategoricalMapping",
    "Parameter",
    "PresizingDiscipline",
    "build_design_space",
    "categorical",
    "from_database",
]
