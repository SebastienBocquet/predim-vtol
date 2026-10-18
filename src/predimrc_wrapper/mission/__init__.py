"""Mission: scenarios, segment powers and mission solver (MVP-005).

The solver is imported lazily so that the project schema can import the scenario
format without a circular import.
"""

from predimrc_wrapper.mission.scenario import Scenario
from predimrc_wrapper.mission.scenario import Segment

__all__ = ["Scenario", "Segment"]


def __getattr__(name: str):
    if name in ("MissionResult", "MissionSolver", "SegmentPower", "SpeedSweep"):
        from predimrc_wrapper.mission import solver  # noqa: PLC0415

        return getattr(solver, name)
    raise AttributeError(name)
