"""Flight scenarios: ordered lists of segments (REQ-MIS-001, REQ-MIS-002).

This module has no dependency on the rest of the package, so that the project schema
can embed scenarios.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

SegmentKind = Literal["hover", "vertical_climb", "vertical_descent", "transition", "cruise", "loiter"]
Speed = float | Literal["optimal_endurance", "optimal_range"]


class Segment(BaseModel):
    """One flight segment.

    Hover, transition and loiter are given by a duration; cruise by a distance;
    vertical climb and descent by an altitude change. Cruise and loiter may instead run
    ``until_reserve``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: SegmentKind = Field(description="Segment kind: hover, vertical climb or descent, transition, cruise, loiter")
    duration_s: float | None = Field(default=None, gt=0, description="Duration (s)")
    distance_m: float | None = Field(default=None, gt=0, description="Distance (m)")
    altitude_change_m: float | None = Field(default=None, description="Altitude change (m); negative for a descent")
    vertical_speed_m_s: float = Field(default=1.5, gt=0, description="Vertical speed (m/s)")
    speed: Speed = Field(default="optimal_range", description="Speed (m/s) or optimal_endurance / optimal_range")
    until_reserve: bool = Field(default=False, description="Fly until only the reserve is left")

    @model_validator(mode="after")
    def _one_extent(self) -> Segment:
        given = [k for k in ("duration_s", "distance_m", "altitude_change_m") if getattr(self, k) is not None]
        if self.until_reserve:
            given.append("until_reserve")
        expected = {
            "hover": {"duration_s"},
            "transition": {"duration_s"},
            "loiter": {"duration_s", "until_reserve"},
            "cruise": {"distance_m", "until_reserve"},
            "vertical_climb": {"altitude_change_m"},
            "vertical_descent": {"altitude_change_m"},
        }[self.kind]
        if len(given) != 1 or given[0] not in expected:
            msg = f"A {self.kind} segment needs exactly one of {sorted(expected)}, got {given or 'none'}."
            raise ValueError(msg)
        if self.kind == "vertical_climb" and self.altitude_change_m <= 0:
            msg = "A vertical climb needs a positive altitude change."
            raise ValueError(msg)
        if self.kind == "vertical_descent" and self.altitude_change_m >= 0:
            msg = "A vertical descent needs a negative altitude change."
            raise ValueError(msg)
        return self


class Scenario(BaseModel):
    """An ordered list of segments, with at most one ``until_reserve`` segment."""

    model_config = ConfigDict(extra="forbid")

    segments: list[Segment] = Field(min_length=1, description="Ordered flight segments")

    @model_validator(mode="after")
    def _one_until_reserve(self) -> Scenario:
        if sum(s.until_reserve for s in self.segments) > 1:
            msg = "At most one segment can be until_reserve."
            raise ValueError(msg)
        return self

    @classmethod
    def hover_time(cls, hover_s: float, wing_borne: bool = True, altitude_m: float = 30.0) -> Scenario:
        """Vertical climb, hover, (transition), cruise until reserve, (transition), descent.

        Args:
            hover_s: The hover duration (s); 0 skips the hover segment.
            wing_borne: Whether the aircraft has a wing (adds the transitions).
            altitude_m: The vertical climb and descent height (m).
        """
        segments = [Segment(kind="vertical_climb", altitude_change_m=altitude_m, vertical_speed_m_s=2.0)]
        if hover_s > 0:
            segments.append(Segment(kind="hover", duration_s=hover_s))
        if wing_borne:
            segments.append(Segment(kind="transition", duration_s=15.0))
        segments.append(Segment(kind="cruise", until_reserve=True, speed="optimal_range"))
        if wing_borne:
            segments.append(Segment(kind="transition", duration_s=15.0))
        segments.append(Segment(kind="vertical_descent", altitude_change_m=-altitude_m, vertical_speed_m_s=1.5))
        return cls(segments=segments)
