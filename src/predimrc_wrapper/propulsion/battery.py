"""Battery pack, specific-energy and internal-resistance model (MIC-PROP-BAT)."""

from __future__ import annotations

from dataclasses import dataclass

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


CHEMISTRIES: dict[str, Chemistry] = {
    # Generic data-sheet values, to be confirmed (see MIC-PROP-BAT).
    "lipo": Chemistry(150.0, 4.2, 3.7, 3.3, 0.010, 30.0, 0.85),
    "li-ion": Chemistry(200.0, 4.2, 3.6, 2.8, 0.040, 8.0, 0.90),
}


class BatteryModel(Model):
    """Battery pack.

    C = m_b·e / (n_s·V_n) or given; E = n_s·V_n·C; R = n_s·r / C; V₀ = n_s·V_n.
    The current for a terminal power P solves R·I² − V₀·I + P = 0 (smallest root;
    infeasible when P > V₀²/4R). The chemical power V₀·I includes the Joule losses.
    """

    mic_id = "MIC-PROP-BAT"
    inputs = ports(Port("power_w", "P", "W", "terminal power demanded", (0, None)))
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
        values = dict(CHEMISTRIES[chemistry].__dict__)
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

    def evaluate(self, x):
        power = np.asarray(x["power_w"], dtype=float)
        v0 = self.open_circuit_voltage
        r = self.resistance_ohm
        if r == 0.0:  # noqa: RUF069 - exact zero is the ideal-battery sentinel
            current = power / v0
            feasible = np.ones_like(power, dtype=bool)
        else:
            disc = v0**2 - 4.0 * r * power
            feasible = disc >= 0.0
            current = np.where(
                feasible, (v0 - np.sqrt(np.clip(disc, 0.0, None))) / (2.0 * r), np.nan
            )
        return {
            "current_a": current,
            "voltage_v": v0 - r * current,
            "chemical_power_w": v0 * current,
            "c_rate_margin": 1.0 - current / self.max_current_a(),
            "feasible": feasible,
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
]
