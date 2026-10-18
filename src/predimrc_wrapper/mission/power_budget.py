"""Power budget: where the battery chemical power goes, per phase (REQ-MIS-009, MIC-MIS-BUDGET).

Post-processing of a ``TwoPhaseResult``, no new physics:

- useful aerodynamic power: hover, ideal induced power Σ T_i^1.5 / √(2ρA_i); cruise, Σ T_i·V
  (= D·V);
- motor: copper and no-load losses I²R_m + I₀·U_emf, U_emf = rpm / K_v (MIC-PROP-MOT); in
  cruise, motor input − shaft power;
- propeller: shaft − useful (hover shaft = motor input − motor losses);
- ESC, main / DC / phase cables, battery internal resistance: the segments of the power
  chain (MIC-PROP-CHAIN), the ESC loss included even when it is inside the test data;
- avionics.

The sinks add up to the chemical power (``closure_w`` ≈ 0). The multicopter cruise of the
forward-flight model (MIC-MIS-SEG) gives only the shaft and terminal powers: rotors in
forward flight (shaft − D·V: induced power to carry the weight, profile power), motors + ESC
+ cables together (terminal − shaft − avionics), battery internal (chemical − terminal).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.core.units import INCH

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import AircraftModel
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult
    from predimrc_wrapper.propulsion.chain import ChainResult

SINKS = (
    "useful aerodynamic",
    "propeller",
    "motor",
    "ESC",
    "main cable",
    "DC cables",
    "phase cables",
    "battery internal",
    "avionics",
    "rotors in forward flight",
    "motors, ESC and cables",
)
"""Order of the sinks, from the air back to the cells."""


@dataclass
class PhaseBudget:
    """Power sinks of one phase (W)."""

    phase: str
    chemical_w: float
    sinks: dict[str, float] = field(default_factory=dict)

    @property
    def closure_w(self) -> float:
        """Chemical power − Σ sinks (0 when the budget is complete)."""
        return self.chemical_w - sum(self.sinks.values())


def _chain_sinks(chain: ChainResult) -> dict[str, float]:
    out = dict.fromkeys(
        ("ESC", "main cable", "DC cables", "phase cables", "battery internal"), 0.0
    )
    for s in chain.segments:
        if s.name == "battery internal resistance":
            out["battery internal"] += s.loss_w
        elif s.name.startswith("main cable"):
            out["main cable"] += s.loss_w
        elif s.name.endswith(": ESC"):
            out["ESC"] += s.loss_w
        elif s.name.endswith(": DC cable"):
            out["DC cables"] += s.loss_w
        elif s.name.endswith(": phase cables"):
            out["phase cables"] += s.loss_w
        else:  # pragma: no cover - a new segment must be classified
            msg = f"unclassified chain segment {s.name!r}"
            raise ValueError(msg)
    return out


def _motor_loss(
    aircraft: AircraftModel, motor_id: str, current_a: float, rpm: float
) -> float:
    record = aircraft.db.motor(motor_id)
    return current_a**2 * record.r_m + record.i0 * rpm / record.kv


def power_budget(aircraft: AircraftModel, result: TwoPhaseResult) -> list[PhaseBudget]:
    """Budgets of the hover and of each target speed."""
    project = aircraft.project
    avionics = project.mission.avionics_power_w
    out = []

    h = result.hover
    useful = motor = 0.0
    for m in h.motors:
        diameter = project.propulsion_units[m.unit].prop_diameter_in * INCH
        area = np.pi * diameter**2 / 4.0
        useful += m.thrust_n**1.5 / np.sqrt(2.0 * aircraft.rho * area)
        motor += _motor_loss(aircraft, m.motor_id, m.motor_current_a, m.rpm)
    shaft = h.chain.motor_power_w - motor
    sinks = {
        "useful aerodynamic": useful,
        "propeller": shaft - useful,
        "motor": motor,
        **_chain_sinks(h.chain),
        "avionics": avionics,
    }
    out.append(PhaseBudget("hover", h.chain.chemical_power_w, sinks))

    for c in result.cruise:
        label = f"V{c.index}"
        if c.chain is None:
            sinks = {
                "useful aerodynamic": c.aero_power_w,
                "rotors in forward flight": c.shaft_power_w - c.aero_power_w,
                "motors, ESC and cables": c.terminal_power_w
                - c.shaft_power_w
                - avionics,
                "battery internal": c.battery_power_w - c.terminal_power_w,
                "avionics": avionics,
            }
            out.append(PhaseBudget(label, c.battery_power_w, sinks))
            continue
        useful = sum(m.thrust_n * c.v_m_s for m in c.motors)
        shaft = sum(m.shaft_power_w for m in c.motors)
        sinks = {
            "useful aerodynamic": useful,
            "propeller": shaft - useful,
            "motor": c.chain.motor_power_w - shaft,
            **_chain_sinks(c.chain),
            "avionics": avionics,
        }
        out.append(PhaseBudget(label, c.chain.chemical_power_w, sinks))
    return out


def budget_rows(budgets: list[PhaseBudget]) -> list[dict]:
    """One row per sink, one column of power per phase, plus the share of the chemical power."""
    rows = []
    for sink in SINKS:
        if not any(sink in b.sinks for b in budgets):
            continue
        row = {"power sink": sink}
        for b in budgets:
            value = b.sinks.get(sink)
            row[f"{b.phase} (W)"] = None if value is None else round(float(value), 1)
            row[f"{b.phase} (%)"] = (
                None if value is None else round(float(100 * value / b.chemical_w), 1)
            )
        rows.append(row)
    total = {"power sink": "battery chemical power (total)"}
    for b in budgets:
        total[f"{b.phase} (W)"] = round(float(b.chemical_w), 1)
        total[f"{b.phase} (%)"] = 100.0
    rows.append(total)
    return rows
