"""Streamlit GUI of the designer's workflow (INC2-009). Run with ``predimrc-ui [project.yaml]``."""

from __future__ import annotations

import sys
import traceback
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import templates as user_templates
from predimrc_wrapper.aircraft.project import TEMPLATES
from predimrc_wrapper.aircraft.project import AeroSpec
from predimrc_wrapper.aircraft.project import BatterySpec
from predimrc_wrapper.aircraft.project import BoomSpec
from predimrc_wrapper.aircraft.project import CostSpec
from predimrc_wrapper.aircraft.project import CruiseReference
from predimrc_wrapper.aircraft.project import EnvironmentSpec
from predimrc_wrapper.aircraft.project import FlightPoint
from predimrc_wrapper.aircraft.project import HoverReference
from predimrc_wrapper.aircraft.project import MassItem
from predimrc_wrapper.aircraft.project import MissionSettings
from predimrc_wrapper.aircraft.project import PropulsionSpec
from predimrc_wrapper.aircraft.project import SizingSpec
from predimrc_wrapper.aircraft.project import WiringSpec
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.api import profiles_dir
from predimrc_wrapper.calibration import __doc__ as calibration_doc
from predimrc_wrapper.data import DatabaseError
from predimrc_wrapper.data import add_user_motor
from predimrc_wrapper.data import add_user_propeller
from predimrc_wrapper.data import default_database
from predimrc_wrapper.data import default_propellers
from predimrc_wrapper.data import default_tests
from predimrc_wrapper.data import user_data_dir
from predimrc_wrapper.data.database import USER_FILE as USER_MOTOR_FILE
from predimrc_wrapper.data.importers import add_user_test
from predimrc_wrapper.data.importers import csv_table
from predimrc_wrapper.data.prices import default_prices
from predimrc_wrapper.data.propellers import USER_FILE as USER_PROPELLER_FILE
from predimrc_wrapper.data.tests import COLUMNS as TEST_COLUMNS
from predimrc_wrapper.data.tests import USER_FOLDER as USER_TEST_FOLDER
from predimrc_wrapper.mission.power_budget import budget_rows
from predimrc_wrapper.mission.power_budget import power_budget
from predimrc_wrapper.settings import Settings
from predimrc_wrapper.settings import available_profiles
from predimrc_wrapper.sizing import motor_power_ranges
from predimrc_wrapper.ui import cg_view
from predimrc_wrapper.ui import cost_view as cov
from predimrc_wrapper.ui import cruise_view as cv
from predimrc_wrapper.ui import drag_view as dv
from predimrc_wrapper.ui import explanations
from predimrc_wrapper.ui import forms
from predimrc_wrapper.ui import geometry
from predimrc_wrapper.ui import hover_view as hv
from predimrc_wrapper.ui import mass_view as mv
from predimrc_wrapper.ui import mic_page
from predimrc_wrapper.ui import positions_view
from predimrc_wrapper.ui import prop_sizing as ps
from predimrc_wrapper.ui import propulsion_charts as pc
from predimrc_wrapper.ui import state as ui_state
from predimrc_wrapper.ui import test_data_view as tdv
from predimrc_wrapper.ui import two_phase_view as tpv
from predimrc_wrapper.ui import units as un
from predimrc_wrapper.ui.help import HelpRegistry
from predimrc_wrapper.ui.session import backend_for

st.set_page_config(page_title="PredimRC pre-sizing", layout="wide")
HELP = HelpRegistry.default()
forms.HELP = HELP.tooltip


def table(rows: list[dict] | dict, **kwargs) -> None:
    """A table whose column headers carry the help of the glossary (REQ-UI-010)."""
    if isinstance(rows, dict):
        rows = [
            {"quantity": k, "value": "—" if v is None else str(v)}
            for k, v in rows.items()
        ]
    columns = list(dict.fromkeys(k for r in rows for k in r))
    config = {c: st.column_config.Column(c, help=HELP.tooltip(c)) for c in columns}
    st.dataframe(rows, hide_index=True, width="stretch", column_config=config, **kwargs)


def cost_and_reliability(project: Project, two=None):
    """Cost (flight time of an up-to-date Run, else 0 h) and motor-out hover."""
    from predimrc_wrapper.cost import cost  # noqa: PLC0415
    from predimrc_wrapper.reliability import motor_out  # noqa: PLC0415

    aircraft = AircraftModel(project)
    current = two is not None and not app.outdated
    flight = two.cruise[0].flight_time_s if current else 0.0
    return cost(aircraft, flight), motor_out(aircraft)


OUTDATED = (
    "The project changed since the last Run: the values below are those of the last Run. "
    "Press Run to update them."
)


def metric(col, label: str, text: str, negative: bool = False) -> None:
    col.metric(label, text, help=HELP.tooltip(label))
    if negative:
        col.markdown(":red[negative margin]")


def _initial_state() -> ui_state.AppState:
    args = [
        a
        for a in sys.argv[1:]
        if not a.startswith("-") and Path(a).suffix in (".yaml", ".yml")
    ]
    if args and Path(args[0]).is_file():
        st.session_state.setdefault("configuration", None)
        return ui_state.AppState(ui_state.load_file(args[0]), Path(args[0]))
    st.session_state.setdefault("configuration", "multicopter")
    return ui_state.AppState(ui_state.load_template("multicopter"))


app: ui_state.AppState = st.session_state.setdefault("app", _initial_state())
db = default_database()


def _switch_configuration() -> None:
    name = st.session_state.get("configuration")
    if name:
        app.load(ui_state.load_template(name))


# --- sidebar --------------------------------------------------------------------------
with st.sidebar:
    page = st.radio(
        "Page",
        ["Pre-sizing", "Studies", "Runs", "Model cards (MIC)", "Glossary"],
        key="page",
        horizontal=True,
    )
    st.header("Project")
    upload = st.file_uploader("Open a project file", type=["yaml", "yml"])
    if upload is not None and st.session_state.get("opened") != upload.file_id:
        st.session_state["opened"] = upload.file_id
        st.session_state["configuration"] = None
        app.load(yaml.safe_load(upload.getvalue()), Path(upload.name))
        st.rerun()
    all_templates = user_templates.all_templates()
    if "template.select" in st.session_state:
        # A template just saved becomes the configuration (same data: nothing reloaded).
        st.session_state["configuration"] = st.session_state.pop("template.select")
    if st.session_state.get("configuration") not in (None, *all_templates):
        st.session_state["configuration"] = None
    st.selectbox(
        "Start from a template",
        list(all_templates),
        format_func=all_templates.get,
        key="configuration",
        placeholder="from a project file",
        on_change=_switch_configuration,
        help="Shipped templates (quadplane 4+1, tricopter, quadcopter, tricopter with wing) and your "
        "own templates. Changing it replaces the project.",
    )
    data = app.data
    gen = app.generation
    architecture = data.get("architecture", "multicopter")
    with st.expander("Save as template"):
        st.caption(
            "A template is a complete project file: geometry, propulsion unit types, motors with "
            "their positions and tilt mask, booms, battery, masses, drag sources, wiring, mission, "
            "sizing, test data. Saved templates appear in the list 'Start from a template' above, as "
            "starting points for new projects. Not to be confused with **Save project file** "
            "(bottom of the sidebar), which writes the project you are editing to a YAML file "
            "of your choice, to reopen with 'Open a project file'."
        )
        configuration = st.session_state.get("configuration") or ""
        default_template = (
            configuration.removeprefix(user_templates.USER)
            if configuration.startswith(user_templates.USER)
            else data.get("name", "")
        )
        template_name = st.text_input(
            "Template name",
            default_template,
            key=f"{gen}:template.name:{default_template}",
            help="Pre-filled with the current user template, else the project name.",
        )
        try:
            existing = user_templates.user_path(template_name)
        except ValueError:
            existing = None
        exists = existing is not None and existing.exists()
        if st.button(
            f"Update template '{existing.stem}'" if exists else "Save as new template",
            key="template.save",
            help="Replaces the saved template with the current project."
            if exists
            else None,
        ):
            try:
                path = user_templates.save_user(
                    app.data, template_name, overwrite=exists
                )
                # Rerun so that the template list above shows the new template.
                st.session_state["template.saved"] = str(path)
                st.session_state["template.select"] = user_templates.USER + path.stem
                st.rerun()
            except (ValueError, FileExistsError) as error:
                st.error(str(error))
        if st.session_state.get("template.saved"):
            st.success(f"Saved {st.session_state.pop('template.saved')}")
        own = [k for k in all_templates if k.startswith(user_templates.USER)]
        if own:
            chosen = st.selectbox(
                "Your templates",
                own,
                format_func=lambda k: k.removeprefix(user_templates.USER),
                key="template.chosen",
            )
            new_name = st.text_input("New name", key="template.new_name")
            c1, c2 = st.columns(2)
            if c1.button("Rename", key="template.rename") and new_name:
                try:
                    user_templates.rename_user(chosen, new_name)
                    st.rerun()
                except (ValueError, FileExistsError) as error:
                    st.error(str(error))
            if c2.button("Delete", key="template.delete"):
                user_templates.delete_user(chosen)
                st.rerun()
    with st.expander("Settings (studies and templates folders)"):
        settings = Settings.load()
        root = st.text_input(
            "Studies root folder",
            settings.studies_root,
            key="settings.studies",
            help="Explorations and optimisations are stored in dated sub-folders of this folder.",
        )
        templates_root = st.text_input(
            "User templates folder",
            settings.templates_folder,
            key="settings.templates",
            placeholder="~/.predimrc_wrapper/templates",
            help="Folder of the templates saved with 'Save as template'.",
        )
        cache_file = st.text_input(
            "PredimRC cache file",
            settings.predimrc_cache,
            key="settings.predimrc_cache",
            placeholder="~/.predimrc_wrapper/predimrc_cache.h5",
            help="HDF5 file of the PredimRC evaluations already computed: an evaluation found "
            "there is not run again (Excel is not even started). A modified workbook starts new "
            "entries; delete the file to empty the cache. Needs GEMSEO (mdo extra).",
        )
        if st.button("Save the settings"):
            settings.studies_root, settings.templates_folder = root, templates_root
            settings.predimrc_cache = cache_file
            st.success(f"Saved {settings.save()}")
        st.caption(
            "The PredimRC folder is set in the first tab (winged configurations)."
        )

