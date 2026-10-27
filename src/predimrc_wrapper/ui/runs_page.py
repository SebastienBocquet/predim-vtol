"""Runs page of the GUI: stored runs, filtered, tabulated and superposed (REQ-UI-013).

A run is saved on demand from the Results tab (Save run); this page works on the stored
runs, not on the project being edited, except to open the project of a run.
"""

from __future__ import annotations

import traceback
from datetime import date
from pathlib import Path

import streamlit as st

from predimrc_wrapper.runs import RunStore
from predimrc_wrapper.runs.plots import FIGURES
from predimrc_wrapper.ui.studies_view import OUTPUT_LABELS
from predimrc_wrapper.ui.studies_view import label

KEY_OUTPUTS = ["flight_time_v1", "flight_time_v2", "mass_total", "hover_power"]
"""The outputs shown by default in the comparison table."""


def save_form(app, project, two) -> None:
    """Name and Save run button of the Results tab (up-to-date result only)."""
    saved = st.session_state.get("runs.saved")
    c1, c2 = st.columns([3, 1])
    name = c1.text_input(
        "Run name",
        project.name,
        key=f"runs.name.{app.result_key}",
        help="Name of the stored run (Runs page); the project name by default.",
    )
    c2.write("")
    if c2.button(
        "Save run",
        disabled=saved is not None and saved[0] == app.result_key,
        help="Store this result with a copy of the project, to compare it later (Runs page).",
    ):
        path = RunStore().save(project, two, name, app.source_path)
        st.session_state["runs.saved"] = (app.result_key, str(path))
        st.rerun()
    if saved is not None and saved[0] == app.result_key:
        c1.caption(f"Saved in {saved[1]}")


def _dates(values) -> tuple[date, date]:
    days = sorted(date.fromisoformat(str(v)[:10]) for v in values if v)
    return (days[0], days[-1]) if days else (date.today(), date.today())


def _filters(runs):
    """The filter bar; returns the filtered collection, or None on an invalid query."""
    s = runs.summaries
    c1, c2, c3 = st.columns(3)
    architectures = c1.multiselect(
        "Architecture", sorted(s["architecture"].dropna().unique()), key="runs.arch"
    )
    projects = c2.multiselect(
        "Project", sorted(s["project_name"].dropna().unique()), key="runs.project"
    )
    first, last = _dates(s["date"])
    period = c3.date_input(
        "Dates", (first, last), min_value=first, max_value=last, key="runs.dates"
    )
    c1, c2, c3 = st.columns([2, 3, 1])
    text = c1.text_input("Name contains", key="runs.text")
    query = c2.text_input(
        "Query",
        key="runs.query",
        help="pandas syntax on the columns, names between backticks, e.g. "
        "`inputs.battery.n_series` >= 4 and `outputs.flight_time_v1` > 600",
    )
    c3.write("")
    feasible = c3.checkbox("Feasible only", key="runs.feasible")
    metadata = {}
    if architectures:
        metadata["architecture"] = architectures
    if projects:
        metadata["project_name"] = projects
    since, until = (period[0], period[-1]) if period else (None, None)
    try:
        return runs.filter(
            query,
            failed=False if feasible else None,
            since=since,
            until=until,
            name_contains=text,
            **metadata,
        )
    except (KeyError, ValueError) as error:
        st.error(str(error))
        return None


def _scaled(value, name: str):
    return value * OUTPUT_LABELS.get(name, ("", "", 1.0))[2]


def _selection(runs) -> list[str]:
    """The table of the runs with a column to tick the runs to compare."""
    s = runs.summaries
    rows = [
        {
            "compare": False,
            "date": str(r["date"]).replace("T", " "),
            "run": r["run_name"],
            "project": r["project_name"],
            "architecture": r["architecture"],
            "feasible": bool(r["feasible"]),
            **{
                label(n): _scaled(r.get(f"outputs.{n}"), n)
                for n in ("flight_time_v1", "flight_time_v2", "mass_total")
            },
            "data changed": r.get("data_changed", ""),
            "id": r["run_id"],
        }
        for _, r in s.iterrows()
    ]
    edited = st.data_editor(
        rows,
        hide_index=True,
        width="stretch",
        disabled=[k for k in rows[0] if k != "compare"],
        key="runs.table",
    )
    return [r["id"] for r in edited if r["compare"]]


