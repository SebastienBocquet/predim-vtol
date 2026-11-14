"""Model foundation: declarations, base classes and MIC Interface generation."""

from predim_vtol.core.model import REGISTRY
from predim_vtol.core.model import CompositeModel
from predim_vtol.core.model import Invariant
from predim_vtol.core.model import Model
from predim_vtol.core.model import Param
from predim_vtol.core.model import Port
from predim_vtol.core.model import ScalingLaw
from predim_vtol.core.model import params
from predim_vtol.core.model import ports

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