if page == "Model cards (MIC)":
    st.title("Model identity cards (MIC)")
    cards = mic_page.cards()
    if not cards:
        st.info(
            "The MIC cards are in the repository folder docs/models (development install)."
        )
    else:
        table([{k: c[k] for k in ("id", "title", "verification")} for c in cards])
        chosen = st.selectbox(
            "Card",
            [c["id"] for c in cards],
            format_func=lambda i: (
                f"{i} — " + next(c["title"] for c in cards if c["id"] == i)
            ),
            key="mic.card",
        )
        st.markdown(mic_page.render_text(chosen))
    st.stop()

if page == "Glossary":
    st.title("Glossary of the quantities")
    query = st.text_input("Search", key="glossary.search")
    entries = HELP.search(query) if query else list(HELP.entries.values())
    table([
        {
            "key": e.key,
            "name": e.name,
            "symbol": e.symbol,
            "unit": e.unit,
            "definition": e.definition,
            "default": e.default,
            "source of the default": e.default_source,
            "model card": e.model,
        }
        for e in entries[:500]
    ])
    st.stop()

checked = ui_state.check(data)
ranges = None
if checked.project is not None and checked.project.sizing is not None:
    ranges = motor_power_ranges(checked.project, db)
two = app.two_phase

if page == "Studies":
    from predimrc_wrapper.ui import studies_page  # noqa: E402

    st.title("Studies: exploration, optimisation, stored studies")
    studies_page.render(app, checked, ranges, backend_for, table)
    st.stop()

if page == "Runs":
    from predimrc_wrapper.ui import runs_page  # noqa: E402

    st.title("Runs: stored evaluations, filtered and compared")
    runs_page.render(app, backend_for, table)
    st.stop()

# --- tabs ------------------------------------------------------------------------------
config_label = data.get("name") or "Aircraft configuration"
labels = [
    config_label,
    "Masses and battery",
    "Mission",
    "Cruise",
    "Drag",
    "Hover",
    "Power chain",
    "Propeller sizing",
    "Test data",
    "Results",
    "Cost and reliability",
]
tabs = dict(zip(labels, st.tabs(labels), strict=False))
errors = checked.errors

