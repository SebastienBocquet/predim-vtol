"""The queries selecting runs from their summaries (ported from ``vimseo.results.query``).

A query is a string with the syntax of :meth:`pandas.DataFrame.query`, evaluated on the
table of the summaries, one row per run::

    `inputs.battery.n_parallel` >= 2 and (`outputs.flight_time_v1` > 900 or architecture == 'quadplane')

The variables are written ``inputs.{path}`` and ``outputs.{name}`` between backticks,
the metadata by their names, e.g. ``architecture``, ``project_name``, ``feasible``. The
operators are ``and``, ``or``, ``not``, the comparisons and ``in``, with parentheses.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

_BACKTICKED = re.compile(r"`([^`]+)`")
"""The pattern of a name between backticks."""


def apply_query(summaries: DataFrame, query: str) -> DataFrame:
    """Select the summaries matching a query.

    The query is evaluated on the table only: it cannot read a Python variable
    (``@name``).

    Args:
        summaries: The summaries, one row per run.
        query: The query. If empty, all the summaries are kept.

    Returns:
        The selected summaries.

    Raises:
        ValueError: If the query is malformed or reads a Python variable.
    """
    if not query.strip():
        return summaries
    if "@" in _BACKTICKED.sub("", query):
        msg = f"The query {query!r} cannot read Python variables (@name)."
        raise ValueError(msg)
    if summaries.empty:
        return summaries
    try:
        return summaries.query(query, engine="python", local_dict={}, global_dict={})
    except Exception as error:  # ruff: ignore[blind-except]
        msg = f"The query {query!r} cannot be evaluated: {error}"
        raise ValueError(msg) from error
