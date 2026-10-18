"""Test helpers: an analytic aero backend (parabolic polar) replacing PredimRC."""

from __future__ import annotations

import numpy as np

from predimrc_wrapper.predimrc_wrapper import AeroResults


class ParabolicAero:
    """Fake AeroBackend: Cx = cx0 + k·Cz² on a fixed wing area, at density ``rho``."""

    def __init__(self, area_m2: float = 0.308, cx0: float = 0.03, k: float = 0.04,
                 rho: float = 1.164, cz_max: float = 2.0) -> None:
        self.area_m2, self.cx0, self.k, self.rho, self.cz_max = area_m2, cx0, k, rho, cz_max
        self.calls = 0

    def evaluate(self, wing, stab, fus, settings) -> AeroResults:
        self.calls += 1
        m = settings.mass / 1000.0
        cz = np.linspace(self.cz_max, 0.05, 80)
        vx = np.sqrt(2 * m * 9.81 / (self.rho * self.area_m2 * cz))
        cx = self.cx0 + self.k * cz**2
        drag = m * 9.81 * cx / cz
        power = drag * vx
        return AeroResults(
            cz=cz, cx=cx, vx=vx, sink_rate=-power / (m * 9.81), finesse_vx=cz / cx, drag_n=drag,
            power_required_w=power, v_min=float(vx[0]), v_min_power=float(vx[np.argmin(power)]),
            v_max_finesse=float(vx[np.argmax(cz / cx)]), mass_kg=m, cg=30.0, foyer=35.0,
            total_surface=100 * self.area_m2, mean_chord=184.0, span_aero=1740.0, span_total=1825.0,
            aspect_ratio=9.83, aspect_ratio_el=11.05, rho=self.rho,
        )

    def close(self) -> None:
        pass


class ConstantEfficiencyUnit:
    """Stub cruise unit: P_b = T·V / eta, no limits."""

    def __init__(self, eta: float = 0.6) -> None:
        self.eta = eta

    def evaluate(self, x):
        p = np.asarray(x["thrust_n"]) * np.asarray(x["v_axial_m_s"]) / self.eta
        one = np.ones_like(p, dtype=float)
        return {"battery_power_w": p, "shaft_power_w": p, "current_margin": one, "power_margin": one,
                "voltage_margin": one}
