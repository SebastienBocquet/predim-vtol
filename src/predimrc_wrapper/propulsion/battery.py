"""Battery pack, specific-energy and internal-resistance model (MIC-PROP-BAT)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

import numpy as np

from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports


@dataclass(frozen=True)
class Chemistry:
    """Default values of a cell chemistry (pack level)."""

    specific_energy_wh_kg: float
    v_full: float
    v_nominal: float
    v_cutoff: float
    r_cell_ohm_ah: float
    c_max: float
    usable_fraction: float
    ocv_shape: tuple[tuple[float, float], ...]
    """(SoC, y) points of the open-circuit cell voltage V_c + y·(V_f − V_c)."""
    r_low_soc_factor: float


SOC_KNEE = 0.2
"""State of charge below which the internal resistance grows (linearly to its factor at 0)."""

CHEMISTRIES: dict[str, Chemistry] = {
    # Generic data-sheet values, to be confirmed (see MIC-PROP-BAT). Open-circuit curves:
    # LiPo 3.30 → 4.20 V with its plateau near 3.75–3.85 V; Li-ion (NMC) 2.8 → 4.2 V, more
    # sloped.
    "lipo": Chemistry(
        150.0,
        4.2,
        3.7,
        3.3,
        0.010,
        30.0,
        0.85,
        (
            (0.0, 0.0),
            (0.05, 0.278),
            (0.1, 0.422),
            (0.2, 0.489),
            (0.3, 0.533),
            (0.4, 0.567),
            (0.5, 0.6),
            (0.6, 0.644),
            (0.7, 0.711),
            (0.8, 0.789),
            (0.9, 0.878),
            (1.0, 1.0),
        ),
        1.5,
    ),
    "li-ion": Chemistry(
        200.0,
        4.2,
        3.6,
        2.8,
        0.040,
        8.0,
        0.90,
        (
            (0.0, 0.0),
            (0.05, 0.286),
            (0.1, 0.393),
            (0.2, 0.479),
            (0.3, 0.543),
            (0.4, 0.586),
            (0.5, 0.629),
            (0.6, 0.686),
            (0.7, 0.75),
            (0.8, 0.821),
            (0.9, 0.9),
            (1.0, 1.0),
        ),
        1.5,
    ),
}


@dataclass
class DischargeProfile:
    """Battery state along a flight of piecewise-constant terminal powers."""

    time_s: list[float] = field(default_factory=list)
    soc: list[float] = field(default_factory=list)
    """State of charge: 1 − chemical energy drawn / nominal energy."""
    ocv_v: list[float] = field(default_factory=list)
    """Open-circuit pack voltage (V)."""
    voltage_v: list[float] = field(default_factory=list)
    """Terminal pack voltage under load (V)."""
    current_a: list[float] = field(default_factory=list)
    segment_end: list[int] = field(default_factory=list)
    """Index of the last sample of each segment."""
    names: list[str] = field(default_factory=list)
    """Segment names."""


class BatteryModel(Model):
    """Battery pack.

    C = m_b·e / (n_s·V_n) or given; E = n_s·V_n·C; R = n_s·r / C; V₀ = n_s·V_n.
    The current for a terminal power P solves R·I² − V₀·I + P = 0 (smallest root;
    infeasible when P > V₀²/4R). The chemical power V₀·I includes the Joule losses.
    With a state of charge s (energy-based: s = 1 − E_drawn / E): V₀(s) = n_s·(V_c +
    y(s)·(V_f − V_c)), y the curve of the chemistry, and R(s) = R·(1 + (k_R − 1)·max(0,
    (s_k − s) / s_k)), s_k = 0.2; without s, V₀ = n_s·V_n and R (nominal).
    """

    mic_id = "MIC-PROP-BAT"
    inputs = ports(
        Port("power_w", "P", "W", "terminal power demanded", (0, None)),
        Port(
            "soc",
            "s",
            "—",
            "state of charge (optional; nominal voltage without)",
            (0, 1),
        ),
    )
    outputs = ports(
        Port("current_a", "I", "A", "pack current", (0, None)),
        Port("voltage_v", "U", "V", "terminal voltage under load", (0, None)),
        Port(
            "chemical_power_w",
            "P_c",
            "W",
            "power drawn from the cells, losses included",
            (0, None),
        ),
        Port("c_rate_margin", "—", "—", "1 − I / I_max"),
        Port("feasible", "—", "—", "false when P > V₀² / 4R"),
        Port("cutoff_ok", "—", "—", "terminal cell voltage U / n_s ≥ V_c"),
    )
    parameters = params(
        Param(
            "chemistry",
            "—",
            "—",
            "cell chemistry: lipo or li-ion",
            origin="project",
            source="project",
        ),
        Param(
            "n_series",
            "n_s",
            "—",
            "cells in series",
            origin="project",
            bounds=(1, 14),
            source="project",
        ),
        Param(
            "n_parallel",
            "n_p",
            "—",
            "cells in parallel",
            default=1,
            bounds=(1, 10),
            source="project",
        ),
        Param(
            "capacity_ah",
            "C",
            "Ah",
            "pack capacity (given or derived from mass)",
            origin="project",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "mass_kg",
            "m_b",
            "kg",
            "pack mass (given or derived from capacity)",
            origin="project",
            bounds=(0, None),
            source="project",
        ),
        Param(
            "specific_energy_wh_kg",
            "e",
            "Wh/kg",
            "pack-level specific energy",
            origin="chemistry table (150 LiPo / 200 Li-ion)",
            bounds=(0, None),
            source="generic data sheets, to confirm",
        ),
        Param(
            "v_full",
            "V_f",
            "V",
            "full cell voltage",
            origin="chemistry table (4.2 / 4.2)",
            bounds=(0, None),
            source="cell data sheets",
        ),
        Param(
            "v_nominal",
            "V_n",
            "V",
            "nominal cell voltage",
            origin="chemistry table (3.7 / 3.6)",
            bounds=(0, None),
            source="cell data sheets",
        ),
        Param(
            "v_cutoff",
            "V_c",
            "V",
            "cut-off cell voltage",
            origin="chemistry table (3.3 / 2.8)",
            bounds=(0, None),
            source="cell data sheets",
        ),
        Param(
            "r_cell_ohm_ah",
            "r",
            "Ω·Ah",
            "cell resistance × capacity",
            origin="chemistry table (0.010 / 0.040)",
            bounds=(0, None),
            source="generic, to confirm",
        ),
        Param(
            "c_max",
            "c_max",
            "C",
            "maximum continuous discharge rate",
            origin="chemistry table (30 / 8)",
            bounds=(0, None),
            source="generic data sheets",
        ),
        Param(
            "usable_fraction",
            "f_u",
            "—",
            "usable fraction of the capacity",
            origin="chemistry table (0.85 / 0.90)",
            bounds=(0, 1),
            source="engineering practice",
        ),
        Param(
            "ocv_shape",
            "y(s)",
            "—",
            "open-circuit cell voltage (V − V_c)/(V_f − V_c) versus state of charge",
            origin="chemistry table",
            source="generic discharge curves, to confirm",
        ),
        Param(
            "r_low_soc_factor",
            "k_R",
            "—",
            "internal resistance at 0 % / at ≥ 20 % state of charge",
            origin="chemistry table (1.5 / 1.5)",
            bounds=(1, None),
            source="generic, to confirm",
        ),
    )
    expected_forms: list = []  # set after the class (needs the factories)

    @classmethod
    def from_capacity(
        cls,
        chemistry: str,
        n_series: int,
        capacity_mah: float,
        n_parallel: int = 1,
        **overrides: float,
    ) -> BatteryModel:
        """Build a pack from its capacity (mAh); the mass is derived."""
        chem = cls._chemistry(chemistry, overrides)
        capacity_ah = capacity_mah / 1000.0
        mass = (
            n_series * chem["v_nominal"] * capacity_ah / chem["specific_energy_wh_kg"]
        )
        return cls(
            chemistry=chemistry,
            n_series=n_series,
            n_parallel=n_parallel,
            capacity_ah=capacity_ah,
            mass_kg=mass,
            **chem,
        )

    @classmethod
    def from_mass(
        cls,
        chemistry: str,
        n_series: int,
        mass_kg: float,
        n_parallel: int = 1,
        **overrides: float,
    ) -> BatteryModel:
        """Build a pack from its mass (kg); the capacity is derived."""
        chem = cls._chemistry(chemistry, overrides)
        capacity_ah = (
            mass_kg * chem["specific_energy_wh_kg"] / (n_series * chem["v_nominal"])
        )
        return cls(
            chemistry=chemistry,
            n_series=n_series,
            n_parallel=n_parallel,
            capacity_ah=capacity_ah,
            mass_kg=mass_kg,
            **chem,
        )

    @staticmethod
    def _chemistry(chemistry: str, overrides: dict[str, float]) -> dict[str, float]:
        if chemistry not in CHEMISTRIES:
            msg = f"Unknown chemistry '{chemistry}'. Available: {list(CHEMISTRIES)}"
            raise ValueError(msg)
        values = dict(vars(CHEMISTRIES[chemistry]))
        unknown = set(overrides) - set(values)
        if unknown:
            msg = f"Unknown battery overrides {sorted(unknown)}."
            raise ValueError(msg)
        values.update(overrides)
        return values

    @property
    def open_circuit_voltage(self) -> float:
        """V₀ = n_s·V_n (V)."""
        return self.p.n_series * self.p.v_nominal

    @property
    def resistance_ohm(self) -> float:
        """R = n_s·r / C (Ω)."""
        return self.p.n_series * self.p.r_cell_ohm_ah / self.p.capacity_ah

    def energy_wh(self) -> float:
        """Nominal energy E = n_s·V_n·C (Wh)."""
        return self.open_circuit_voltage * self.p.capacity_ah

    def usable_energy_j(self) -> float:
        """Usable energy E_u = 3600·f_u·E (J)."""
        return 3600.0 * self.p.usable_fraction * self.energy_wh()

    def max_current_a(self) -> float:
        """I_max = c_max·C (A)."""
        return self.p.c_max * self.p.capacity_ah

    def ocv_v(self, soc: float | None = None) -> float:
        """Open-circuit pack voltage at a state of charge; V₀ = n_s·V_n without (V)."""
        if soc is None:
            return self.open_circuit_voltage
        s, y = np.array(self.p.ocv_shape, dtype=float).T
        shape = float(np.interp(np.clip(soc, 0.0, 1.0), s, y))
        return self.p.n_series * (
            self.p.v_cutoff + shape * (self.p.v_full - self.p.v_cutoff)
        )

    def resistance_at(self, soc: float | None = None) -> float:
        """Internal resistance at a state of charge; R without (Ω)."""
        if soc is None:
            return self.resistance_ohm
        low = max(0.0, (SOC_KNEE - float(soc)) / SOC_KNEE)
        return self.resistance_ohm * (1.0 + (self.p.r_low_soc_factor - 1.0) * low)

    def discharge(
        self,
        durations_s: list[float],
        powers_w: list[float],
        names: list[str] | None = None,
        soc0: float = 1.0,
        n_sub: int = 20,
    ) -> DischargeProfile:
        """State of charge and voltages along segments of constant terminal power.

        Stateless: the whole power history is given. Each segment is split in ``n_sub``
        steps integrated with the midpoint rule on ds/dt = −P_c(s) / E.

        Args:
            durations_s: The segment durations (s).
            powers_w: The terminal power of each segment (W).
            names: The segment names.
            soc0: The state of charge at the start.
            n_sub: The number of steps per segment.
        """
        energy = 3600.0 * self.energy_wh()

        def chemical(soc: float, power: float) -> float:
            return float(
                self.evaluate({"power_w": power, "soc": soc})["chemical_power_w"]
            )

        out = DischargeProfile(names=list(names or [""] * len(durations_s)))
        t, soc = 0.0, soc0

        def record(power: float) -> None:
            y = self.evaluate({"power_w": power, "soc": soc})
            out.time_s.append(t)
            out.soc.append(soc)
            out.ocv_v.append(self.ocv_v(soc))
            out.voltage_v.append(float(y["voltage_v"]))
            out.current_a.append(float(y["current_a"]))

        for duration, power in zip(durations_s, powers_w, strict=True):
            dt = duration / n_sub
            record(power)
            for _ in range(n_sub):
                mid = soc - 0.5 * dt * chemical(soc, power) / energy
                soc -= dt * chemical(mid, power) / energy
                t += dt
            record(power)
            out.segment_end.append(len(out.time_s) - 1)
        return out

    def evaluate(self, x):
        power = np.asarray(x["power_w"], dtype=float)
        soc = x.get("soc")
        v0 = self.ocv_v(soc)
        r = self.resistance_at(soc)
        if r == 0.0:  # noqa: RUF069 - exact zero is the ideal-battery sentinel
            current = power / v0
            feasible = np.ones_like(power, dtype=bool)
        else:
            disc = v0**2 - 4.0 * r * power
            feasible = disc >= 0.0
            current = np.where(
                feasible, (v0 - np.sqrt(np.clip(disc, 0.0, None))) / (2.0 * r), np.nan
            )
        voltage = v0 - r * current
        return {
            "current_a": current,
            "voltage_v": voltage,
            "chemical_power_w": v0 * current,
            "c_rate_margin": 1.0 - current / self.max_current_a(),
            "feasible": feasible,
            "cutoff_ok": feasible & (voltage >= self.p.n_series * self.p.v_cutoff),
        }


def _example(**overrides: float) -> dict:
    """Parameter values of a 6S, 600 g Li-ion pack."""
    return dict(vars(BatteryModel.from_mass("li-ion", 6, 0.6, **overrides).p))


BatteryModel.expected_forms = [
    Invariant(
        "capacity → mass → capacity round trip",
        lambda m: bool(
            np.isclose(
                BatteryModel.from_capacity(
                    m.p.chemistry, m.p.n_series, 1000.0 * m.p.capacity_ah
                ).p.mass_kg,
                m.p.mass_kg,
                rtol=1e-12,
            )
        ),
        params=_example(),
    ),
    Invariant(
        "R = 0 ⇒ chemical power equals terminal power",
        lambda m: bool(
            np.isclose(
                float(m.evaluate({"power_w": 100.0})["chemical_power_w"]),
                100.0,
                rtol=1e-9,
            )
        ),
        params=_example(r_cell_ohm_ah=0.0),
    ),
    Invariant(
        "energy proportional to mass",
        lambda m: bool(
            np.isclose(
                2.0 * m.energy_wh(),
                BatteryModel.from_mass(
                    m.p.chemistry, m.p.n_series, 2.0 * m.p.mass_kg
                ).energy_wh(),
            )
        ),
        params=_example(),
    ),
    Invariant(
        "open-circuit voltage n_s·V_f full and n_s·V_c empty",
        lambda m: bool(
            np.isclose(m.ocv_v(1.0), m.p.n_series * m.p.v_full)
            and np.isclose(m.ocv_v(0.0), m.p.n_series * m.p.v_cutoff)
        ),
        params=_example(),
    ),
    Invariant(
        "R = 0 ⇒ discharge energy closure: s_end = 1 − Σ P·t / E",
        lambda m: bool(
            np.isclose(
                m.discharge([600.0, 300.0], [200.0, 50.0]).soc[-1],
                1.0 - (200.0 * 600.0 + 50.0 * 300.0) / (3600.0 * m.energy_wh()),
                rtol=1e-12,
            )
        ),
        params=_example(r_cell_ohm_ah=0.0),
    ),
    Invariant(
        "constant power ⇒ terminal voltage non-increasing",
        lambda m: bool(
            np.all(np.diff(m.discharge([1800.0], [150.0]).voltage_v) <= 0.0)
        ),
        params=_example(),
    ),
]