with tabs[config_label]:
    left, right = st.columns([3, 2])
    with left:
        data["name"] = st.text_input(
            "Project name *",
            data.get("name", ""),
            key=f"{gen}:name",
            help="Name of the project (title of this tab, default file name).",
        )
        st.caption(
            f"Architecture **{architecture}** ({TEMPLATES.get(st.session_state.get('configuration'), 'project file')})."
        )
        if architecture == "quadplane":
            with st.container(border=True):
                st.markdown("**PredimRC workbooks** (wing aerodynamics)")
                settings = Settings.load()
                c1, c2 = st.columns([4, 1])
                folder = c1.text_input(
                    "PredimRC folder",
                    settings.predimrc_folder,
                    key="settings.predimrc",
                    help="Folder of the PredimRC workbooks, one per wing airfoil, named "
                    "PredimRC_<profile>.xls (.xlsx, .xlsm accepted). Saved in your settings, "
                    "not in the project file.",
                )
                if c2.button("Use this folder", key="settings.predimrc.save"):
                    settings.predimrc_folder = folder
                    settings.save()
                    st.rerun()
                profiles = available_profiles()
                current = (data.get("aero") or {}).get("profile", "SD7003")
                st.caption(
                    f"Naming rule: `PredimRC_<profile>.xls` → profiles found in "
                    f"`{profiles_dir().resolve()}`: **{', '.join(profiles) or 'none'}**. "
                    f"Profile of this project: **{current}** (chosen with the wing geometry, "
                    "below)."
                    + (
                        ""
                        if current in profiles
                        else f" :red[No workbook PredimRC_{current}.xls in this folder.]"
                    )
                )
            with st.expander(
                "Wing, stabiliser and fuselage (PredimRC geometry)", expanded=False
            ):
                st.caption(
                    "Labels as in PredimRC (page 3-Geometrie). The accessory surface (S.ac) is "
                    "forced to 0: the parasitic drag is in the Drag tab."
                )
                data["aero"] = forms.render_model(
                    st,
                    AeroSpec,
                    data.get("aero"),
                    "aero",
                    errors,
                    {"aero.profile": available_profiles() or ["SD7003"]},
                    gen,
                )
        winged = architecture == "quadplane"
        units = dict(data.get("propulsion_units") or {})
        with st.expander(
            "Motor layout: positions, roles"
            + (", tilting motors (tilt mask)" if winged else ""),
            expanded=False,
        ):
            st.caption(
                "One motor per arm or boom end, numbered in this order (ArduPilot outputs). Positions "
                "in mm from the reference point "
                + ("(**wing root leading edge**)" if winged else "(**frame centre**)")
                + ": x aft-positive, y right-positive — see the drawing on the right. "
                + (
                    "Role: lift (vertical flight) or cruise (forward flight); the tilting motors are "
                    "chosen below with the tilt mask."
                    if winged
                    else "A multicopter flies forward by tilting the whole frame: every motor lifts, no "
                    "tilting motor (a tricopter's rear motor tilts for yaw only). For tilting motors, "
                    "choose a configuration with a wing (e.g. tricopter with wing)."
                )
            )
            motors_in = data.get("motors") or []
            rows = [
                {
                    "unit": m.get("unit"),
                    "role": "lift" if m.get("role") == "tilt" else m.get("role"),
                    "tilts": m.get("role") == "tilt",
                    "x_mm": m.get("x_mm"),
                    "y_mm": m.get("y_mm"),
                }
                for m in motors_in
            ]
            layout_version = st.session_state.setdefault("layout_version", 0)
            motors_key = f"{gen}:motors:{layout_version}"
            edited = st.data_editor(
                forms.editor_base(st, motors_key, gen, lambda: rows),
                key=motors_key,
                num_rows="dynamic",
                hide_index=False,
                width="stretch",
                column_config={
                    "unit": st.column_config.SelectboxColumn(
                        "unit", options=list(units), help=HELP.tooltip("motors.*.unit")
                    ),
                    "role": st.column_config.SelectboxColumn(
                        "role",
                        options=["lift", "cruise"] if winged else ["lift"],
                        help=HELP.tooltip("motors.*.role"),
                    ),
                    "tilts": st.column_config.CheckboxColumn(
                        "tilts (mask)", help=HELP.tooltip("tilts"), disabled=True
                    ),
                    "x_mm": st.column_config.NumberColumn(
                        "x (mm)", help=HELP.tooltip("motors.*.x_mm")
                    ),
                    "y_mm": st.column_config.NumberColumn(
                        "y (mm)", help=HELP.tooltip("motors.*.y_mm")
                    ),
                },
                column_order=["unit", "role", "tilts", "x_mm", "y_mm"]
                if winged
                else ["unit", "role", "x_mm", "y_mm"],
            )
            data["motors"] = [
                {
                    "unit": r["unit"],
                    "role": "tilt" if r.get("tilts") else (r.get("role") or "lift"),
                    "x_mm": r["x_mm"],
                    "y_mm": r["y_mm"],
                }
                for r in edited
                if r.get("unit") is not None
                and r.get("x_mm") is not None
                and r.get("y_mm") is not None
            ]
            if winged:
                numbers = list(range(1, len(data["motors"]) + 1))
                mask = [
                    i + 1 for i, m in enumerate(data["motors"]) if m["role"] == "tilt"
                ]
                cg = data.get("cg_x_mm")
                ref = (
                    cg
                    if cg is not None
                    else float(np.mean([m["x_mm"] for m in data["motors"]] or [0.0]))
                )
                quick = {
                    "none": [],
                    "front": [
                        i + 1 for i, m in enumerate(data["motors"]) if m["x_mm"] < ref
                    ],
                    "rear": [
                        i + 1 for i, m in enumerate(data["motors"]) if m["x_mm"] > ref
                    ],
                    "all": numbers,
                }
                c1, c2 = st.columns([3, 2])
                chosen = c1.multiselect(
                    "Tilting motors (tilt mask)",
                    numbers,
                    default=[n for n in mask if n in numbers],
                    key=f"{gen}:tiltmask:{layout_version}",
                    help="Motor numbers that tilt: they lift in hover and push in cruise (ArduPilot "
                    "Q_TILT_MASK). The others keep their role. A wing-borne aircraft needs at least "
                    "one motor able to push in cruise (cruise or tilting).",
                )
                pick = c2.selectbox(
                    "Quick choice",
                    ["—", *quick],
                    key=f"{gen}:tiltquick:{layout_version}",
                    help="front / rear: the motors ahead of / behind the CG (or of the mean station).",
                )
                new_mask = quick[pick] if pick != "—" else chosen
                if sorted(new_mask) != sorted(mask):
                    for i, m in enumerate(data["motors"]):
                        if i + 1 in new_mask:
                            m["role"] = "tilt"
                        elif m["role"] == "tilt":
                            m["role"] = "lift"
                    st.session_state["layout_version"] = layout_version + 1
                    app.data = data
                    st.rerun()
        with st.expander(
            "Booms carrying the lift motors", expanded=data.get("booms") is not None
        ):
            st.caption(
                "**Parallel**: booms along the flow carrying the off-centreline lift motors (quadplane "
                "4+1). **Diagonal**: one straight boom per lift motor from an anchor under the "
                "fuselage (or the frame centre). The section sets the drag (Drag tab, cross-flow "
                "model on the frontal area for diagonal booms); the cables follow the booms "
                "(Power chain tab)."
            )
            if st.checkbox(
                "The aircraft has booms",
                value=data.get("booms") is not None,
                key=f"{gen}:booms.on",
            ):
                data["booms"] = forms.render_model(
                    st,
                    BoomSpec,
                    data.get("booms")
                    or {"layout": "parallel" if winged else "diagonal"},
                    "booms",
                    errors,
                    {},
                    gen,
                )
            else:
                data.pop("booms", None)
        c1, c2 = st.columns(2)
        with c1:
            data["cg_x_mm"] = forms.render_field(
                st,
                "cg_x_mm",
                Project.model_fields["cg_x_mm"],
                data.get("cg_x_mm"),
                "cg_x_mm",
                errors,
                {},
                gen,
            )
        with c2:
            data["cg_y_mm"] = forms.render_field(
                st,
                "cg_y_mm",
                Project.model_fields["cg_y_mm"],
                data.get("cg_y_mm", 0.0),
                "cg_y_mm",
                errors,
                {},
                gen,
            )
        if architecture == "quadplane":
            level, text = cg_view.cg_check(
                two.aero_results if two is not None else None,
                data.get("cg_x_mm"),
                (data.get("aero") or {}).get("static_margin_pct"),
            )
            show = {"none": st.caption, "unset": st.info, "ok": st.success}.get(
                level, st.warning
            )
            show(text + (" (last Run)" if two is not None and app.outdated else ""))
            if level in ("unset", "warning") and st.button(
                "Use the PredimRC CG", key=f"{gen}:cg.use_predimrc"
            ):
                app.data["cg_x_mm"] = round(two.aero_results.cg_mm, 1)
                app.generation += 1
                st.rerun()
        units = dict(data.get("propulsion_units") or {})
        st.subheader("Propulsion unit types")
        st.caption(
            "A propulsion unit type is one **motor + propeller + ESC** combination. Each motor of "
            "the table below uses one type, so the motors can differ (e.g. `front` with 12 in "
            "propellers, `rear` with 10 in). Add a type to give some motors another motor or "
            "propeller. A type can be renamed (its motors follow) or removed (its motors take "
            "the type you choose)."
        )
        only_in_range = bool(ranges) and st.checkbox(
            "Offer only the motors in the power range",
            value=True,
            key=f"{gen}:only_in_range",
        )
        choices = {}
        for name in units:
            candidates = next(
                (r.candidates for r in ranges or [] if r.unit == name), None
            )
            choices[f"propulsion_units.{name}.motor_id"] = (
                candidates if only_in_range and candidates is not None else db.ids()
            )
            choices[f"propulsion_units.{name}.propeller_id"] = [
                None,
                *default_propellers().ids(),
            ]
        columns = st.columns(max(1, min(3, len(units))))
        for i, name in enumerate(list(units)):
            with columns[i % len(columns)], st.container(border=True):
                st.markdown(f"**{name}**")
                motor_before = units[name].get("motor_id")
                if units[name].get("motor_mass_g") is None and motor_before in db.ids():
                    # Pre-filled with the database mass, editable (e.g. weighed motor).
                    units[name] = {
                        **units[name],
                        "motor_mass_g": round(1000 * db.motor(motor_before).mass_kg, 1),
                    }
                units[name] = forms.render_model(
                    st,
                    PropulsionSpec,
                    units[name],
                    f"propulsion_units.{name}",
                    errors,
                    choices,
                    gen,
                )
                motor_after = units[name].get("motor_id")
                if motor_after != motor_before and motor_after in db.ids():
                    # Another motor: its database mass replaces the pre-filled one.
                    units[name]["motor_mass_g"] = round(
                        1000 * db.motor(motor_after).mass_kg, 1
                    )
                    data["propulsion_units"] = units
                    app.generation += 1
                    st.rerun()
                with st.expander(f"Rename or remove '{name}'"):
                    new_name = st.text_input(
                        "New name", name, key=f"{gen}:rename_unit.{name}"
                    )
                    others = [u for u in units if u != name]
                    n_users = sum(
                        m.get("unit") == name for m in data.get("motors") or []
                    )
                    replacement = (
                        st.selectbox(
                            f"Type of its {n_users} motor(s) once removed",
                            others,
                            key=f"{gen}:replace_unit.{name}",
                        )
                        if n_users and others
                        else None
                    )
                    c1, c2 = st.columns(2)
                    action = (
                        "rename"
                        if c1.button("Rename", key=f"{gen}:rename_unit_go.{name}")
                        else "remove"
                        if c2.button(
                            "Remove",
                            key=f"{gen}:remove_unit.{name}",
                            disabled=not others,
                            help=None if others else "The last type cannot be removed.",
                        )
                        else None
                    )
                    if action:
                        data["propulsion_units"] = units
                        try:
                            if action == "rename":
                                ui_state.rename_unit(data, name, new_name)
                            else:
                                ui_state.remove_unit(data, name, replacement)
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            # The motors table shows the new names.
                            st.session_state["layout_version"] = (
                                st.session_state.get("layout_version", 0) + 1
                            )
                            st.rerun()
        c1, c2 = st.columns([3, 1])
        new_unit = c1.text_input(
            "Add a propulsion unit type: its name",
            key=f"{gen}:new_unit",
            placeholder="e.g. rear",
            help="Name of the new type (copied from the first type, then edit it). Use it in "
            "the 'unit' column of the motors.",
        )
        if c2.button("Add the type") and new_unit and new_unit not in units:
            units[new_unit] = (
                dict(next(iter(units.values())))
                if units
                else {"motor_id": db.ids()[0], "prop_diameter_in": 10.0}
            )
            data["propulsion_units"] = units
            st.rerun()
        data["propulsion_units"] = units

        with st.expander("Add a custom motor to the database"):
            st.caption(
                f"Saved in `{user_data_dir() / USER_MOTOR_FILE}`, merged with the shipped motors "
                "and offered in the motor lists of the propulsion unit types (untick 'Offer only "
                "the motors in the power range' if it is outside the range). Values from the data "
                "sheet, in its units. Only the fields marked * are used by the computations."
            )
            with st.form(f"{gen}:custom_motor", clear_on_submit=False):
                c1, c2, c3 = st.columns(3)
                motor_id = c1.text_input(
                    "id *",
                    key=f"{gen}:custom_motor.id",
                    placeholder="e.g. sunnysky-x2216-880kv",
                )
                manufacturer = c2.text_input(
                    "Manufacturer", key=f"{gen}:custom_motor.manufacturer"
                )
                motor_range = c3.text_input(
                    "Product line (range)",
                    key=f"{gen}:custom_motor.range",
                    placeholder="e.g. MN, AT",
                )
                c1, c2, c3 = st.columns(3)
                role = c1.selectbox(
                    "Role (data sheet)",
                    ["lift", "cruise"],
                    key=f"{gen}:custom_motor.role",
                )
                kv = c2.number_input(
                    "Kv (rpm/V) *",
                    key=f"{gen}:custom_motor.kv",
                    min_value=1.0,
                    value=900.0,
                )
                rm_mohm = c3.number_input(
                    "Rm (mΩ) *",
                    key=f"{gen}:custom_motor.rm_mohm",
                    min_value=0.1,
                    value=100.0,
                )
                c1, c2, c3 = st.columns(3)
                i0_a = c1.number_input(
                    "I0 (A) *",
                    key=f"{gen}:custom_motor.i0_a",
                    min_value=0.01,
                    value=0.5,
                )
                i_max_a = c2.number_input(
                    "Imax (A) *",
                    key=f"{gen}:custom_motor.i_max_a",
                    min_value=0.1,
                    value=15.0,
                )
                p_max_w = c3.number_input(
                    "Pmax (W) *",
                    key=f"{gen}:custom_motor.p_max_w",
                    min_value=1.0,
                    value=200.0,
                )
                c1, c2, c3 = st.columns(3)
                mass_g = c1.number_input(
                    "Mass (g) *",
                    key=f"{gen}:custom_motor.mass_g",
                    min_value=0.1,
                    value=60.0,
                )
                status = c2.selectbox(
                    "Status",
                    ["estimated", "verified"],
                    key=f"{gen}:custom_motor.status",
                    help="verified: copied from the source; estimated: otherwise.",
                )
                use_for = c3.selectbox(
                    "Use it for the type",
                    ["(none)", *units],
                    key=f"{gen}:custom_motor.use_for",
                    help="Optional.",
                )
                source = st.text_input(
                    "Source",
                    key=f"{gen}:custom_motor.source",
                    placeholder="URL of the data sheet, or 'own measurement' (default: user entry)",
                )
                notes = st.text_input("Notes", key=f"{gen}:custom_motor.notes")
                if st.form_submit_button("Add the motor"):
                    try:
                        add_user_motor({
                            "id": motor_id.strip(),
                            "manufacturer": manufacturer.strip(),
                            "range": motor_range.strip(),
                            "role": role,
                            "kv": kv,
                            "rm_mohm": rm_mohm,
                            "i0_a": i0_a,
                            "i_max_a": i_max_a,
                            "p_max_w": p_max_w,
                            "mass_g": mass_g,
                            "source": source.strip(),
                            "retrieved": date.today(),
                            "status": status,
                            "notes": notes.strip(),
                        })
                    except DatabaseError as error:
                        st.error(str(error))
                    else:
                        if use_for in units:
                            units[use_for] = {
                                **units[use_for],
                                "motor_id": motor_id.strip(),
                                "motor_mass_g": mass_g,
                            }
                            data["propulsion_units"] = units
                        app.generation += 1
                        st.rerun()

        with st.expander("Motor pre-selection from a target mass range"):
            st.markdown(r"""
**What it is for**: before choosing a motor, narrow the database to the motors whose maximum power fits the aircraft.
For each propulsion unit type it gives a power range [needed at the minimum target mass ; headroom × needed at the
maximum target mass] and offers only the motors inside it (MIC-CFG-SIZ).

**Formula**, for a take-off mass m:
1. Hover battery power of the whole aircraft, scaled from a reference aircraft (your tricopter by default:
   m_ref = 1.87 kg, P_ref = 280 W): **P_h(m) = P_ref · (m / m_ref)^k** (k = 1 when the propellers grow with the
   aircraft, 1.5 with the same propellers).
2. Share of motor i: its hover thrust T_i comes from the balance of forces and moments about the CG; the momentum
   power of a rotor grows as T^1.5 / √A (A = disc area), so **s_i = (T_i^1.5 / √A_i) / Σ_j (T_j^1.5 / √A_j)**.
3. Power motor i must deliver at the minimum thrust-to-weight (full thrust at fixed propeller, P ∝ T^1.5):
   **P_i(m) = s_i · P_h(m) · (T/W_min)^1.5**.
4. Cruise motor of a winged aircraft: **P_c = m·g·V_max / ((L/D)·η)** shared by disc area; a tilting motor takes the
   larger of both.

It depends on the propellers through their disc areas (diameters), not on their pitch, nor on the motors.""")
            sizing = data.get("sizing")
            if st.checkbox(
                "Use a target mass range",
                value=sizing is not None,
                key=f"{gen}:sizing.on",
            ):
                sizing = dict(sizing or {"target_mass_kg": [1.5, 2.5]})
                low, high = (sizing.get("target_mass_kg") or [1.5, 2.5])[:2]
                c1, c2 = st.columns(2)
                low = c1.number_input(
                    "Target mass min (kg) *",
                    value=float(low),
                    min_value=0.05,
                    key=f"{gen}:sizing.min",
                    help=HELP.tooltip("sizing.target_mass_kg"),
                )
                high = c2.number_input(
                    "Target mass max (kg) *",
                    value=float(high),
                    min_value=0.05,
                    key=f"{gen}:sizing.max",
                    help=HELP.tooltip("sizing.target_mass_kg"),
                )
                out = forms.render_model(
                    st,
                    SizingSpec,
                    sizing,
                    "sizing",
                    errors,
                    {},
                    gen,
                    skip=("target_mass_kg",),
                )
                data["sizing"] = {"target_mass_kg": [low, high], **out}
            else:
                data.pop("sizing", None)
            if ranges:
                table(pc.range_rows(ranges))
        with st.expander(
            "Reference motor data (all the motors of the database; the 'fits unit types' column uses the "
            "pre-selection above)"
        ):
            table(pc.motor_rows(db, ranges))
    with right:
        # Validated again here: the drawings follow the table edits of this very run.
        current = ui_state.check(data)
        st.plotly_chart(
            positions_view.positions_figure(
                data.get("motors") or [],
                data.get("propulsion_units") or {},
                architecture == "quadplane",
                data.get("cg_x_mm"),
            ),
            width="stretch",
            key="config.positions",
        )
        overlap = [m for m in current.errors.values() if "overlap" in m]
        if overlap:
            st.error(overlap[0])
        if current.project is not None:
            st.plotly_chart(
                geometry.top_view(current.project), width="stretch", key="config.top"
            )
            st.plotly_chart(
                geometry.front_view(current.project),
                width="stretch",
                key="config.front",
            )
        else:
            st.info("The top and front views are drawn once the project is valid.")

