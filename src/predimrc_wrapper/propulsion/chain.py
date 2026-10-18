"""Power chain battery – main cable – DC branches – ESCs – phase cables – motors (MIC-PROP-CHAIN).

Per motor i, from the motor side: P_esc,out = P_m + I_m²·2R_phase (DC-equivalent, two
phases conducting, I_m the motor current); P_esc,in = P_esc,out / η_esc; I_dc = P_esc,in
/ U_bus; P_branch = P_esc,in + I_dc²·2R_dc. Bus: P_bus = Σ P_branch + P_av; main cable and
connector: I = P_bus / U_bus, loss I²·(2R_main + R_conn); battery terminal power P_t =
P_bus + main loss; battery internal loss from MIC-PROP-BAT. U_bus = U_t − I·(2R_main +
R_conn), solved by fixed point. Data measured at the ESC input (``esc_input``): P_esc,in
= P_data + phase loss / η_esc, the ESC loss (1 − η_esc)·P_esc,in being inside the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.propulsion.wiring import awg_for_current
from predimrc_wrapper.propulsion.wiring import default_layout
from predimrc_wrapper.propulsion.wiring import resistance_ohm

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.project import Project
    from predimrc_wrapper.propulsion.battery import BatteryModel


@dataclass
class SegmentLoss:
    """One segment of the chain at one operating point."""

    name: str
    power_in_w: float
    loss_w: float
    model: str
    in_data: bool = False
    """The loss is inside the thrust–power data (shown, not added)."""

    @property
    def efficiency(self) -> float:
        return 1.0 - self.loss_w / self.power_in_w if self.power_in_w > 0 else float("nan")


@dataclass
class ChainResult:
    """Losses of the chain at one operating point."""

    segments: list[SegmentLoss]
    battery_power_w: float
    """Power at the battery terminals (W)."""
    chemical_power_w: float
    battery_current_a: float
    battery_voltage_v: float
    bus_voltage_v: float
    motor_power_w: float
    """Σ power at the motor inputs (W)."""
    feasible: bool
    branch_currents_a: list[float] = field(default_factory=list)

    @property
    def total_loss_w(self) -> float:
        return sum(s.loss_w for s in self.segments if not s.in_data)

    @property
    def efficiency(self) -> float:
        """Σ motor input power / chemical power."""
        return self.motor_power_w / self.chemical_power_w if self.chemical_power_w > 0 else float("nan")


@dataclass
class BranchSpec:
    """Cables and ESC of one motor, resolved (lengths, gauges, efficiency)."""

    name: str
    dc_length_mm: float
    dc_awg: int
    phase_length_mm: float
    phase_awg: int
    esc_efficiency: float
    four_in_one: bool = False


class PowerChain(Model):
    """Losses of the power chain, from the motor powers and currents to the battery.

    See the module docstring for the equations.
    """

    mic_id = "MIC-PROP-CHAIN"
    inputs = ports(
        Port("motor_power_w", "P_m,i", "W", "electric power at each motor input (or at each ESC input for esc_input data)", (0, None)),
        Port("motor_current_a", "I_m,i", "A", "motor (phase-side) current of each motor", (0, None)),
        Port("esc_input", "—", "—", "per motor: the power is measured at the ESC input"),
        Port("avionics_power_w", "P_av", "W", "avionics and payload power on the bus", (0, None)),
    )
    outputs = ports(
        Port("result", "—", "—", "ChainResult: segments, battery power, voltages, currents"),
    )
    parameters = params(
        Param("branches", "—", "—", "per motor: cable lengths and gauges, ESC efficiency", origin="project wiring + geometry", source="project"),
        Param("main_length_mm", "L_main", "mm", "main cable length, battery rear → distribution", origin="geometry", bounds=(0, None), source="project"),
        Param("main_awg", "—", "AWG", "main cable gauge", origin="project or current", source="project"),
        Param("connector_mohm", "R_conn", "mΩ", "battery connector resistance", default=0.5, bounds=(0, None), source="XT60-class connector, generic"),
        Param("wire_temperature_c", "T_w", "°C", "wire temperature", default=40.0, source="generic"),
        Param("battery", "—", "—", "battery model (MIC-PROP-BAT)", origin="project", source="project"),
    )
    expected_forms: list = []  # set after the class

    @classmethod
    def from_project(cls, project: Project, battery: BatteryModel, hover_currents_a: list[float] | None = None) -> PowerChain:
        """Chain of a project; gauges not entered are chosen from the hover currents (default 10 A)."""
        from predimrc_wrapper.aircraft.project import WiringSpec  # noqa: PLC0415

        spec = project.wiring or WiringSpec()
        layout = default_layout(project)
        overrides = {o.motor_index: o for o in spec.overrides}
        currents = hover_currents_a or [10.0] * len(project.motors)
        four_in_one = spec.lift_esc == "four_in_one"
        branches = []
        for b, m, current in zip(layout.branches, project.motors, currents):
            o = overrides.get(b.motor_index)
            dc = o.dc_length_mm if (o and o.dc_length_mm is not None) else b.dc_length_mm
            phase = o.phase_length_mm if (o and o.phase_length_mm is not None) else b.phase_length_mm
            branches.append(BranchSpec(
                name=f"motor {b.motor_index + 1} ({m.unit})", dc_length_mm=dc,
                dc_awg=spec.dc_awg or awg_for_current(current), phase_length_mm=phase,
                phase_awg=spec.phase_awg or awg_for_current(current),
                esc_efficiency=project.propulsion_units[m.unit].esc_efficiency,
                four_in_one=four_in_one and m.role != "cruise"))
        return cls(branches=branches, main_length_mm=layout.main_length_mm,
                   main_awg=spec.main_awg or awg_for_current(sum(currents)),
                   connector_mohm=spec.connector_mohm, wire_temperature_c=spec.wire_temperature_c, battery=battery)

    def _r(self, length_mm: float, awg: int) -> float:
        return resistance_ohm(length_mm, awg, self.p.wire_temperature_c)

    def evaluate(self, x):
        p_m = [float(v) for v in x["motor_power_w"]]
        i_m = [float(v) for v in x["motor_current_a"]]
        esc_input = list(x.get("esc_input") or [False] * len(p_m))
        p_av = float(x.get("avionics_power_w", 0.0))
        battery = self.p.battery
        r_main = 2.0 * self._r(self.p.main_length_mm, self.p.main_awg) + self.p.connector_mohm / 1000.0
        u_bus = battery.open_circuit_voltage
        for _ in range(30):
            segments, p_bus, dc_currents = [], p_av, []
            for b, p, i, at_esc in zip(self.p.branches, p_m, i_m, esc_input):
                phase_loss = i**2 * 2.0 * self._r(b.phase_length_mm, b.phase_awg)
                if at_esc:
                    p_esc_in = p + phase_loss / b.esc_efficiency
                else:
                    p_esc_in = (p + phase_loss) / b.esc_efficiency
                i_dc = p_esc_in / u_bus
                dc_loss = i_dc**2 * 2.0 * self._r(b.dc_length_mm, b.dc_awg)
                dc_currents.append(i_dc)
                segments += [
                    SegmentLoss(f"{b.name}: DC cable", p_esc_in + dc_loss, dc_loss,
                                f"2·ρL/A·I², {b.dc_length_mm:.0f} mm AWG{b.dc_awg}"),
                    SegmentLoss(f"{b.name}: ESC", p_esc_in, (1 - b.esc_efficiency) * p_esc_in,
                                f"constant efficiency {b.esc_efficiency:.2f} (MVP)", in_data=at_esc),
                    SegmentLoss(f"{b.name}: phase cables", p_esc_in * b.esc_efficiency, phase_loss,
                                f"2·ρL/A·I_m², {b.phase_length_mm:.0f} mm AWG{b.phase_awg}"),
                ]
                p_bus += p_esc_in + dc_loss
            current = p_bus / u_bus
            main_loss = current**2 * r_main
            p_t = p_bus + main_loss
            bat = battery.evaluate({"power_w": p_t})
            u_t = float(bat["voltage_v"]) if np.isfinite(bat["voltage_v"]) else battery.open_circuit_voltage
            new_bus = u_t - float(bat["current_a"]) * r_main if np.isfinite(bat["current_a"]) else u_t
            if abs(new_bus - u_bus) < 1e-10 * u_bus:
                u_bus = new_bus
                break
            u_bus = new_bus
        i_bat = float(bat["current_a"])
        chemical = float(bat["chemical_power_w"])
        head = [
            SegmentLoss("battery internal resistance", chemical, chemical - p_t, "R_bat·I², MIC-PROP-BAT"),
            SegmentLoss("main cable and connector", p_t, main_loss,
                        f"(2·ρL/A + R_conn)·I², {self.p.main_length_mm:.0f} mm AWG{self.p.main_awg}"),
        ]
        motor_power = sum(p if not at else p * b.esc_efficiency for p, at, b in zip(p_m, esc_input, self.p.branches))
        return {"result": ChainResult(head + segments, p_t, chemical, i_bat, u_t, u_bus, motor_power,
                                      bool(bat["feasible"]), dc_currents)}


def _losses_close(_: PowerChain) -> bool:
    """Chemical power = Σ losses + Σ motor powers + avionics."""
    from predimrc_wrapper.propulsion.battery import BatteryModel  # noqa: PLC0415

    chain = PowerChain(branches=[BranchSpec("m", 300.0, 16, 400.0, 16, 0.95)] * 3, main_length_mm=150.0, main_awg=12,
                       battery=BatteryModel.from_mass("lipo", 4, 0.45))
    r = chain.evaluate({"motor_power_w": [90.0, 90.0, 100.0], "motor_current_a": [12.0, 12.0, 13.0],
                        "avionics_power_w": 5.0})["result"]
    return bool(np.isclose(r.chemical_power_w, r.total_loss_w + r.motor_power_w + 5.0, rtol=1e-9))


def _zero_length_no_loss(_: PowerChain) -> bool:
    from predimrc_wrapper.propulsion.battery import BatteryModel  # noqa: PLC0415

    chain = PowerChain(branches=[BranchSpec("m", 0.0, 16, 0.0, 16, 1.0)], main_length_mm=0.0, main_awg=12,
                       connector_mohm=0.0, battery=BatteryModel.from_mass("lipo", 4, 0.45, r_cell_ohm_ah=0.0))
    r = chain.evaluate({"motor_power_w": [100.0], "motor_current_a": [12.0]})["result"]
    return bool(abs(r.total_loss_w) < 1e-12 and np.isclose(r.battery_power_w, 100.0))


def _example() -> dict:
    from predimrc_wrapper.propulsion.battery import BatteryModel  # noqa: PLC0415

    return {"branches": [BranchSpec("m", 300.0, 16, 400.0, 16, 0.95)], "main_length_mm": 150.0, "main_awg": 12,
            "battery": BatteryModel.from_mass("lipo", 4, 0.45)}


PowerChain.expected_forms = [
    Invariant("chemical power = losses + motor powers + avionics", _losses_close, params=_example()),
    Invariant("zero lengths, ideal ESC and battery ⇒ no loss", _zero_length_no_loss, params=_example()),
]
