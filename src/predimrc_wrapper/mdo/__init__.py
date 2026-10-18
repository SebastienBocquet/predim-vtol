"""GEMSEO integration (MVP-006). Requires the ``[mdo]`` extra."""

try:
    import gemseo  # noqa: F401
except ModuleNotFoundError as error:  # pragma: no cover
    msg = "predimrc_wrapper.mdo needs GEMSEO: pip install 'predimrc_wrapper[mdo]'."
    raise ImportError(msg) from error

from predimrc_wrapper.mdo.discipline import OUTPUTS
from predimrc_wrapper.mdo.discipline import PresizingDiscipline
from predimrc_wrapper.mdo.parameters import CategoricalMapping
from predimrc_wrapper.mdo.parameters import Parameter
from predimrc_wrapper.mdo.parameters import build_design_space
from predimrc_wrapper.mdo.parameters import categorical
from predimrc_wrapper.mdo.parameters import from_database

__all__ = [
    "OUTPUTS",
    "CategoricalMapping",
    "Parameter",
    "PresizingDiscipline",
    "build_design_space",
    "categorical",
    "from_database",
]