with tabs["Masses and battery"]:
    left, right = st.columns(2)
    with left:
        st.subheader("Battery")
        battery = dict(data.get("battery") or {})
        mode = forms.render_field(
            st,
            "mode",
            BatterySpec.model_fields["mode"],
            battery.get("mode", "mass"),
            "battery.mode",
            errors,
            {},
            gen,
        )
        hidden = "capacity_mah" if mode == "mass" else "mass_g"
        out = forms.render_model(
            st, BatterySpec, battery, "battery", errors, {}, gen, skip=("mode", hidden)
        )
        # The other quantity is kept (hidden) so that switching back restores it.
        data["battery"] = {
            **({hidden: battery[hidden]} if battery.get(hidden) is not None else {}),
            **out,
            "mode": mode,
        }
        battery_info = st.empty()
        info = Project.model_fields["max_takeoff_mass_kg"]
        data["max_takeoff_mass_kg"] = forms.render_field(
            st,
            "max_takeoff_mass_kg",
            info,
            data.get("max_takeoff_mass_kg"),
            "max_takeoff_mass_kg",
            errors,
            {},
            gen,
        )
    with right:
        st.subheader("Mass items")
        data["mass_items"] = forms.render_items(
            st, MassItem, data.get("mass_items") or [], "mass_items", errors, gen
        )
        # Validated again here: the masses follow the edits of this very run, without Run.
        current = ui_state.check(data)
        if current.project is not None:
            battery_info.info(mv.battery_text(AircraftModel(current.project)))
            mass = AircraftModel(current.project).mass
            fig = go.Figure(
                go.Bar(
                    x=[1000 * v for v in mass["breakdown"].values()],
                    y=list(mass["breakdown"]),
                    orientation="h",
                )
            )
            fig.update_layout(
                title=f"Mass breakdown — total {mass['total_kg']:.3f} kg",
                xaxis_title="mass (g)",
                height=300,
                margin={"l": 10, "r": 10, "t": 40, "b": 10},
            )
            st.plotly_chart(fig, width="stretch")
            st.markdown("**Mass recap by component**")
            table(mv.mass_rows(AircraftModel(current.project)))
        else:
            st.info("The mass recap is drawn once the project is valid.")

with tabs["Mission"]:
    left, right = st.columns(2)
    with left:
        st.subheader("Two-phase flight time")
        mission = dict(data.get("mission") or {})
        data["mission"] = forms.render_model(
            st,
            MissionSettings,
            mission,
            "mission",
            errors,
            {},
            gen,
            skip=("target_speeds_m_s", "transition_factor"),
        )
        auto = st.checkbox(
            "Target speeds: minimum aerodynamic power (V1) and maximum L/D (V2)",
            value=not mission.get("target_speeds_m_s"),
            key=f"{gen}:mission.speeds_auto",
            help=HELP.tooltip("mission.target_speeds_m_s"),
        )
        if not auto:
            v1, v2 = (mission.get("target_speeds_m_s") or [12.0, 15.0])[:2]
            c1, c2 = st.columns(2)
            data["mission"]["target_speeds_m_s"] = [
                un.m_s(
                    c1.number_input(
                        "V1 (km/h)",
                        value=round(un.kmh(float(v1)), 1),
                        min_value=3.6,
                        key=f"{gen}:mission.v1",
                        help=HELP.tooltip("V1"),
                    )
                ),
                un.m_s(
                    c2.number_input(
                        "V2 (km/h)",
                        value=round(un.kmh(float(v2)), 1),
                        min_value=3.6,
                        key=f"{gen}:mission.v2",
                        help=HELP.tooltip("V2"),
                    )
                ),
            ]
    with right:
        st.subheader("Environment")
        data["environment"] = forms.render_model(
            st, EnvironmentSpec, data.get("environment"), "environment", errors, {}, gen
        )
