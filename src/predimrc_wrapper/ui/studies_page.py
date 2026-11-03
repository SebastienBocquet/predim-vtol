"""Studies page of the GUI: exploration, optimisation and stored studies (INC2-008, INC3-002).

Moved out of the pre-sizing tabs to its own sidebar page; it works on the current project.
"""

from __future__ import annotations

import traceback

import numpy as np
import streamlit as st

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.data import default_database
from predimrc_wrapper.data import default_propellers
from predimrc_wrapper.settings import Settings
from predimrc_wrapper.ui.help import HelpRegistry

HELP = HelpRegistry.default()
TABS = ["Exploration", "Optimisation", "Studies"]
db = default_database()

try:
    from predimrc_wrapper.mdo.explore import explore
    from predimrc_wrapper.mdo.explore import pareto_mask
    from predimrc_wrapper.mdo.explore import study_from_optimisation
    from predimrc_wrapper.mdo.optimise import CONSTRAINTS
    from predimrc_wrapper.mdo.optimise import available_algorithms
    from predimrc_wrapper.mdo.optimise import optimise
    from predimrc_wrapper.mdo.parameters import expand_overrides
    from predimrc_wrapper.mdo.studies import StudyStore
    from predimrc_wrapper.ui import optimisation as opt
    from predimrc_wrapper.ui import studies_view as sv

    MDO = True
except ImportError:  # pragma: no cover - GEMSEO not installed
    MDO = False

TWO_PHASE_OBJECTIVES = {
    "flight_time_v1": "Maximise the flight time at V1",
    "flight_time_v2": "Maximise the flight time at V2",
    "range_v2": "Maximise the range at V2",
    "mass_total": "Minimise the total mass",
    "cost_purchase": "Minimise the purchase cost",
    "cost_per_hour": "Minimise the cost per flight hour",
    "motor_out_tw": "Maximise the motor-out thrust-to-weight",
}


def _choices_ui(project: Project, prefix: str, gen: int, ranges) -> dict[str, list]:
    """Motors and propellers per unit type, cell count."""
    out = {}
    cols = st.columns(len(project.propulsion_units) + 1)
    for col, (name, unit) in zip(cols, project.propulsion_units.items(), strict=False):
        motor_options = list(
            dict.fromkeys([
                unit.motor_id,
                *(
                    next((r.candidates for r in ranges or [] if r.unit == name), None)
                    or db.ids()
                ),
            ])
        )
        motors = col.multiselect(
            f"Motors of '{name}'",
            motor_options,
            default=[unit.motor_id],
            key=f"{gen}:{prefix}.motors.{name}",
            help=HELP.tooltip("propulsion_units.*.motor_id"),
        )
        if motors and motors != [unit.motor_id]:
            out[f"propulsion_units.{name}.motor_id"] = motors
        props = col.multiselect(
            f"Propellers of '{name}' (database)",
            default_propellers().ids(),
            key=f"{gen}:{prefix}.props.{name}",
            help=HELP.tooltip("propulsion_units.*.propeller_id"),
        )
        if props:
            out[f"propulsion_units.{name}.propeller"] = props
    cells = cols[-1].multiselect(
        "Cells in series",
        list(range(2, 13)),
        default=[project.battery.n_series],
        key=f"{gen}:{prefix}.cells",
        help=HELP.tooltip("battery.n_series"),
    )
    if cells and cells != [project.battery.n_series]:
        out["battery.n_series"] = cells
    return out


def _variables_ui(project: Project, prefix: str, gen: int):
    rows = st.session_state.setdefault(
        f"{gen}:{prefix}.rows", opt.default_variables(project)
    )
    edited = st.data_editor(
        rows,
        key=f"{gen}:{prefix}.table",
        hide_index=True,
        width="stretch",
        disabled=["name", "path"],
    )
    return opt.to_parameters(list(edited))


def _apply(app, project: Project, overrides: dict) -> None:
    app.load(
        project.with_overrides(expand_overrides(overrides)).to_dict(), app.source_path
    )
    st.rerun()


