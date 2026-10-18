"""Mission integration, optimal speeds and margins (MIC-MIS-SOL, MVP variant)."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from predimrc_wrapper.core import CompositeModel
from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.mission.powers import VERTICAL
from predimrc_wrapper.mission.powers import SegmentPower

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft.model import AircraftModel
    from predimrc_wrapper.mission.scenario import Scenario

MULTICOPTER_V_MIN = 1.0
"""Lowest cruise speed swept for a multicopter (m/s)."""

MULTICOPTER_V_MAX = 40.0
"""Highest cruise speed swept for a multicopter (m/s)."""


@dataclass
class SpeedSweep:
    """Cruise battery power versus speed."""

    v_m_s: np.ndarray
    battery_power_w: np.ndarray
    feasible: np.ndarray
    v_endurance: float
    v_range: float
    drag_n: np.ndarray | None = None
    """Total drag (N)."""
    shaft_power_w: np.ndarray | None = None
    """Total shaft power of the running propellers (W)."""

    @property
    def aero_power_w(self) -> np.ndarray | None:
        """Aerodynamic power D·V (W)."""
        return None if self.drag_n is None else np.asarray(self.drag_n) * np.asarray(self.v_m_s)


@dataclass
class SegmentResult:
    """Result of one segment."""

    kind: str
    duration_s: float
    distance_m: float
    speed_m_s: float
    battery_power_w: float
    battery_current_a: float
    energy_j: float
    feasible: bool
    limiting: str


@dataclass
class MissionResult:
    """Outputs of interest of one scenario."""

    scenario: str
    feasible: bool
    limiting: str
    flight_time_s: float
    range_m: float
    energy_used_j: float
    energy_available_j: float
    energy_reserve_j: float
    segments: list[SegmentResult]
    cruise_sweep: SpeedSweep
    margins: dict[str, float]
    mass_total_kg: float
    mass_breakdown: dict[str, float]
    defaults_left: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def flight_time_min(self) -> float:
        return self.flight_time_s / 60.0

    @property
    def range_km(self) -> float:
        return self.range_m / 1000.0

    @property
    def v_endurance(self) -> float:
        return self.cruise_sweep.v_endurance

    @property
    def v_range(self) -> float:
        return self.cruise_sweep.v_range

    def to_dict(self) -> dict[str, Any]:
        """Plain data, numpy arrays converted to lists."""
        data = asdict(self)
        sweep = data["cruise_sweep"]
        for key in ("v_m_s", "battery_power_w", "feasible", "drag_n", "shaft_power_w"):
            if sweep[key] is not None:
                sweep[key] = np.asarray(sweep[key]).tolist()
        return data


def _parabolic_min(v: np.ndarray, f: np.ndarray, i: int) -> float:
    """Refine a grid minimum with the parabola through its neighbours."""
    if 0 < i < len(v) - 1 and np.all(np.isfinite(f[i - 1:i + 2])):
        x0, x1, x2 = v[i - 1:i + 2]
        y0, y1, y2 = f[i - 1:i + 2]
        denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
        a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
        b = (x2**2 * (y0 - y1) + x1**2 * (y2 - y0) + x0**2 * (y1 - y2)) / denom
        if a > 0:
            return float(np.clip(-b / (2 * a), x0, x2))
    return float(v[i])


def _energy_additivity(_: MissionSolver) -> bool:
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.aircraft import Project  # noqa: PLC0415

    project = Project.template("multicopter")
    solver = MissionSolver(AircraftModel(project))
    result = solver.solve(project.scenarios["hover_90s"], "hover_90s")
    total = sum(s.energy_j for s in result.segments)
    return (abs(total - result.energy_used_j) <= 1e-9 * total
            and abs(result.energy_used_j - result.energy_available_j) <= 1e-6 * total)


class MissionSolver(CompositeModel):
    """Integrate a scenario.

    E_k = P_c,k·t_k; available energy E_u·(1 − r); an until-reserve segment lasts
    (E_avail − ΣE_others)/P_c. Sweep V ∈ [k_s·V_min; V_max]: V_e = argmin P_b,
    V_r = argmin P_b/V, parabolic refinement. Margins are worst cases over segments.

    Args:
        aircraft: The aircraft model.
        **values: The parameters.
    """

    mic_id = "MIC-MIS-SOL"
    inputs = ports(
        Port("scenario", "—", "—", "list of segments"),
        Port("scenario_name", "—", "—", "name of the scenario"),
    )
    outputs = ports(
        Port("flight_time_s", "t", "s", "total flight time", (0, None)),
        Port("range_m", "x", "m", "distance flown", (0, None)),
        Port("v_endurance", "V_e", "m/s", "best-endurance speed", (0, None)),
        Port("v_range", "V_r", "m/s", "best-range speed", (0, None)),
        Port("margins", "—", "—", "motor current, motor power, voltage, battery C, thrust-to-weight, mass"),
        Port("feasible", "—", "—", "scenario feasible with the reserve"),
        Port("result", "—", "—", "full MissionResult (per-segment table, sweep, mass)"),
    )
    parameters = params(
        Param("reserve_fraction", "r", "—", "energy reserve", default=0.20, bounds=(0, 0.5), source="practice"),
        Param("stall_margin", "k_s", "—", "minimum cruise speed / minimum polar speed", default=1.2, bounds=(1, None), source="practice"),
        Param("speed_step", "ΔV", "m/s", "speed sweep step", default=0.25, bounds=(0, None), source="numerical"),
        Param("min_thrust_to_weight", "T/W_min", "—", "minimum lift thrust-to-weight", default=1.5, bounds=(1, None), source="control authority practice"),
    )
    expected_forms = [Invariant("energy additivity and reserve left exactly", _energy_additivity)]

    def __init__(self, aircraft: AircraftModel | None = None, **values: Any) -> None:
        if aircraft is not None:
            m = aircraft.project.mission
            values = {"reserve_fraction": m.reserve_fraction, "stall_margin": m.stall_margin,
                      "speed_step": m.speed_step, "min_thrust_to_weight": m.min_thrust_to_weight, **values}
        segment_power = SegmentPower(aircraft) if aircraft is not None else None
        super().__init__({"segments": segment_power} if segment_power else {}, **values)
        self.aircraft = aircraft

    @property
    def power(self) -> SegmentPower:
        return self.submodels["segments"]

    def cruise_sweep(self) -> SpeedSweep:
        """Battery power versus cruise speed and the two optimal speeds."""
        ac = self.aircraft
        if ac.wing_borne:
            lo = self.p.stall_margin * ac.drag(1.0)["v_min_m_s"]
            polar = ac.aero.polar(ac.total_mass_kg)
            hi = float(polar.v_m_s[-1] * np.sqrt(polar.rho / ac.rho))
        else:
            lo, hi = MULTICOPTER_V_MIN, MULTICOPTER_V_MAX
        v = np.arange(lo, hi + 1e-9, self.p.speed_step)
        y = self.power.evaluate({"kind": "cruise", "v_m_s": v})
        p = np.asarray(y["battery_power_w"], dtype=float)
        ok = np.asarray(y["feasible"], dtype=bool) & np.isfinite(p)
        extra = {"drag_n": np.asarray(ac.drag(v)["drag_n"], dtype=float),
                 "shaft_power_w": np.broadcast_to(np.asarray(y["shaft_power_w"], dtype=float), v.shape).copy()}
        if not ok.any():
            return SpeedSweep(v, p, ok, float("nan"), float("nan"), **extra)
        masked = np.where(ok, p, np.inf)
        per_m = np.where(ok, p / v, np.inf)
        i_e, i_r = int(np.argmin(masked)), int(np.argmin(per_m))
        return SpeedSweep(v, p, ok, _parabolic_min(v, masked, i_e), _parabolic_min(v, per_m, i_r), **extra)

    def _speed(self, segment, sweep: SpeedSweep) -> float:
        if segment.speed == "optimal_endurance":
            return sweep.v_endurance
        if segment.speed == "optimal_range":
            return sweep.v_range
        return float(segment.speed)

    def solve(self, scenario: Scenario, name: str = "scenario") -> MissionResult:
        """Integrate a scenario."""
        ac = self.aircraft
        sweep = self.cruise_sweep()
        rows: list[dict] = []
        for seg in scenario.segments:
            v = self._speed(seg, sweep) if seg.kind in ("cruise", "loiter") else 0.0
            if seg.kind in ("cruise", "loiter") and not np.isfinite(v):
                y = {"battery_power_w": np.nan, "battery_current_a": np.nan, "chemical_power_w": np.nan,
                     "margins": {}, "feasible": False, "limiting": "no_feasible_speed"}
            else:
                y = self.power.evaluate({"kind": seg.kind, "v_m_s": v})
            if seg.until_reserve:
                duration = None
            elif seg.kind in VERTICAL and seg.kind != "hover":
                duration = abs(seg.altitude_change_m) / seg.vertical_speed_m_s
            elif seg.kind == "cruise":
                duration = seg.distance_m / v if v > 0 else np.nan
            else:
                duration = seg.duration_s
            rows.append({"seg": seg, "v": v, "y": y, "duration": duration})

        available = ac.battery.usable_energy_j() * (1.0 - self.p.reserve_fraction)
        fixed = sum(float(r["y"]["chemical_power_w"]) * r["duration"] for r in rows if r["duration"] is not None)
        segments, feasible, limiting = [], True, ""
        for r in rows:
            p_c = float(r["y"]["chemical_power_w"])
            if r["duration"] is None:
                r["duration"] = max(0.0, (available - fixed) / p_c) if p_c > 0 else 0.0
                if available - fixed < 0:
                    feasible, limiting = False, limiting or "energy"
            seg_ok = bool(r["y"]["feasible"]) and np.isfinite(r["duration"])
            if not seg_ok and feasible:
                feasible, limiting = False, f"{r['seg'].kind}:{r['y']['limiting']}"
            segments.append(SegmentResult(
                kind=r["seg"].kind, duration_s=float(r["duration"]), speed_m_s=float(r["v"]),
                distance_m=float(r["v"] * r["duration"]) if r["seg"].kind in ("cruise", "loiter") else 0.0,
                battery_power_w=float(r["y"]["battery_power_w"]),
                battery_current_a=float(r["y"]["battery_current_a"]),
                energy_j=p_c * float(r["duration"]), feasible=seg_ok, limiting=str(r["y"]["limiting"]),
            ))
        used = sum(s.energy_j for s in segments)
        if used > available * (1 + 1e-9):
            feasible, limiting = False, limiting or "energy"

        margins = {}
        for key in ("motor_current", "motor_power", "voltage", "battery_c"):
            values = [float(r["y"]["margins"][key]) for r in rows if key in r["y"]["margins"]]
            margins[key] = min(values) if values else float("nan")
        margins["thrust_to_weight"] = self.power.lift_thrust_to_weight() / self.p.min_thrust_to_weight - 1.0
        margins["mass"] = float(ac.mass["margin_mass"])
        if margins["thrust_to_weight"] < 0 and feasible:
            feasible, limiting = False, "thrust_to_weight"

        from predimrc_wrapper import __version__  # noqa: PLC0415
        from predimrc_wrapper.aircraft.project import defaults_left  # noqa: PLC0415

        return MissionResult(
            scenario=name, feasible=feasible, limiting=limiting,
            flight_time_s=sum(s.duration_s for s in segments),
            range_m=sum(s.distance_m for s in segments),
            energy_used_j=used, energy_available_j=available,
            energy_reserve_j=ac.battery.usable_energy_j() - used,
            segments=segments, cruise_sweep=sweep, margins=margins,
            mass_total_kg=ac.total_mass_kg, mass_breakdown=dict(ac.mass["breakdown"]),
            defaults_left=defaults_left(ac.project),
            metadata={"tool_version": __version__, "project": ac.project.name, "scenario": name},
        )

    def evaluate(self, x):
        result = self.solve(x["scenario"], x.get("scenario_name", "scenario"))
        return {"flight_time_s": result.flight_time_s, "range_m": result.range_m,
                "v_endurance": result.v_endurance, "v_range": result.v_range,
                "margins": result.margins, "feasible": result.feasible, "result": result}