with tabs["Cruise"]:
    if architecture != "quadplane":
        st.info(
            "A multicopter does not use PredimRC: its cruise uses the body drag area (Drag tab) and the "
            "forward-flight model; the target speeds are its best-endurance and best-range speeds."
        )
    else:
        st.caption(
            f"PredimRC folder `{profiles_dir().resolve()}` — profiles: {', '.join(available_profiles()) or 'none'}. "
            "Accessory surface (S.ac) forced to 0: the parasitic drag is in the Drag tab."
        )
        st.caption(
            "Wing, stabiliser and fuselage are entered in the first tab (PredimRC geometry)."
        )
        if two is None or two.curve is None:
            st.info("Press Run to compute the PredimRC curves.")
        else:
            passed, message = cv.iso_text(two)
            (st.success if passed else st.warning)(message)
            table(cv.results_rows(two))
            st.subheader("Stabilité longitudinale (PredimRC, Cz de réglage)")
            table(cv.stability_rows(two))
            c1, c2 = st.columns(2)
            c1.plotly_chart(cv.power_figure(two), width="stretch")
            c2.plotly_chart(cv.imposed_figure(two), width="stretch")
            st.plotly_chart(cv.palier_figure(two), width="stretch")

with tabs["Drag"]:
    st.caption(
        "The PredimRC accessory drag is set to 0: every parasitic drag outside the PredimRC airframe is a "
        "source below (shapes Profilé / Mixte / Non profilé with the PredimRC C_d)."
    )
    if architecture == "multicopter":
        st.subheader("Body drag in cruise")
        st.caption(
            "Drag of the body (frame, battery, payload) when the multicopter flies forward: C_d of the shape "
            "(PredimRC values) × frontal area, or a C_d / CdS entered (advanced)."
        )
        from predimrc_wrapper.data.drag_shapes import drag_shapes as _shapes  # noqa: E402

        c1, c2 = st.columns(2)
        with c1:
            data["body_shape"] = forms.render_field(
                st,
                "body_shape",
                Project.model_fields["body_shape"],
                data.get("body_shape", "Non profilé"),
                "body_shape",
                errors,
                {"body_shape": list(_shapes())},
                gen,
            )
        with c2:
            data["body_frontal_area_dm2"] = forms.render_field(
                st,
                "body_frontal_area_dm2",
                Project.model_fields["body_frontal_area_dm2"],
                data.get("body_frontal_area_dm2"),
                "body_frontal_area_dm2",
                errors,
                {},
                gen,
            )
        with st.expander("Advanced: C_d or CdS entered"):
            for name in ("body_cd", "body_cds_m2"):
                data[name] = forms.render_field(
                    st,
                    name,
                    Project.model_fields[name],
                    data.get(name),
                    name,
                    errors,
                    {},
                    gen,
                )
        if checked.project is not None:
            st.info("Body drag model: " + checked.project.body_drag()[1])
    if checked.project is not None and checked.project.booms is not None:
        st.subheader("Booms (set in the configuration tab)")
        st.markdown(
            "Diagonal booms: **cross-flow principle** on the frontal area (Hoerner, *Fluid-Dynamic "
            "Drag*): the flow component normal to the boom sets the force, plus the skin friction."
        )
        st.latex(dv.BOOM_DRAG_LATEX)
        st.caption(
            "θ_i: angle between boom i and the flow, t: thickness seen by the flow, L_i: boom "
            "length, p: perimeter of the section. Parallel booms (along the flow): skin friction "
            "plus base drag of the section."
        )
        table(dv.boom_rows(checked.project, two))
        if any(s_.kind == "boom" for s_ in checked.project.drag_sources):
            st.warning(
                "A drag source of kind 'boom' is also listed below: the booms are then counted "
                "twice. Remove it, the booms of the configuration tab replace it."
            )
    st.subheader("Parasitic drag sources")
    from predimrc_wrapper.data.drag_shapes import drag_shapes  # noqa: E402

    st.caption(
        "One form per source with the fields of its type. Choose the type of a new source in the "
        "list, then Add; the source drag areas are in the table below."
    )
    data["drag_sources"] = data.get("drag_sources") or []
    data["drag_sources"] = dv.render_sources(
        st,
        data["drag_sources"],
        errors,
        gen,
        list(drag_shapes()),
        len(data.get("motors") or []),
    )
    if checked.project is not None and checked.project.drag_sources:
        from predimrc_wrapper.aircraft.drag_sources import drag_report  # noqa: E402

        rho = AircraftModel(checked.project).rho
        v1 = two.cruise[0].v_m_s if two is not None else None
        rows = []
        for r in drag_report(checked.project):
            row = {
                "source": r.name,
                "kind": r.kind,
                "model": r.model,
                "formula": r.formula,
                "frontal area (dm²)": None
                if not np.isfinite(r.frontal_area_m2)
                else round(100 * r.frontal_area_m2, 3),
                "area from": r.area_from,
                "C_d": None if not np.isfinite(r.cd) else r.cd,
                "CdS (dm²)": round(100 * r.cds_m2, 4),
                "coefficient source": r.coefficient_source,
            }
            if v1 is not None:
                row["drag power at V1 (W)"] = round(0.5 * rho * v1**3 * r.cds_m2, 2)
            rows.append(row)
        table(rows)

with tabs["Power chain"]:
    from predimrc_wrapper.ui import wiring_view as wv  # noqa: E402

    left, right = st.columns([2, 3])
    with left:
        st.markdown(wv.TERMS)
        st.caption(
            "The values below are the defaults used until you change them (no need to enter everything). "
            + (
                "Lift ESC position: % of the **arm length** from the frame centre for separate ESCs; a 4-in-1 "
                "board sits at the frame centre."
                if architecture == "multicopter"
                else "ESC positions: % of the **fuselage length** from the nose."
            )
        )
        skip = ("overrides",) + (
            ("cruise_esc_position_pct", "cruise_on_four_in_one")
            if architecture == "multicopter"
            else ()
        )
        wiring = forms.render_model(
            st,
            WiringSpec,
            data.get("wiring") or {},
            "wiring",
            errors,
            {},
            gen,
            skip=skip,
        )
        with st.expander(
            "Cable lengths entered per motor (replace the lengths from the geometry)"
        ):
            from predimrc_wrapper.aircraft.project import BranchOverride  # noqa: E402

            wiring["overrides"] = forms.render_items(
                st,
                BranchOverride,
                (data.get("wiring") or {}).get("overrides") or [],
                "wiring.overrides",
                errors,
                gen,
            )
        data["wiring"] = wiring
    with right:
        if checked.project is not None:
            st.plotly_chart(
                wv.diagram(checked.project), width="stretch", key="chain.diagram"
            )
            rows = wv.cable_rows(checked.project)
            st.markdown(
                f"**Cables: {sum(r['mass (g)'] for r in rows):.0f} g** (copper and silicone "
                "insulation, counted in the mass budget as 'wiring')"
            )
            table(rows)
        if two is not None:
            st.markdown(
                "**Losses per segment** (W) at hover, V1, V2 — segments inside the test data marked"
            )
            chain_rows = tpv.chain_rows(two)
            table(chain_rows)
            points = [c for c in chain_rows[0] if c.endswith("loss (W)")]
            fig = go.Figure([
                go.Bar(
                    name=p.replace(" loss (W)", ""),
                    x=[r["segment"] for r in chain_rows],
                    y=[r[p] for r in chain_rows],
                )
                for p in points
            ])
            fig.update_layout(
                barmode="group",
                yaxis_title="loss (W)",
                height=380,
                margin={"l": 10, "r": 10, "t": 30, "b": 10},
            )
            st.plotly_chart(fig, width="stretch", key="chain.losses")
        else:
            st.info("Press Run to compute the losses.")

data = {k: v for k, v in data.items() if v is not None and v != {}}
app.data = data
checked = ui_state.check(data)

