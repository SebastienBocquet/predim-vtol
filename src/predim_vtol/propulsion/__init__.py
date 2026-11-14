"""Propulsion models of the MVP (MVP-003)."""

from predim_vtol.propulsion.atmosphere import AtmosphereISA
from predim_vtol.propulsion.atmosphere import density
from predim_vtol.propulsion.battery import CHEMISTRIES
from predim_vtol.propulsion.battery import BatteryModel
from predim_vtol.propulsion.chain import PowerChain
from predim_vtol.propulsion.motor import MotorModel
from predim_vtol.propulsion.propeller import BladeElementPropeller
from predim_vtol.propulsion.propeller import MomentumPropeller
from predim_vtol.propulsion.surrogate import ThrustPowerSurrogate
from predim_vtol.propulsion.unit import PropulsionUnit

__all__ = [
    "CHEMISTRIES",
    "AtmosphereISA",
    "BatteryModel",
    "BladeElementPropeller",
    "MomentumPropeller",
    "MotorModel",
    "PowerChain",
    "PropulsionUnit",
    "ThrustPowerSurrogate",
    "density",
]
