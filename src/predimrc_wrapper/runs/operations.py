# Ported from VIMSEO (vimseo.results), modified for predimrc_wrapper.
# Copyright 2021 IRT Saint Exupery, https://www.irt-saintexupery.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.

"""The functions behind the verbs of the collections of runs (ported from ``vimseo.results``).

They work on the table of the summaries of the runs, one row per run, whose columns are
the metadata, ``inputs.{path}`` and ``outputs.{name}``. They return new objects and never
change their arguments nor the stored runs.
"""

from __future__ import annotations

import numbers
from collections import Counter
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from pandas import DataFrame

from predimrc_wrapper.runs.query import apply_query

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping

INPUT_PREFIX = "inputs."
"""The prefix of the columns of the inputs."""

OUTPUT_PREFIX = "outputs."
"""The prefix of the columns of the outputs."""


def get_input_columns(summaries: DataFrame, ignored: Iterable[str] = ()) -> list[str]:
    """Return the columns of the inputs, except the ignored ones.

    Args:
        summaries: The summaries.
        ignored: The names of the inputs to ignore.
    """
    ignored = {f"{INPUT_PREFIX}{name}" for name in ignored}
    return [
        column
        for column in summaries.columns
        if column.startswith(INPUT_PREFIX) and column not in ignored
    ]