with tabs["Hover"]:
    if two is not None and app.outdated:
        st.warning(OUTDATED)
    if two is None:
        st.info("Press Run to compute the hover operating points.")
    else:
        st.markdown(
            f"Thrust of each lift motor from the mass and the balance of moments about the CG "
            f"(x = {two.hover.cg_x_mm:.0f} mm). **Front / rear thrust ratio "
            f"{tpv.fmt(two.hover.front_rear_ratio, '.2f')}**; hover battery power "
            f"{two.hover.battery_power_w:.0f} ± {two.hover.battery_power_sd_w:.0f} W."
        )
        mission = checked.project.mission if checked.project is not None else None
        tilting = {
            i
            for i, m in enumerate(checked.project.motors if mission else [])
            if m.role == "tilt"
        }
        notes = []
        if two.landing is not None:
            notes.append(
                f"**landing**, hover at the end of the flight with the battery at the "
                f"reserve ({two.reserve_fraction:.0%} state of charge): open-circuit voltage "
                "and internal resistance of the pack at that state of charge, bus "
                f"{two.landing.chain.bus_voltage_v:.2f} V (hover "
                f"{two.hover.chain.bus_voltage_v:.2f} V), {two.landing.battery_power_w:.0f} W "
                "(MIC-PROP-BAT)"
            )
        if two.transition is not None and mission is not None and tilting:
            notes.append(
                f"**transition**, the tilting motors at {mission.transition_tilt_deg:g}° for "
                f"{mission.transition_time_s:g} s: a tilting motor gives T·sin θ vertically, so "
                "to carry its hover share F it gives T = F / sin θ = F × "
                f"{1 / np.sin(np.radians(mission.transition_tilt_deg)):.3f} (no wing lift "
                f"yet, start of the transition), {two.transition.battery_power_w:.0f} W"
            )
        if two.yaw_cases and mission is not None:
            notes.append(
                f"**worst case yaw**, the {mission.yaw_tilt} yaw-tilting motors at the yaw "
                f"tilt {mission.yaw_tilt_max_deg:g}° "
                + (
                    "differential, added to the transition tilt on one side (sin(θ − δ)) "
                    "and taken off on the other (sin(θ + δ))"
                    if mission.yaw_tilt == "front"
                    else "lateral, orthogonal to the transition tilt (sin θ · cos δ)"
                )
                + " (T = F / k)"
            )
        if notes:
            st.markdown(
                "Rows after the hover ones: "
                + "; ".join(notes)
                + ". The worst values of this table are the margin tiles of the Results tab."
            )
        if mission is not None:
            st.caption(
                "**Margins without safety factor**: power, current and thrust margin, at the "
                "thrust of the row. **Margins with the safety factor T/W min = "
                f"{mission.min_thrust_to_weight:g}** (Mission tab): the 'with T/W min' columns, "
                "at the thrust of the row × T/W min (download factor removed); they must stay "
                "≥ 0, and the worst hover row is the 'Margin thrust-to-weight' tile."
            )
        table(
            tpv.hover_tilt_rows(
                two,
                tilting,
                mission.transition_tilt_deg,
                mission.yaw_tilt,
                mission.yaw_tilt_max_deg,
            )
            if mission is not None
            else tpv.hover_rows(two)
        )
        if two.climb is not None and mission is not None:
            with st.expander(
                f"Climb to {mission.transition_altitude_m:g} m at "
                f"{mission.vertical_climb_speed_m_s:g} m/s: "
                f"{two.climb.battery_power_w:.0f} W"
            ):
                st.caption(
                    "Each rotor at its hover thrust with the momentum-theory climb factor "
                    "k_c = v_c/(2v_h) + √((v_c/(2v_h))² + 1) on its power."
                )
                table(tpv.hover_rows(two, two.climb))
        for pair, motors in hv.pairs(two).items():
            with st.container(border=True):
                st.plotly_chart(
                    hv.pair_figure(two, pair), width="stretch", key=f"hover.{pair}"
                )
                near = hv.points_near_rows(motors[0])
                if near:
                    st.caption("Test points closest to the operating thrust")
                    table(near)
                else:
                    st.caption(
                        "No test data for this pair: power predicted from similar pairs (larger uncertainty)."
                    )
    with st.expander(
        "Error guarantee of the thrust–power surrogate (validation on the stored data)"
    ):
        summary, per_pair = hv.validation_rows()
        table(summary)
        table(per_pair)
    with st.expander("Thrust–power test data (manufacturer tables)"):
        table([
            {
                "test": t.id,
                "motor": t.motor_id,
                "propeller": t.propeller_id,
                "voltage (V)": t.voltage_v,
                "points": len(t.thrust_n),
                "measured at": t.measured_at,
                "ESC": t.esc,
                "source": t.source,
            }
            for t in default_tests().records.values()
        ])
    with st.expander("Add a propeller to the database (for a test or a unit type)"):
        st.caption(
            f"Saved in `{user_data_dir() / USER_PROPELLER_FILE}`, merged with the shipped "
            "propellers. Only the fields marked * are used by the computations."
        )
        with st.form("propeller_add"):
            c1, c2, c3, c4 = st.columns(4)
            prop_id = c1.text_input(
                "id *", key="propeller_add.id", placeholder="e.g. apc-10x4.5mr"
            )
            prop_d = c2.number_input(
                "Diameter (in) *", min_value=1.0, value=10.0, key="propeller_add.d"
            )
            prop_p = c3.number_input(
                "Pitch (in) *", min_value=0.5, value=4.5, key="propeller_add.p"
            )
            prop_blades = c4.number_input(
                "Blades *", min_value=2, value=2, step=1, key="propeller_add.blades"
            )
            c1, c2, c3, c4 = st.columns(4)
            prop_manufacturer = c1.text_input(
                "Manufacturer", key="propeller_add.manufacturer"
            )
            prop_name = c2.text_input(
                "Name", key="propeller_add.name", placeholder="default: the id"
            )
            prop_mass = c3.number_input(
                "Mass (g)", min_value=0.0, value=None, key="propeller_add.mass"
            )
            prop_status = c4.selectbox(
                "Status", ["estimated", "verified"], key="propeller_add.status"
            )
            prop_source = st.text_input(
                "Source",
                key="propeller_add.source",
                placeholder="URL of the data sheet (default: user entry)",
            )
            if st.form_submit_button("Add the propeller"):
                try:
                    add_user_propeller({
                        "id": prop_id.strip(),
                        "manufacturer": prop_manufacturer.strip(),
                        "name": prop_name.strip(),
                        "diameter_in": prop_d,
                        "pitch_in": prop_p,
                        "n_blades": int(prop_blades),
                        "mass_g": prop_mass or None,
                        "source": prop_source.strip(),
                        "retrieved": date.today(),
                        "status": prop_status,
                    })
                except DatabaseError as error:
                    st.error(str(error))
                else:
                    st.session_state["propeller_add.done"] = prop_id.strip()
                    st.rerun()
        if done := st.session_state.pop("propeller_add.done", None):
            st.success(f"Propeller '{done}' added.")
    with st.expander("Add a thrust–power test (fitted by the surrogate)"):
        st.caption(
            f"Saved in `{user_data_dir() / USER_TEST_FOLDER}`. The surrogate is fitted again on "
            "the shipped and user tests at the next Run, and the hover powers of this motor + "
            "propeller pair then follow the test (and those of similar pairs too). Motor or "
            "propeller missing: add it first (Configuration tab for a motor, above for a "
            "propeller). Rows: one per throttle step; power empty = voltage × current."
        )
        c1, c2, c3 = st.columns(3)
        test_motor = c1.selectbox("Motor *", db.ids(), key="test_add.motor")
        test_prop = c2.selectbox(
            "Propeller *", default_propellers().ids(), key="test_add.propeller"
        )
        test_voltage = c3.number_input(
            "Voltage of the table (V) *",
            min_value=0.1,
            value=14.8,
            key="test_add.voltage",
            help="Nominal voltage; the voltage column, when filled, gives each row's.",
        )
        c1, c2, c3 = st.columns(3)
        test_measured_at = c1.selectbox(
            "Power measured at",
            ["motor_input", "esc_input"],
            key="test_add.measured_at",
            help="esc_input: the ESC loss is inside the power (the table names an ESC).",
        )
        default_test_id = f"{test_motor}__{test_prop}__{test_voltage:g}v"
        test_id = c2.text_input(
            "id", key="test_add.id", placeholder=f"default: {default_test_id}"
        )
        test_status = c3.selectbox(
            "Status", ["estimated", "verified"], key="test_add.status"
        )
        c1, c2 = st.columns(2)
        test_source = c1.text_input(
            "Source",
            key="test_add.source",
            placeholder="URL of the table, or 'own bench' (default: user entry)",
        )
        test_esc = c2.text_input("ESC", key="test_add.esc", placeholder="optional")
        upload = st.file_uploader(
            "CSV (optional): fills the table below",
            type="csv",
            key="test_add.csv",
            help="First line = column names among "
            + ", ".join(TEST_COLUMNS)
            + " (also throttle, thrust_n).",
        )
        if upload is not None:
            try:
                csv_columns, csv_rows = csv_table(upload.getvalue().decode("utf-8"))
            except ValueError as error:
                st.error(f"Unreadable CSV: {error}")
                csv_columns, csv_rows = [], []
        else:
            csv_columns, csv_rows = [], []
        edit_columns = [c for c in TEST_COLUMNS if c != "torque_nm"]
        frame = pd.DataFrame(
            [
                [
                    r[csv_columns.index(c)] if c in csv_columns else None
                    for c in edit_columns
                ]
                for r in csv_rows
            ]
            or [[None] * len(edit_columns)] * 5,
            columns=edit_columns,
            dtype=float,
        )
        edited = st.data_editor(
            frame,
            num_rows="dynamic",
            key=f"test_add.rows.{upload.file_id if upload is not None else 'manual'}",
            column_config={
                "throttle_pct": st.column_config.NumberColumn("throttle (%)"),
                "voltage_v": st.column_config.NumberColumn("voltage (V)"),
                "current_a": st.column_config.NumberColumn("current (A) *"),
                "power_w": st.column_config.NumberColumn("power (W)"),
                "thrust_g": st.column_config.NumberColumn("thrust (g) *"),
                "rpm": st.column_config.NumberColumn("rpm"),
            },
        )
        if st.button("Add the test", key="test_add.go"):
            columns, rows = hv.typed_test_rows(edited, test_voltage)
            try:
                add_user_test({
                    "id": test_id.strip() or default_test_id,
                    "motor_id": test_motor,
                    "propeller_id": test_prop,
                    "esc": test_esc.strip() or None,
                    "measured_at": test_measured_at,
                    "voltage_v": test_voltage,
                    "source": test_source.strip(),
                    "retrieved": date.today(),
                    "status": test_status,
                    "columns": columns,
                    "rows": rows,
                })
            except DatabaseError as error:
                st.error(str(error))
            else:
                st.session_state["test_add.done"] = test_id.strip() or default_test_id
                st.rerun()
        if done := st.session_state.pop("test_add.done", None):
            st.success(f"Test '{done}' added: press Run to use it.")

