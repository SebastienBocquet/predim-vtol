# Ported from VIMSEO (vimseo.results), modified for predimrc_wrapper.
# Copyright 2021 IRT Saint Exupery, https://www.irt-saintexupery.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.

"""The collection of stored runs (ported from ``vimseo.results.collection``).

A collection is immutable: every verb returns a new collection or a new object
(``DataFrame``, :class:`.Families`, figures), and nothing is deleted from the store.
It holds the table of the summaries of its runs, one row per run, and loads the detailed
result of a run (``result.json``) only when it is accessed (``runs[i]``, iteration) or
when its curves are drawn.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any

from pandas import DataFrame
from pandas import concat

from predimrc_wrapper.runs import operations
from predimrc_wrapper.runs.operations import INPUT_PREFIX
from predimrc_wrapper.runs.operations import OUTPUT_PREFIX

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date
    from datetime import datetime

    from predimrc_wrapper.runs.store import StoredRun

LOGGER = logging.getLogger(__name__)

MAX_SUPERPOSED_RUNS = 20
"""The number of runs above which superposing their curves is discouraged."""

PROVENANCE_PREFIX = "data_hashes."
"""The prefix of the columns of the hashes of the reference data."""


class FamilyKey(Mapping):
    """The values of the inputs shared by a family of runs, frozen and hashable."""

    def __init__(self, items: Iterable[tuple[str, Any]] = ()):
        self.__items = tuple(items)

    def __getitem__(self, name: str) -> Any:
        for key, value in self.__items:
            if key == name:
                return value
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        return iter(key for key, _ in self.__items)

    def __len__(self) -> int:
        return len(self.__items)

    def __hash__(self) -> int:
        return hash(self.__items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FamilyKey):
            return self.__items == other.__items
        if isinstance(other, tuple):
            return self.__items == other
        return NotImplemented

    def __str__(self) -> str:
        return ", ".join(f"{key}={value}" for key, value in self.__items) or "all"

    def __repr__(self) -> str:
        return f"FamilyKey({self})"


class RunResults:
    """An immutable collection of stored runs."""

    ID_COLUMN = "run_id"
    """The column of the identifiers of the runs."""

    NAME_COLUMN = "run_name"
    """The column of the names of the runs."""

    def __init__(
        self,
        summaries: DataFrame,
        loader: Callable[[Mapping[str, Any]], StoredRun],
        ignored: Iterable[str] = (),
        cache: dict[str, StoredRun] | None = None,
    ) -> None:
        """
        Args:
            summaries: The summaries of the runs, one row per run.
            loader: The function loading a run from its summary.
            ignored: The names of the inputs ignored by the comparisons.
            cache: The runs already loaded, bound to their identifiers.
        """
        self.__summaries = summaries.reset_index(drop=True)
        self.__loader = loader
        self.__ignored = tuple(dict.fromkeys(ignored))
        self.__cache = {} if cache is None else cache

    def _new(
        self, summaries: DataFrame, ignored: Iterable[str] | None = None
    ) -> RunResults:
        """Return a collection sharing the loaded runs."""
        return type(self)(
            summaries,
            self.__loader,
            self.__ignored if ignored is None else ignored,
            self.__cache,
        )

    @property
    def summaries(self) -> DataFrame:
        """The summaries of the runs, one row per run."""
        return self.__summaries.copy()

    @property
    def ignored(self) -> tuple[str, ...]:
        """The names of the inputs ignored by the comparisons."""
        return self.__ignored

    @property
    def ids(self) -> list[str]:
        """The identifiers of the runs."""
        return list(self.__summaries[self.ID_COLUMN]) if len(self) else []

    def _load(self, row: Mapping[str, Any]) -> StoredRun:
        """Return the run of a row of the summaries, loaded once."""
        identifier = row[self.ID_COLUMN]
        if identifier not in self.__cache:
            self.__cache[identifier] = self.__loader(row)
        return self.__cache[identifier]

    def __len__(self) -> int:
        return len(self.__summaries)

    def __iter__(self) -> Iterator[StoredRun]:
        for _, row in self.__summaries.iterrows():
            yield self._load(row)

    def __getitem__(self, index: int | slice | str):
        if isinstance(index, str):
            rows = self.__summaries[self.__summaries[self.ID_COLUMN] == index]
            if rows.empty:
                raise KeyError(index)
            return self._load(rows.iloc[0])
        if isinstance(index, slice):
            return self._new(self.__summaries.iloc[index])
        return self._load(self.__summaries.iloc[index])

    def __repr__(self) -> str:
        summaries = self.__summaries
        text = f"RunResults({len(self)} runs"
        for column in ("project_name", "architecture"):
            if column in summaries.columns and not summaries.empty:
                text += f", {column} {sorted(summaries[column].astype(str).unique())}"
        if self.__ignored:
            text += f", ignoring {list(self.__ignored)}"
        return f"{text})"

    def filter(
        self,
        query: str = "",
        failed: bool | None = None,
        since: str | date | datetime | None = None,
        until: str | date | datetime | None = None,
        name_contains: str = "",
        **metadata: Any,
    ) -> RunResults:
        """Return the runs matching every condition.

        Args:
            query: A query, see :mod:`.query`, e.g.
                ``"`inputs.battery.n_parallel` >= 2 and `outputs.flight_time_v1` > 900"``.
            failed: Whether to keep only the infeasible runs (``True``), only the
                feasible ones (``False``), or both (``None``).
            since: The earliest date of the runs, e.g. ``"2026-10-01"``.
            until: The latest date of the runs (a date covers its whole day).
            name_contains: A text the run name or the project name contains (any case).
            **metadata: Values of metadata, e.g. ``architecture="quadplane"``,
                ``project_name=["A", "B"]``.

        Returns:
            A new collection.
        """
        return self._new(
            operations.filter_summaries(
                self.__summaries, query, failed, since, until, name_contains, **metadata
            )
        )

    def ignoring(self, *names: str) -> RunResults:
        """Return the same runs, ignoring some inputs in the comparisons.

        The ignored inputs are left out of :meth:`varying_inputs`, :meth:`families`
        and :meth:`duplicates`; they stay in :meth:`to_dataframe`.

        Args:
            *names: The names of the inputs.

        Returns:
            A new collection.
        """
        return self._new(self.__summaries, (*self.__ignored, *names))

    def varying_inputs(self) -> DataFrame:
        """Return the inputs taking several values, except the ignored ones.

        Returns:
            One row per varying input, with the number of its values and the values.
        """
        return operations.get_varying_inputs(self.__summaries, self.__ignored)

    def provenance(self) -> DataFrame:
        """Return the tool versions and reference data differing between the runs.

        A difference of outputs between such runs may come from the data, not from the
        inputs.

        Returns:
            One row per differing item (``tool_version``, ``format_version`` or a
            source of reference data), with its number of values.
        """
        rows = {}
        for column in self.__summaries.columns:
            if column not in (
                "tool_version",
                "format_version",
            ) and not column.startswith(PROVENANCE_PREFIX):
                continue
            values = self.__summaries[column].dropna().unique().tolist()
            if len(values) > 1:
                rows[column.removeprefix(PROVENANCE_PREFIX)] = {
                    "n_values": len(values),
                    "values": values,
                }
        return DataFrame.from_dict(
            rows, orient="index", columns=["n_values", "values"]
        ).rename_axis("item")

    def duplicates(self) -> DataFrame:
        """Return the groups of runs with the same inputs; nothing is deleted.

        Returns:
            The runs which have a duplicate, with a column ``group``.
        """
        return operations.find_duplicates(self.__summaries, self.__ignored)

    def to_dataframe(self, variable_names: Iterable[str] = ()) -> DataFrame:
        """Return the table of the runs, one row per run.

        Args:
            variable_names: The names of the inputs, outputs and metadata. If empty,
                all the columns of the summaries.

        Returns:
            The table, indexed by the identifiers of the runs.
        """
        return operations.to_dataframe(self.__summaries, self.ID_COLUMN, variable_names)

    def labels(self) -> list[str]:
        """A label per run: its varying inputs (up to 3), else its name."""
        return operations.get_labels(self.__summaries, self.NAME_COLUMN, self.__ignored)

    def families(self, along: str) -> Families:
        """Group the runs differing by a single input.

        Args:
            along: The name of the input varying in a family.

        Returns:
            The families, bound to the values of the other varying inputs.
        """
        families, ungrouped = operations.group_by_variation(
            self.__summaries, along, self.__ignored
        )
        if ungrouped:
            LOGGER.warning(
                "%d runs belong to no family (a single value of %s): %s.",
                len(ungrouped),
                along,
                list(self.__summaries.loc[ungrouped, self.ID_COLUMN]),
            )
        return Families(
            {
                FamilyKey(key): self._new(self.__summaries.loc[rows])
                for key, rows in families.items()
            },
            along,
            self.__ignored,
            self._new(self.__summaries.loc[ungrouped]),
        )

    def compare_to(
        self,
        reference: str | Mapping[str, float],
        output_names: Iterable[str] = (),
    ) -> DataFrame:
        """Return the relative differences of the outputs to a reference.

        Args:
            reference: The identifier of a run of the collection, or reference values
                of the outputs.
            output_names: The names of the outputs. If empty, all the numerical outputs
                (or those of ``reference`` when it is a mapping).

        Returns:
            One row per run: ``(value − reference) / |reference|`` for each output.
        """
        if isinstance(reference, str):
            row = self.__summaries[self.__summaries[self.ID_COLUMN] == reference]
            if row.empty:
                raise KeyError(reference)
            reference = operations.get_scalars(row.iloc[0])
        output_names = list(output_names) or [
            name
            for name in reference
            if f"{OUTPUT_PREFIX}{name}" in self.__summaries.columns
        ]
        table = self.to_dataframe(output_names)
        errors = DataFrame(index=table.index)
        for name in output_names:
            ref = reference[name]
            errors[name] = (
                (table[name] - ref) / abs(ref)
                if ref and not math.isnan(ref)
                else float("nan")
            )
        return errors

    def visualize(self, names: Iterable[str] = ()) -> dict[str, Any]:
        """Superpose the runs, one figure per quantity (plotly).

        Args:
            names: The names of the figures, see :data:`.plots.FIGURES`. If empty, all.

        Returns:
            The figures, whose traces are labelled by the varying inputs.
        """
        from predimrc_wrapper.runs import plots  # noqa: PLC0415

        if len(self) > MAX_SUPERPOSED_RUNS:
            LOGGER.warning(
                "Superposing %d runs: use families(along=...) to group them.", len(self)
            )
        return plots.superpose(self, names)

    def _plot_family(self, along: str, title: str = "") -> dict[str, Any]:
        """Return the figures of the runs as a family varying along an input."""
        from predimrc_wrapper.runs import plots  # noqa: PLC0415

        return plots.plot_family(self, along, title)


class Families(Mapping):
    """The families of runs differing by a single input.

    It maps the values of the other varying inputs (a :class:`.FamilyKey`) to the
    collection of a family, whose runs are sorted by the varying input.
    """

    def __init__(
        self,
        families: Mapping[FamilyKey, RunResults],
        along: str,
        ignoring: Iterable[str],
        ungrouped: RunResults,
    ) -> None:
        """
        Args:
            families: The families, bound to their keys.
            along: The name of the input varying in a family.
            ignoring: The names of the inputs ignored by the comparisons.
            ungrouped: The runs alone in their group.
        """
        self.__families = dict(families)
        self.along = along
        """The name of the input varying in a family."""
        self.ignoring = tuple(ignoring)
        """The names of the inputs ignored by the comparisons."""
        self.ungrouped = ungrouped
        """The runs alone in their group."""

    def __getitem__(self, key: FamilyKey | tuple) -> RunResults:
        return self.__families[key if isinstance(key, FamilyKey) else FamilyKey(key)]

    def __iter__(self) -> Iterator[FamilyKey]:
        return iter(self.__families)

    def __len__(self) -> int:
        return len(self.__families)

    def get(self, default: Any = None, **fixed: Any) -> RunResults | Any:
        """Return the family of the given values of the other varying inputs.

        Args:
            default: The value returned when there is no such family.
            **fixed: The values of the other varying inputs; a dotted path is passed
                as ``**{"battery.n_series": 4}``.
        """
        for key, family in self.__families.items():
            if dict(key) == fixed:
                return family
        return default

    def __repr__(self) -> str:
        lines = [
            (
                f"Families(along={self.along!r}, ignoring={self.ignoring}, "
                f"{len(self)} families, {len(self.ungrouped)} ungrouped)"
            )
        ]
        for key, family in self.__families.items():
            values = list(family.summaries[f"{INPUT_PREFIX}{self.along}"])
            lines.append(f"  {key}   RunResults({len(family)}, {values})")
        if len(self.ungrouped):
            lines.append(f"  ungrouped   {self.ungrouped.ids}")
        return "\n".join(lines)

    def visualize(self) -> dict[str, Any]:
        """Return the figures of each family.

        Returns:
            For each family, the figure of its outputs versus the varying input and
            the figures superposing its curves, labelled by the varying input; the keys
            end with the key of the family, e.g. ``outputs[battery.n_series=4]``.
        """
        figures = {}
        for key, family in self.__families.items():
            figures.update({
                f"{name}[{key}]": figure
                for name, figure in family._plot_family(self.along, str(key)).items()
            })
        return figures

    def to_dataframe(self, variable_names: Iterable[str] = ()) -> DataFrame:
        """Return the table of the runs of the families, with a column ``family``.

        Args:
            variable_names: The names of the inputs, outputs and metadata. If empty,
                all the columns of the summaries.
        """
        names = list(variable_names)
        if names and self.along not in names:
            names.insert(0, self.along)
        tables = [
            family.to_dataframe(names).assign(family=str(key))
            for key, family in self.__families.items()
        ]
        return DataFrame() if not tables else concat(tables)
