"""Model foundation: declarations, base classes and MIC Interface generation."""

from predimrc_wrapper.core.model import REGISTRY
from predimrc_wrapper.core.model import CompositeModel
from predimrc_wrapper.core.model import Invariant
from predimrc_wrapper.core.model import Model
from predimrc_wrapper.core.model import Param
from predimrc_wrapper.core.model import Port
from predimrc_wrapper.core.model import ScalingLaw
from predimrc_wrapper.core.model import params
from predimrc_wrapper.core.model import ports

__all__ = [
    "REGISTRY",
    "CompositeModel",
    "Invariant",
    "Model",
    "Param",
    "Port",
    "ScalingLaw",
    "params",
    "ports",
]