with tabs["Propeller sizing"]:
    if two is not None and app.outdated:
        st.warning(OUTDATED)
    with st.expander("How to choose the pitch"):
        st.markdown(pc.__doc__.split("\n\n", 2)[2])
    st.markdown(
        "**Cruise motors** (cruise and tilting): the pitch is sized at the two cruise operating points, the "
        "target speeds V1 and V2 with the thrust each motor must give there (cruise drag of the last Run). "
        "**Lift-only motors**: sized in hover."
    )
    if two is None or checked.project is None:
        st.info(
            "Press Run: the pitch is sized at the thrusts of the target speeds V1 and V2."
        )
    else:
        aircraft = AircraftModel(checked.project)
        roles = {}
        for m in checked.project.motors:
            roles.setdefault(m.unit, set()).add(m.role)
        cruise_units = [u for u, r in roles.items() if r & {"cruise", "tilt"}]
        lift_units = [u for u, r in roles.items() if not r & {"cruise", "tilt"}]
        if architecture != "quadplane":
            lift_units, cruise_units = list(roles), []
        st.subheader("Cruise motors (sized at V1 and V2)")
        if not cruise_units:
            st.info(
                "No cruise or tilting motor: a multicopter flies forward by tilting the frame, "
                "its propellers are sized in hover (below)."
            )
        for name in cruise_units:
            spec = checked.project.propulsion_units[name]
            with st.container(border=True):
                numbers = [
                    str(i + 1)
                    for i, m in enumerate(checked.project.motors)
                    if m.unit == name
                ]
                st.markdown(
                    f"**{name}** (motor {', '.join(numbers)}) — {spec.motor_id}, "
                    f"{spec.prop_diameter_in:g} x {tpv.fmt(spec.prop_pitch_in, 'g')} in; "
                    "database propellers of this diameter: "
                    f"{', '.join(ps.database_propellers(spec.prop_diameter_in)) or 'none'}"
                )
                rows, rec = ps.cruise_pitch_rows(aircraft, two, name)
                if not rows:
                    st.info("No cruise operating point for this unit in the last Run.")
                    continue
                points = [
                    (c.index, c.v_m_s, m.thrust_n)
                    for c in two.cruise
                    for m in c.motors
                    if m.unit == name
                ][:2]
                st.markdown(
                    "**Sizing point: cruise** — "
                    + "; ".join(
                        f"V{k} = {un.speed_text(v)}, thrust {un.thrust_text(t)} per motor"
                        for k, v, t in points
                    )
                    + " (thrust = cruise drag shared by the cruise motors, from the last Run)."
                )
                st.plotly_chart(
                    ps.pitch_figure(
                        rows,
                        rec,
                        f"{name}: efficiency versus pitch at the cruise points",
                    ),
                    width="stretch",
                    key=f"pitch.{name}",
                )
                table(rec)
                with st.expander("Values per pitch"):
                    table(rows)
                best = rec.get("best compromise V1 + V2 (in)")
                if best is not None and st.button(
                    f"Use {best:g} in for '{name}'", key=f"{gen}:usepitch.{name}"
                ):
                    app.data["propulsion_units"][name]["prop_pitch_in"] = best
                    app.data["propulsion_units"][name].pop("propeller_id", None)
                    st.rerun()
        if lift_units:
            with st.expander(
                "Lift motors (sized in hover): " + ", ".join(lift_units),
                expanded=not cruise_units,
            ):
                for name in lift_units:
                    spec = checked.project.propulsion_units[name]
                    hover_motors = [m for m in two.hover.motors if m.unit == name]
                    if not hover_motors:
                        continue
                    st.markdown(
                        f"**{name}** — {spec.motor_id}, {spec.prop_diameter_in:g} x "
                        f"{tpv.fmt(spec.prop_pitch_in, 'g')} in: only lifts, its pitch is sized in "
                        f"hover at {un.thrust_text(hover_motors[0].thrust_n)} per motor "
                        "(lowest electric power)."
                    )
                    table(
                        pc.hover_pitch_rows(
                            aircraft.units[name],
                            spec.prop_diameter_in,
                            pc.default_pitches(spec.prop_diameter_in),
                            hover_motors[0].thrust_n,
                            aircraft.rho,
                            two.hover.chain.bus_voltage_v,
                        )
                    )