def render(app, checked, ranges, backend_for, table) -> None:
    """The Studies page: tabs Exploration, Optimisation, Studies (REQ-UI-008)."""
    gen = app.generation
    tabs = dict(zip(TABS, st.tabs(TABS), strict=False))
    with tabs["Exploration"]:
        if not MDO:
            st.info(
                "The exploration needs GEMSEO: pip install 'predimrc_wrapper[mdo]'."
            )
        elif checked.project is None:
            st.info("The exploration is set up once the project is valid.")
        else:
            project = checked.project
            st.markdown(
                "Design of experiments on the continuous variables × every combination of the categorical "
                "choices, two-phase flight time at each point. The study is stored in the studies folder."
            )
            variables = _variables_ui(project, "exp", gen)
            choices = _choices_ui(project, "exp", gen, ranges)
            c1, c2, c3, c4 = st.columns(4)
            method = c1.selectbox(
                "Design",
                ["lhs", "full_factorial"],
                key=f"{gen}:exp.method",
                help="Latin hypercube (lhs) or full factorial grid.",
            )
            n = int(
                c2.number_input(
                    "Points per combination", 2, 500, 10, key=f"{gen}:exp.n"
                )
            )
            seed = int(c3.number_input("Seed", 0, 10_000, 0, key=f"{gen}:exp.seed"))
            name = c4.text_input(
                "Study name", f"exploration {project.name}", key=f"{gen}:exp.name"
            )
            n_combos = (
                int(np.prod([len(v) for v in choices.values()])) if choices else 1
            )
            st.caption(f"{n_combos} combination(s) × {n} points")
            if st.button("Run the exploration", type="primary"):
                bar = st.progress(0.0, text="Starting…")
                try:
                    study = explore(
                        project,
                        variables,
                        choices,
                        method,
                        n,
                        seed,
                        backend=backend_for(project),
                        name=name,
                        progress=lambda i, t: bar.progress(
                            i / max(t, 1), text=f"Point {i + 1}/{t}"
                        ),
                    )
                    StudyStore(Settings.load().studies_root).save(study)
                    st.session_state["last_exploration"] = study
                    bar.progress(1.0, text=f"Done — saved in {study.path}")
                except Exception as error:  # ruff: ignore[blind-except]
                    st.error(f"Exploration failed: {error}")
                    with st.expander("Details"):
                        st.code(traceback.format_exc())
            study = st.session_state.get("last_exploration")
            if study is not None:
                cols = sv.numeric_columns(study.points)
                c1, c2 = st.columns(2)
                x = c1.selectbox(
                    "x",
                    cols,
                    index=cols.index("mass_total") if "mass_total" in cols else 0,
                    key="exp.x",
                )
                y = c2.selectbox(
                    "y",
                    cols,
                    index=cols.index("flight_time_v2")
                    if "flight_time_v2" in cols
                    else 0,
                    key="exp.y",
                )
                mask = pareto_mask(
                    study.points, [("flight_time_v2", True), ("mass_total", False)]
                )
                st.plotly_chart(
                    sv.scatter_figure([study], x, y, [mask]),
                    width="stretch",
                    key="exp.scatter",
                )
                table(sv.point_rows(study))

    with tabs["Optimisation"]:
        if not MDO:
            st.info(
                "The optimisation needs GEMSEO: pip install 'predimrc_wrapper[mdo]' (gemseo[all] for COBYLA)."
            )
        elif checked.project is None:
            st.info("The optimisation is set up once the project is valid.")
        else:
            project = checked.project
            st.markdown(
                "Outer loop over the categorical choices (motors, propellers, cells), optimiser on the continuous "
                "variables, margins ≥ 0. Two-phase flight time; the study is stored."
            )
            c1, c2, c3 = st.columns(3)
            objective = c1.selectbox(
                "Objective",
                list(TWO_PHASE_OBJECTIVES),
                format_func=TWO_PHASE_OBJECTIVES.get,
                key=f"{gen}:opt.objective",
            )
            algo = c2.selectbox(
                "Algorithm",
                available_algorithms(),
                key=f"{gen}:opt.algo",
                help="SLSQP: gradient by finite differences; NLOPT_COBYLA, COBYQA: gradient-free.",
            )
            max_iter = int(
                c3.number_input(
                    "Iterations per choice", 5, 500, 40, key=f"{gen}:opt.max_iter"
                )
            )
            variables = _variables_ui(project, "opt", gen)
            choices = _choices_ui(project, "opt", gen, ranges)
            constraints = st.multiselect(
                "Constraints (≥ 0)",
                [
                    "margin_motor_power",
                    "margin_motor_current",
                    "margin_hover_thrust",
                    "margin_thrust_to_weight",
                    "margin_battery_c",
                    "margin_mass",
                ],
                default=list(CONSTRAINTS),
                key=f"{gen}:opt.constraints",
            )
            sd_on = st.checkbox(
                "Constrain the surrogate uncertainty (σ_rel ≤ 5 %)",
                value=True,
                key=f"{gen}:opt.sd",
                help=HELP.tooltip("max_sd_rel"),
            )
            if st.button("Run the optimisation", type="primary"):
                bar = st.progress(0.0, text="Starting…")
                try:
                    summary = optimise(
                        project,
                        variables,
                        choices,
                        objective=objective,
                        constraints=tuple(constraints),
                        algo=algo,
                        max_iter=max_iter,
                        backend=backend_for(project),
                        progress=lambda i, n_, c: bar.progress(
                            i / n_, text=f"Combination {i + 1}/{n_}: {c or 'base'}"
                        ),
                        max_sd_rel=0.05 if sd_on else None,
                    )
                    study = study_from_optimisation(
                        summary,
                        project,
                        variables,
                        choices,
                        constraints,
                        algo,
                        max_iter,
                        name=f"optimisation {project.name}",
                        max_sd_rel=0.05 if sd_on else None,
                    )
                    StudyStore(Settings.load().studies_root).save(study)
                    st.session_state["optimisation"] = {
                        "summary": summary,
                        "continuous": variables,
                        "study": study,
                    }
                    bar.progress(
                        1.0,
                        text=f"Done in {summary.seconds:.0f} s — saved in {study.path}",
                    )
                except Exception as error:  # ruff: ignore[blind-except]
                    st.error(f"Optimisation failed: {error}")
                    with st.expander("Details"):
                        st.code(traceback.format_exc())
            stored = st.session_state.get("optimisation")
            if stored:
                summary = stored["summary"]
                best = summary.best
                if best is None:
                    st.error("No combination could be evaluated.")
                else:
                    st.markdown(
                        f"**Best:** {best.choice or 'base design'} — {summary.objective} = "
                        f"{best.outputs[summary.objective]:.4g}, "
                        + ("feasible" if best.feasible else ":red[infeasible]")
                    )
                    if st.button("Apply the best design to the project"):
                        _apply(
                            app, project, summary.best_overrides(stored["continuous"])
                        )
                c1, c2 = st.columns([3, 2])
                with c1:
                    table(sv.point_rows(stored["study"]))
                c2.plotly_chart(
                    opt.history_figure(summary), width="stretch", key="opt.history"
                )

    with tabs["Studies"]:
        if not MDO:
            st.info("The studies need GEMSEO: pip install 'predimrc_wrapper[mdo]'.")
        else:
            store = StudyStore(Settings.load().studies_root)
            listing = store.list()
            st.caption(f"Studies root: `{store.root.resolve()}`")
            if not listing:
                st.info("No study yet: run an exploration or an optimisation.")
            else:
                table([
                    {k: s[k] for k in ("id", "name", "kind", "mode", "date", "points")}
                    for s in listing
                ])
                ids = [s["id"] for s in listing]
                chosen = st.multiselect(
                    "Open (one, or two to compare)",
                    ids,
                    default=ids[:1],
                    max_selections=2,
                    key="studies.open",
                )
                studies = [store.load(i) for i in chosen]
                if studies:
                    cols = sorted(
                        set.intersection(*[
                            set(sv.numeric_columns(s.points)) for s in studies
                        ])
                    )
                    c1, c2 = st.columns(2)
                    x = c1.selectbox(
                        "x",
                        cols,
                        index=cols.index("mass_total") if "mass_total" in cols else 0,
                        key="studies.x",
                    )
                    y = c2.selectbox(
                        "y",
                        cols,
                        index=cols.index("flight_time_v2")
                        if "flight_time_v2" in cols
                        else 0,
                        key="studies.y",
                    )
                    masks = [
                        pareto_mask(
                            s.points, [("flight_time_v2", True), ("mass_total", False)]
                        )
                        for s in studies
                    ]
                    st.plotly_chart(
                        sv.scatter_figure(studies, x, y, masks),
                        width="stretch",
                        key="studies.scatter",
                    )
                    for s in studies:
                        with st.container(border=True):
                            st.markdown(
                                f"**{s.name}** ({s.definition.kind}, {s.definition.mode}) — {s.metadata.get('date')}"
                                + (
                                    " — :orange[data changed since this study]"
                                    if StudyStore.data_changed(s)
                                    else ""
                                )
                            )
                            table(sv.point_rows(s))
                            c1, c2, c3 = st.columns(3)
                            index = int(
                                c1.number_input(
                                    "Point to apply (row)",
                                    0,
                                    max(0, len(s.points) - 1),
                                    0,
                                    key=f"studies.apply.{s.id}",
                                )
                            )
                            if c1.button(
                                "Apply this point to the project",
                                key=f"studies.applybtn.{s.id}",
                            ):
                                _apply(
                                    app,
                                    Project.model_validate(s.base_project),
                                    sv.overrides_of(s, index),
                                )
                            new_name = c2.text_input(
                                "Rename", s.name, key=f"studies.rename.{s.id}"
                            )
                            if (
                                c2.button("Rename", key=f"studies.renamebtn.{s.id}")
                                and new_name != s.name
                            ):
                                store.rename(s.id, new_name)
                                st.rerun()
                            if c3.button("Delete", key=f"studies.delete.{s.id}"):
                                store.delete(s.id)
                                st.rerun()