def _actions(app, store, runs, backend_for) -> None:
    """Rename, delete, open the project of, re-run one run."""
    ids = runs.ids
    names = dict(zip(ids, runs.summaries["run_name"], strict=True))
    run_id = st.selectbox(
        "Run", ids, format_func=lambda i: f"{names[i]} ({i})", key="runs.one"
    )
    if run_id is None:
        return
    row = runs.summaries.set_index("run_id").loc[run_id]
    loadable = bool(row.get("project_loadable", True))
    if row.get("data_changed"):
        st.warning(
            f"Reference data changed since this run: {row['data_changed']}. "
            "Re-run it to compare with the current data."
        )
    if not loadable:
        st.warning(
            "The project of this run no longer loads with this version of the tool: it can be "
            "compared (stored inputs) but not opened nor re-run."
        )
    c1, c2, c3, c4 = st.columns(4)
    new_name = c1.text_input("New name", names[run_id], key=f"runs.rename.{run_id}")
    if (
        c1.button("Rename", key=f"runs.renamebtn.{run_id}")
        and new_name != names[run_id]
    ):
        store.rename(run_id, new_name)
        st.rerun()
    c2.write("")
    if c2.button(
        "Open the project of this run",
        disabled=not loadable,
        key=f"runs.open.{run_id}",
        help="Load the copy of the project stored with the run into the editor (Pre-sizing page).",
    ):
        run = store.load(run_id)
        source = run.summary.get("project_file")
        app.load(
            run.project().to_dict(),
            Path(source) if source and Path(source).is_file() else None,
        )
        st.session_state["runs.opened"] = run.name
        st.rerun()
    c3.write("")
    if c3.button(
        "Re-run with the current data",
        disabled=not loadable,
        key=f"runs.rerun.{run_id}",
        help="Evaluate the project of the run again and store it as '<name> (re-run)'.",
    ):
        with st.spinner("Evaluating…"):
            try:
                project = store.load(run_id).project()
                store.rerun(run_id, backend=backend_for(project))
                st.rerun()
            except Exception as error:  # ruff: ignore[blind-except]
                st.error(f"Re-run failed: {error}")
                with st.expander("Details"):
                    st.code(traceback.format_exc())
    c4.write("")
    if c4.button("Delete", key=f"runs.delete.{run_id}"):
        store.delete(run_id)
        st.rerun()


def _compare(runs, table) -> None:
    """Varying inputs, comparison table, reference, figures of the selected runs."""
    provenance = runs.provenance()
    if not provenance.empty:
        st.warning(
            "These runs do not share the same tool version or reference data ("
            + ", ".join(provenance.index)
            + "): a difference of outputs may come from the data, not from the inputs."
        )
    varying = runs.varying_inputs()
    st.markdown("**Varying inputs**")
    if varying.empty:
        st.caption("The runs have the same inputs.")
    else:
        table([
            {"input": name, "values": ", ".join(map(str, r["values"]))}
            for name, r in varying.iterrows()
        ])
    outputs_available = [
        c.removeprefix("outputs.")
        for c in runs.summaries.columns
        if c.startswith("outputs.")
    ]
    outputs = st.multiselect(
        "Outputs",
        outputs_available,
        [o for o in KEY_OUTPUTS if o in outputs_available],
        key="runs.outputs",
    )
    st.dataframe(
        runs.to_dataframe(["run_name", *list(varying.index)[:8], *outputs]),
        width="stretch",
    )
    ids = runs.ids
    names = dict(zip(ids, runs.summaries["run_name"], strict=True))
    reference = st.selectbox(
        "Reference run (relative differences)",
        [None, *ids],
        format_func=lambda i: "none" if i is None else names[i],
        key="runs.reference",
    )
    if reference is not None and outputs:
        st.dataframe(
            (100 * runs.compare_to(reference, outputs)).round(2).add_suffix(" (%)"),
            width="stretch",
        )
    mode = st.radio(
        "Figures",
        ["Superpose the runs", "Families along an input"],
        horizontal=True,
        key="runs.mode",
    )
    if mode == "Superpose the runs":
        figures = runs.visualize(
            st.multiselect("Figures", list(FIGURES), list(FIGURES), key="runs.figures")
        )
    else:
        if varying.empty:
            st.info("No input varies between these runs.")
            return
        along = st.selectbox("Along", list(varying.index), key="runs.along")
        families = runs.families(along)
        if len(families.ungrouped):
            st.caption(
                f"{len(families.ungrouped)} runs belong to no family (a single value of {along})."
            )
        if not len(families):
            st.info(f"No family: no runs differing by {along} only.")
            return
        st.dataframe(families.to_dataframe(["run_name", *outputs]), width="stretch")
        figures = families.visualize()
    for name, figure in figures.items():
        st.plotly_chart(figure, width="stretch", key=f"runs.fig.{name}")


def render(app, backend_for, table) -> None:
    """The Runs page."""
    store = RunStore()
    st.caption(f"Folder of the runs: {store.root.resolve()} (studies folder / runs)")
    opened = st.session_state.pop("runs.opened", None)
    if opened:
        st.success(
            f"The project of the run '{opened}' is loaded in the editor: Pre-sizing page."
        )
    runs = store.collection()
    if not len(runs):
        st.info("No stored run yet: press Run, then Save run in the Results tab.")
        return
    filtered = _filters(runs)
    if filtered is None:
        return
    st.markdown(
        f"**{len(filtered)} / {len(runs)} runs** — tick the runs to compare (all by default)."
    )
    if not len(filtered):
        return
    chosen = _selection(filtered)
    selected = filtered.filter(run_id=chosen) if chosen else filtered
    with st.expander("Rename, delete, open, re-run a run"):
        _actions(app, store, selected, backend_for)
    _compare(selected, table)