with tabs["Test data"]:
    with st.expander("What is compared, and how the model computes it", expanded=True):
        st.markdown(explanations.INTRO)
        st.plotly_chart(
            explanations.energy_chain_figure(architecture == "quadplane"),
            width="stretch",
            key="testdata.chain",
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Hover point**")
            for text, formula in explanations.HOVER:
                st.markdown(text)
                st.latex(formula)
        with c2:
            if architecture == "quadplane":
                st.markdown("**Cruise point** (winged aircraft)")
                steps = explanations.CRUISE_WINGED
            else:
                st.markdown("**Cruise point** (multicopter, in-house drag model)")
                steps = explanations.CRUISE_MULTICOPTER
            for text, formula in steps:
                st.markdown(text)
                st.latex(formula)
    st.subheader("Measured flight points")
    data["test_data"] = forms.render_items(
        st, FlightPoint, data.get("test_data") or [], "test_data", errors, gen
    )
    if (
        checked.project is not None
        and checked.project.test_data
        and st.button("Compare with the model")
    ):
        try:
            backend = (
                backend_for(checked.project)
                if ui_state.excel_available() is None
                else None
            )
            st.session_state["comparison"] = tdv.compare_points(
                checked.project, backend
            )
        except Exception as error:  # ruff: ignore[blind-except]
            st.error(f"Comparison failed: {error}")
    if st.session_state.get("comparison"):
        st.caption(
            "Model without calibration, at the mass and conditions of each point."
        )
        table(st.session_state["comparison"])
    with st.expander("Calibration on the measured points"):
        calibration = dict(data.get("calibration") or {})
        c1, c2 = st.columns(2)
        for column, point, model_cls, default in (
            (c1, "hover", HoverReference, {"battery_power_w": 200.0}),
            (
                c2,
                "cruise",
                CruiseReference,
                {"speed_m_s": 15.0, "battery_power_w": 100.0},
            ),
        ):
            with column:
                if st.checkbox(
                    f"Calibrate on a {point} point",
                    value=calibration.get(point) is not None,
                    key=f"{gen}:calibration.{point}.on",
                ):
                    calibration[point] = forms.render_model(
                        st,
                        model_cls,
                        calibration.get(point) or default,
                        f"calibration.{point}",
                        errors,
                        {},
                        gen,
                    )
                else:
                    calibration.pop(point, None)
        data["calibration"] = (
            calibration
            if (calibration.get("hover") or calibration.get("cruise"))
            else None
        )
        st.markdown(explanations.CALIBRATION)
        report = (two.metadata.get("calibration") if two is not None else None) or []
        if report:
            st.markdown("**Factors set by the last Run**")
            table(tdv.calibration_rows(report))
        with st.expander("Calibration procedure in detail (MIC-CAL-REF)"):
            st.markdown(calibration_doc)
    data = {k: v for k, v in data.items() if v is not None and v != {}}
    app.data = data

checked = ui_state.check(data)

# --- sidebar: validation, Run, save ------------------------------------------------------
with st.sidebar:
    if checked.missing:
        st.warning("Required fields missing: " + ", ".join(checked.missing))
    elif checked.errors:
        st.error(
            "Invalid project:\n\n"
            + "\n\n".join(f"`{p or 'project'}`: {m}" for p, m in checked.errors.items())
        )
    excel_reason = (
        ui_state.excel_available(data.get("aero", {}).get("profile", "SD7003"))
        if architecture == "quadplane"
        else None
    )
    if excel_reason:
        st.info(excel_reason)
    run = st.button(
        "Run",
        type="primary",
        disabled=not ui_state.run_enabled(checked) or bool(excel_reason),
        help="Two-phase flight time: hover, then cruise at V1 and V2 (calibrated first when "
        "measured points are given for the calibration).",
    )
    st.divider()
    default_name = (
        f"{app.source_path.stem}_copy.yaml"
        if app.source_path
        else f"{data.get('name', 'project')}.yaml"
    )
    st.markdown("**Project file**")
    target = st.text_input(
        "File name",
        default_name,
        key=f"{gen}:save_as",
        help="YAML file of the project being edited, reopened with 'Open a project file'. "
        "To add it to the list 'Start from a template' instead, use 'Save as template' above.",
    )
    if st.button("Save project file", disabled=checked.project is None):
        st.success(f"Saved {ui_state.save_project(data, target).resolve()}")
    if checked.project is not None:
        st.download_button(
            "Download YAML",
            yaml.safe_dump(
                checked.project.to_dict(), sort_keys=False, allow_unicode=True
            ),
            file_name=Path(target).name,
        )

if run:
    with st.spinner(
        "Evaluating…" + (" (PredimRC)" if architecture == "quadplane" else "")
    ):
        try:
            backend = backend_for(checked.project)
            app.two_phase = evaluate_two_phase(checked.project, backend=backend)
            app.result_key = ui_state.project_key(data)
            st.rerun()
        except Exception as error:  # ruff: ignore[blind-except]
            st.error(f"Evaluation failed: {error}")
            with st.expander("Details"):
                st.code(traceback.format_exc())

with tabs["Results"]:
    if two is None:
        st.info("Press Run to compute the flight time.")
    else:
        if app.outdated:
            st.warning(
                "Outdated: the project changed since this result. Press Run to update."
            )
        if checked.project is not None and not app.outdated:
            from predimrc_wrapper.ui import runs_page  # noqa: E402

            runs_page.save_form(app, checked.project, two)
        st.subheader("Flight time — hover then cruise (designer's process)")
        st.markdown(
            (
                "feasible"
                if two.feasible
                else f":red[infeasible] (limiting: {two.limiting})"
            )
            + f" — hover {two.hover_time_s:.0f} s, reserve {100 * two.reserve_fraction:.0f} % of the nominal "
            f"energy ({two.energy_nominal_j / 3600:.1f} Wh nominal, {two.energy_available_j / 3600:.1f} Wh available)"
        )
        for row in tpv.kpi_rows(two):
            for col, (label, text, negative) in zip(
                st.columns(len(row)), row, strict=False
            ):
                metric(col, label, text, negative)
        if checked.project is not None and not app.outdated:
            try:
                c_res, r_res = cost_and_reliability(checked.project, two)
                cols = st.columns(3)
                metric(
                    cols[0], "Purchase cost", f"{c_res.purchase:.0f} {c_res.currency}"
                )
                metric(
                    cols[1],
                    "Cost per flight hour",
                    f"{c_res.cost_per_hour:.2f} {c_res.currency}/h",
                )
                metric(
                    cols[2],
                    "Motor-out T/W (worst)",
                    f"{r_res.worst_thrust_to_weight:.2f}",
                    negative=not r_res.all_survivable,
                )
            except Exception as error:  # ruff: ignore[blind-except]
                st.warning(f"Cost / reliability not computed: {error}")
        for w in two.warnings:
            st.warning(w)
        st.markdown(
            "**Flight phases** (vertical phases, then the cruise until the reserve)"
        )
        table(tpv.phase_rows(two))
        for c in two.cruise:
            st.caption(f"V{c.index}: " + two.hand_check(c.index))
        if two.discharge is not None and two.discharge.time_s:
            st.plotly_chart(tpv.discharge_figure(two), width="stretch")
            st.caption(
                "Open-circuit voltage from the discharge curve of the chemistry, internal "
                "resistance growing below 20 % (MIC-PROP-BAT). The landing is evaluated at the "
                f"reserve, {two.reserve_fraction:.0%} state of charge: its margins are in the "
                "tiles above (worst case of the flight) and its rows in the Hover tab."
            )
        st.markdown(
            f"Front / rear thrust ratio **{tpv.fmt(two.hover.front_rear_ratio, '.2f')}** — "
            "margins of each lift motor (hover, landing, transition, yaw): Hover tab, with "
            "the test points and the surrogate; Cruise tab (PredimRC), Power chain tab (losses)."
        )
        st.markdown("**Cruise**")
        table(tpv.cruise_rows(two))
        if checked.project is not None and not app.outdated:
            st.subheader("Where the battery power goes (power budget)")
            st.caption(
                "Each phase splits the chemical power of the cells into its sinks, from the "
                "air back to the battery; they add up to the total (MIC-MIS-BUDGET)."
            )
            budgets = power_budget(
                AircraftModel(checked.project, aero_backend=None), two
            )
            fig = go.Figure([
                go.Bar(
                    name=sink,
                    x=[b.phase for b in budgets],
                    y=[b.sinks.get(sink, 0.0) for b in budgets],
                )
                for sink in dict.fromkeys(k for b in budgets for k in b.sinks)
            ])
            fig.update_layout(
                barmode="stack",
                yaxis_title="power (W)",
                height=380,
                margin={"l": 10, "r": 10, "t": 30, "b": 10},
            )
            c1, c2 = st.columns([2, 3])
            c1.plotly_chart(fig, width="stretch", key="results.budget")
            with c2:
                table(budget_rows(budgets))

with tabs["Cost and reliability"]:
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Prices entered and wear")
        st.caption(
            "Costs in euros. Component prices come from the price list (source and date in the "
            f"table), read in USD and converted at {default_prices().usd_per_eur} USD/EUR (ECB "
            f"reference rate of {default_prices().exchange_date}; changed in Advanced). Frame, "
            "avionics and overrides are entered in euros. Overrides replace a database price: "
            "keys `motor:<id>`, `propeller:<id>`, `esc`, `esc4in1`, `battery_per_wh`, `cable:<awg>`."
        )
        spec = dict(data.get("cost") or {})
        out = forms.render_model(
            st, CostSpec, spec, "cost", errors, {}, gen, skip=("overrides",)
        )
        rows = [
            {"key": k, "price": v} for k, v in (spec.get("overrides") or {}).items()
        ]
        edited = st.data_editor(
            forms.editor_base(
                st,
                f"{gen}:cost.overrides",
                gen,
                lambda: rows or [{"key": None, "price": None}],
            ),
            key=f"{gen}:cost.overrides",
            num_rows="dynamic",
            width="stretch",
            column_config={
                "key": st.column_config.TextColumn("override key"),
                "price": st.column_config.NumberColumn("price (EUR)", min_value=0.0),
            },
        )
        out["overrides"] = {
            r["key"]: float(r["price"])
            for r in edited
            if r.get("key") and r.get("price") is not None
        }
        # Stored only once it differs from the defaults (a Run result stays up to date).
        if data.get("cost") or out != CostSpec().model_dump():
            data["cost"] = out
    with right:
        if checked.project is None:
            st.info("The cost is computed once the project is valid.")
        else:
            c_res, r_res = cost_and_reliability(checked.project, two)
            st.subheader(
                f"Purchase cost: {c_res.purchase:.2f} {c_res.currency}"
                + (
                    f" (+ {len(c_res.missing)} item(s) without price)"
                    if c_res.missing
                    else ""
                )
            )
            if c_res.missing:
                st.warning(
                    "No price for: "
                    + ", ".join(c_res.missing)
                    + ". Enter an override to "
                    "include them."
                )
            by_cat = c_res.by_category()
            fig = go.Figure(
                go.Bar(x=list(by_cat.values()), y=list(by_cat), orientation="h")
            )
            fig.update_layout(
                xaxis_title=f"price ({c_res.currency})",
                height=260,
                margin={"l": 10, "r": 10, "t": 10, "b": 10},
            )
            st.plotly_chart(fig, width="stretch", key="cost.categories")
            table(cov.purchase_rows(c_res))
            st.subheader("Cost of use (wear)")
            if two is None or app.outdated:
                st.info("Press Run: the cost of use needs the flight time.")
            else:
                st.caption(
                    f"Per flight of {c_res.flight_time_s / 60:.1f} min (two-phase flight time at "
                    "V1): battery price / cycle life + motor price × flight time / motor life + "
                    "propeller price / flights between replacements (MIC-COST)."
                )
                table(cov.use_rows(c_res))
            st.subheader("Reliability: hover with one motor stopped")
            st.caption(
                "For each lift motor stopped, the others must balance the weight and the pitch, "
                "roll"
                + (
                    " moments (yaw by the tilting motor)"
                    if r_res.yaw_by_tilt
                    else " and yaw (propeller torque, alternating spins) moments"
                )
                + " within their maximum thrust (MIC-REL)."
            )
            table(cov.reliability_rows(r_res, checked.project))
            st.markdown(
                "**Single points of failure:** " + "; ".join(r_res.single_points)
            )
