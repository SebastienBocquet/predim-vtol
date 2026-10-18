"""Cost and reliability tab: tables (no Streamlit import, REQ-COST-001 to -003)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.cost import CostResult
    from predimrc_wrapper.reliability import Reliability


def purchase_rows(result: CostResult) -> list[dict]:
    """One row per item, with its source; items without a price are flagged."""
    return [
        {
            "category": i.category,
            "item": i.item,
            "amount": round(i.quantity, 2),
            f"unit price ({result.currency})": None
            if i.unit_price is None
            else round(i.unit_price, 3),
            f"total ({result.currency})": None
            if i.total is None
            else round(i.total, 2),
            "price status": i.status,
            "price source": i.source,
        }
        for i in result.items
    ]


def use_rows(result: CostResult) -> list[dict]:
    """Wear cost per flight and per flight hour, by category."""
    hours = result.flight_time_s / 3600.0
    rows = [
        {
            "wear item": k,
            f"per flight ({result.currency})": round(v, 3),
            f"per flight hour ({result.currency})": round(v / hours, 3)
            if hours > 0
            else None,
        }
        for k, v in result.per_flight.items()
    ]
    rows.append({
        "wear item": "total",
        f"per flight ({result.currency})": round(result.cost_per_flight, 3),
        f"per flight hour ({result.currency})": None
        if not np.isfinite(result.cost_per_hour)
        else round(result.cost_per_hour, 3),
    })
    return rows


def reliability_rows(rel: Reliability, project: Project) -> list[dict]:
    """One row per stopped lift motor."""
    return [
        {
            "motor stopped": c.motor + 1,
            "unit": project.motors[c.motor].unit,
            "hover survives": c.survivable,
            "remaining T/W": round(c.thrust_to_weight, 2),
            "why": c.reason,
        }
        for c in rel.cases
    ]