def _as_datetime(value: str | date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(value)


def filter_summaries(
    summaries: DataFrame,
    query: str = "",
    failed: bool | None = None,
    since: str | date | datetime | None = None,
    until: str | date | datetime | None = None,
    name_contains: str = "",
    **metadata: Any,
) -> DataFrame:
    """Select the summaries.

    Args:
        summaries: The summaries.
        query: A query, see :mod:`.query`.
        failed: Whether to keep only the infeasible runs (``True``), only the feasible
            ones (``False``), or both (``None``).
        since: The earliest date of the runs (ISO text, date or datetime), included.
        until: The latest date of the runs, included (a date covers its whole day).
        name_contains: A text the run name or the project name contains (any case).
        **metadata: Values of metadata which the runs must have, e.g.
            ``architecture="quadplane"``; a list or tuple keeps any of its values.

    Returns:
        The selected summaries.

    Raises:
        KeyError: If a metadata is not a column of the summaries.
    """
    selected = summaries
    for name, value in metadata.items():
        if name not in selected.columns:
            if selected.empty:
                continue
            msg = f"Unknown metadata {name}; the columns are {list(selected.columns)}."
            raise KeyError(msg)
        if isinstance(value, (list, tuple, set)):
            selected = selected[selected[name].isin(list(value))]
        else:
            selected = selected[selected[name] == value]
    if selected.empty:
        return selected
    if failed is not None:
        selected = selected[(~selected["feasible"].astype(bool)) == failed]
    if since is not None or until is not None:
        dates = selected["date"].map(_as_datetime)
        if since is not None:
            selected = selected[dates >= _as_datetime(since)]
            dates = dates[selected.index]
        if until is not None:
            end = _as_datetime(until)
            if not isinstance(until, datetime) and len(str(until)) <= 10:
                end = end.replace(hour=23, minute=59, second=59)
            selected = selected[dates <= end]
    if name_contains:
        text = name_contains.lower()
        names = selected["run_name"].astype(str).str.lower()
        projects = selected["project_name"].astype(str).str.lower()
        selected = selected[
            names.str.contains(text, regex=False)
            | projects.str.contains(text, regex=False)
        ]
    return apply_query(selected, query)


def get_varying_inputs(summaries: DataFrame, ignored: Iterable[str] = ()) -> DataFrame:
    """Return the inputs taking several values.

    Args:
        summaries: The summaries.
        ignored: The names of the inputs to ignore.

    Returns:
        One row per varying input, indexed by its name, with the number of its values
        and the sorted values.
    """
    rows = {}
    for column in get_input_columns(summaries, ignored):
        values = summaries[column].dropna().unique().tolist()
        if len(values) > 1 or (values and summaries[column].isna().any()):
            rows[column[len(INPUT_PREFIX) :]] = {
                "n_values": len(values) + int(bool(summaries[column].isna().any())),
                "values": sorted(values, key=_sort_key),
            }
    return DataFrame.from_dict(
        rows, orient="index", columns=["n_values", "values"]
    ).rename_axis("input")


def _sort_key(value: Any) -> tuple[int, Any]:
    """Return a key sorting numbers before strings."""
    return (0, value) if isinstance(value, numbers.Real) else (1, str(value))


def find_duplicates(summaries: DataFrame, ignored: Iterable[str] = ()) -> DataFrame:
    """Return the groups of runs with the same inputs.

    Nothing is deleted: the duplicates are only reported.

    Args:
        summaries: The summaries.
        ignored: The names of the inputs to ignore.

    Returns:
        The runs which have a duplicate, with a column ``group`` numbering the groups.
    """
    columns = get_input_columns(summaries, ignored)
    if summaries.empty or not columns:
        return DataFrame(columns=["group", *summaries.columns])
    keys = summaries[columns].astype(str).agg("|".join, axis=1)
    duplicated = summaries[keys.duplicated(keep=False)]
    groups = {
        key: index for index, key in enumerate(dict.fromkeys(keys[duplicated.index]))
    }
    duplicated = duplicated.assign(group=keys[duplicated.index].map(groups))
    return duplicated[["group", *summaries.columns]].sort_values("group", kind="stable")


def to_dataframe(
    summaries: DataFrame, id_column: str, variable_names: Iterable[str] = ()
) -> DataFrame:
    """Return the table of the runs, one row per run, indexed by their identifiers.

    Args:
        summaries: The summaries.
        id_column: The column of the identifiers.
        variable_names: The names of the inputs, outputs and metadata, without prefix.
            If empty, all the columns.

    Returns:
        The table, whose columns are the names of the variables, without prefix
        unless an input and an output have the same name.

    Raises:
        KeyError: For an unknown variable.
    """
    variable_names = list(variable_names)
    if not variable_names:
        table = summaries
    else:
        columns = []
        for name in variable_names:
            for column in (f"{INPUT_PREFIX}{name}", f"{OUTPUT_PREFIX}{name}", name):
                if column in summaries.columns:
                    columns.append(column)
                    break
            else:
                msg = f"Unknown variable {name}."
                raise KeyError(msg)
        table = (
            summaries[[id_column, *columns]]
            if id_column not in columns
            else (summaries[columns])
        )
    # A column keeps its prefix when its name would collide with another column.
    stripped = Counter(
        column.split(".", 1)[1]
        for column in table.columns
        if column.startswith((INPUT_PREFIX, OUTPUT_PREFIX))
    )
    renamed = {
        column: name
        for column in table.columns
        if column.startswith((INPUT_PREFIX, OUTPUT_PREFIX))
        and stripped[name := column.split(".", 1)[1]] == 1
        and name not in table.columns
    }
    return table.rename(columns=renamed).set_index(id_column)


def group_by_variation(
    summaries: DataFrame, along: str, ignored: Iterable[str] = ()
) -> tuple[dict[tuple[tuple[str, Any], ...], list[Any]], list[Any]]:
    """Group the runs which differ by one input only.

    Args:
        summaries: The summaries.
        along: The name of the input varying in a family.
        ignored: The names of the inputs to ignore.

    Returns:
        The index labels of the rows of each family, sorted by the varying input and
        bound to the values of the other varying inputs, and the labels of the rows
        alone in their group.

    Raises:
        KeyError: If ``along`` is not an input.
    """
    column = f"{INPUT_PREFIX}{along}"
    if column not in summaries.columns:
        msg = f"Unknown input {along}."
        raise KeyError(msg)
    other_columns = [
        name for name in get_varying_inputs(summaries, ignored).index if name != along
    ]
    families = {}
    ungrouped = []
    groups = (
        summaries.groupby(
            [f"{INPUT_PREFIX}{name}" for name in other_columns],
            dropna=False,
            sort=True,
        )
        if other_columns
        else [((), summaries)]
    )
    for key, rows in groups:
        key = key if isinstance(key, tuple) else (key,)
        if rows[column].nunique(dropna=True) > 1:
            rows = rows.sort_values(column, kind="stable")
            families[tuple(zip(other_columns, key, strict=True))] = list(rows.index)
        else:
            ungrouped.extend(rows.index)
    return families, ungrouped


def get_labels(
    summaries: DataFrame, name_column: str, ignored: Iterable[str]
) -> list[str]:
    """Return a label per run, from its varying inputs, else its name.

    Args:
        summaries: The summaries.
        name_column: The column of the names of the runs.
        ignored: The names of the inputs to ignore.
    """
    varying = list(get_varying_inputs(summaries, ignored).index)
    if not varying or len(varying) > 3:
        return list(summaries[name_column].astype(str))
    return [
        ", ".join(
            f"{name} = {_format(row[f'{INPUT_PREFIX}{name}'])}" for name in varying
        )
        for _, row in summaries.iterrows()
    ]


def _format(value: Any) -> str:
    """Return a short text of a value."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def get_scalars(row: Mapping[str, Any]) -> dict[str, float]:
    """Return the numerical outputs of a row of summaries, without prefix."""
    return {
        name[len(OUTPUT_PREFIX) :]: value
        for name, value in row.items()
        if name.startswith(OUTPUT_PREFIX)
        and isinstance(value, numbers.Real)
        and not isinstance(value, bool)
    }
