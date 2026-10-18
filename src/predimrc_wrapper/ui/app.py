"""Streamlit GUI of the designer's workflow (INC2-009). Run with ``predimrc-ui [project.yaml]``."""

from __future__ import annotations

import inspect
import sys
import traceback
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml

from predimrc_wrapper.aircraft import AircraftModel
from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import layouts
from predimrc_wrapper.aircraft.project import TEMPLATES
from predimrc_wrapper.aircraft.project import AeroSpec
from predimrc_wrapper.aircraft.project import BatterySpec
from predimrc_wrapper.aircraft.project import CruiseReference
from predimrc_wrapper.aircraft.project import DragSource
from predimrc_wrapper.aircraft.project import EnvironmentSpec
from predimrc_wrapper.aircraft.project import FlightPoint
from predimrc_wrapper.aircraft.project import HoverReference
from predimrc_wrapper.aircraft.project import MassItem
from predimrc_wrapper.aircraft.project import MissionSettings
from predimrc_wrapper.aircraft.project import PropulsionSpec
from predimrc_wrapper.aircraft.project import SizingSpec
from predimrc_wrapper.aircraft.project import WiringSpec
from predimrc_wrapper.api import evaluate
from predimrc_wrapper.api import evaluate_two_phase
from predimrc_wrapper.api import profiles_dir
from predimrc_wrapper.calibration import __doc__ as CALIBRATION_DOC
from predimrc_wrapper.data import default_database
from predimrc_wrapper.data import default_propellers
from predimrc_wrapper.data import default_tests
from predimrc_wrapper.mission.scenario import Segment
from predimrc_wrapper.settings import Settings
from predimrc_wrapper.settings import available_profiles
from predimrc_wrapper.sizing import motor_power_ranges
from predimrc_wrapper.ui import charts
from predimrc_wrapper.ui import cruise_view as cv
from predimrc_wrapper.ui import forms
from predimrc_wrapper.ui import geometry
from predimrc_wrapper.ui import hover_view as hv
from predimrc_wrapper.ui import mic_page
from predimrc_wrapper.ui import prop_sizing as ps
from predimrc_wrapper.ui import propulsion_charts as pc
from predimrc_wrapper.ui import state as ui_state
from predimrc_wrapper.ui import test_data_view as tdv
from predimrc_wrapper.ui import two_phase_view as tpv
from predimrc_wrapper.ui.help import HelpRegistry

st.set_page_config(page_title="PredimRC pre-sizing", layout="wide")
HELP = HelpRegistry.default()
forms.HELP = HELP.tooltip


@st.cache_resource
def predimrc_session(profile: str, folder: str):
    """One Excel session per profile and folder for the whole GUI."""
    from predimrc_wrapper.predimrc_wrapper import PredimRCWrapper  # noqa: PLC0415

    return PredimRCWrapper(profile=profile, template_dir=folder).__enter__()


def backend_for(project: Project):
    """The PredimRC session of a quadplane, reopened when Excel was closed or disconnected."""
    if project.architecture != "quadplane":
        return None
    session = predimrc_session(project.aero.profile, str(profiles_dir()))
    if not session.is_alive():
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass
        predimrc_session.clear()
        session = predimrc_session(project.aero.profile, str(profiles_dir()))
    return session


def table(rows: list[dict] | dict, **kwargs) -> None:
    """A table whose column headers carry the help of the glossary (REQ-UI-010)."""
    if isinstance(rows, dict):
        rows = [{"quantity": k, "value": "—" if v is None else str(v)} for k, v in rows.items()]
    columns = list(dict.fromkeys(k for r in rows for k in r))
    config = {c: st.column_config.Column(c, help=HELP.tooltip(c)) for c in columns}
    st.dataframe(rows, hide_index=True, width="stretch", column_config=config, **kwargs)


def metric(col, label: str, text: str, negative: bool = False) -> None:
    col.metric(label, text, help=HELP.tooltip(label))
    if negative:
        col.markdown(":red[negative margin]")


def _initial_state() -> ui_state.AppState:
    args = [a for a in sys.argv[1:] if not a.startswith("-") and Path(a).suffix in (".yaml", ".yml")]
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
    page = st.radio("Page", ["Pre-sizing", "Model cards (MIC)", "Glossary"], key="page", horizontal=True)
    st.header("Project")
    upload = st.file_uploader("Open a project file", type=["yaml", "yml"])
    if upload is not None and st.session_state.get("opened") != upload.file_id:
        st.session_state["opened"] = upload.file_id
        st.session_state["configuration"] = None
        app.load(yaml.safe_load(upload.getvalue()), Path(upload.name))
        st.rerun()
    st.selectbox("Configuration (loads its template)", list(TEMPLATES), format_func=TEMPLATES.get,
                 key="configuration", placeholder="from a project file", on_change=_switch_configuration,
                 help="Quadplane 4+1, tricopter, quadcopter or tilt-rotor. Changing it replaces the project.")
    data = app.data
    gen = app.generation
    architecture = data.get("architecture", "multicopter")
    with st.expander("Settings (folders)"):
        settings = Settings.load()
        folder = st.text_input("PredimRC folder", settings.predimrc_folder, key="settings.predimrc",
                               help="Folder of the workbooks PredimRC_<profile>.xls (one per wing airfoil).")
        root = st.text_input("Studies root folder", settings.studies_root, key="settings.studies",
                             help="Explorations and optimisations are stored in dated sub-folders of this folder.")
        if st.button("Save the settings"):
            settings.predimrc_folder, settings.studies_root = folder, root
            st.success(f"Saved {settings.save()}")
        st.caption(f"Profiles found: {', '.join(available_profiles()) or 'none'}")

if page == "Model cards (MIC)":
    st.title("Model identity cards (MIC)")
    cards = mic_page.cards()
    if not cards:
        st.info("The MIC cards are in the repository folder mvp/docs/models (development install).")
    else:
        table([{k: c[k] for k in ("id", "title", "verification")} for c in cards])
        chosen = st.selectbox("Card", [c["id"] for c in cards], format_func=lambda i: f"{i} — "
                              + next(c["title"] for c in cards if c["id"] == i), key="mic.card")
        st.markdown(mic_page.render_text(chosen))
    st.stop()

if page == "Glossary":
    st.title("Glossary of the quantities")
    query = st.text_input("Search", key="glossary.search")
    entries = HELP.search(query) if query else list(HELP.entries.values())
    table([{"key": e.key, "name": e.name, "symbol": e.symbol, "unit": e.unit, "definition": e.definition,
            "default": e.default, "source of the default": e.default_source, "model card": e.model}
           for e in entries[:500]])
    st.stop()

checked = ui_state.check(data)
ranges = None
if checked.project is not None and checked.project.sizing is not None:
    ranges = motor_power_ranges(checked.project, db)
two = app.two_phase

# --- tabs ------------------------------------------------------------------------------
config_label = data.get("name") or "Aircraft configuration"
labels = [config_label, "Masses and battery", "Mission", "Hover", "Cruise", "Drag", "Power chain", "Propeller sizing",
          "Test data", "Results", "Exploration", "Optimisation", "Studies"]
tabs = dict(zip(labels, st.tabs(labels)))
errors = checked.errors

with tabs[config_label]:
    left, right = st.columns([3, 2])
    with left:
        data["name"] = st.text_input("Configuration name *", data.get("name", ""), key=f"{gen}:name",
                                     help="Name of the configuration (title of this tab, project name).")
        st.caption(f"Architecture **{architecture}** ({TEMPLATES.get(st.session_state.get('configuration'), 'project file')}).")
        units = dict(data.get("propulsion_units") or {})
        st.subheader("Propulsion unit types")
        only_in_range = bool(ranges) and st.checkbox("Offer only the motors in the power range", value=True,
                                                     key=f"{gen}:only_in_range")
        choices = {}
        for name in units:
            candidates = next((r.candidates for r in ranges or [] if r.unit == name), None)
            choices[f"propulsion_units.{name}.motor_id"] = (candidates if only_in_range and candidates is not None
                                                            else db.ids())
            choices[f"propulsion_units.{name}.propeller_id"] = [None, *default_propellers().ids()]
        used = {m.get("unit") for m in data.get("motors") or []}
        columns = st.columns(max(1, min(3, len(units))))
        for i, name in enumerate(list(units)):
            with columns[i % len(columns)], st.container(border=True):
                st.markdown(f"**{name}**")
                units[name] = forms.render_model(st, PropulsionSpec, units[name], f"propulsion_units.{name}", errors,
                                                 choices, gen)
                if name not in used and st.button(f"Remove '{name}'", key=f"{gen}:remove_unit.{name}"):
                    units.pop(name)
                    data["propulsion_units"] = units
                    st.rerun()
        c1, c2 = st.columns([3, 1])
        new_unit = c1.text_input("New unit type name", key=f"{gen}:new_unit")
        if c2.button("Add unit type") and new_unit and new_unit not in units:
            units[new_unit] = dict(next(iter(units.values()))) if units else {"motor_id": db.ids()[0],
                                                                               "prop_diameter_in": 10.0}
            data["propulsion_units"] = units
            st.rerun()
        data["propulsion_units"] = units

        winged = architecture == "quadplane"
        st.subheader("Motors and tilting motors" if winged else "Motors")
        st.caption("One motor per arm or boom end, numbered in this order (ArduPilot outputs). x aft-positive from the "
                   + ("wing root LE" if winged else "frame centre") + ", y right. "
                   + ("Role: lift (vertical flight) or cruise (forward flight); tick **tilts** for a motor that lifts "
                      "in hover and pushes in cruise (ArduPilot Q_TILT_MASK)." if winged else
                      "A multicopter flies forward by tilting the whole frame: every motor lifts, no tilting motor "
                      "(a tricopter's rear motor tilts for yaw only). For tilting motors, choose a configuration with "
                      "a wing (e.g. tricopter with wing)."))
        rows = [{"unit": m.get("unit"), "role": "lift" if m.get("role") == "tilt" else m.get("role"),
                 "tilts": m.get("role") == "tilt", "x_mm": m.get("x_mm"), "y_mm": m.get("y_mm")}
                for m in data.get("motors") or []]
        layout_version = st.session_state.setdefault("layout_version", 0)
        edited = st.data_editor(
            rows, key=f"{gen}:motors:{layout_version}", num_rows="dynamic", hide_index=False, width="stretch",
            column_config={"unit": st.column_config.SelectboxColumn("unit", options=list(units), help=HELP.tooltip("motors.*.unit")),
                           "role": st.column_config.SelectboxColumn("role", options=["lift", "cruise"] if winged else ["lift"],
                                                                    help=HELP.tooltip("motors.*.role")),
                           "tilts": st.column_config.CheckboxColumn("tilts", help=HELP.tooltip("tilts"), disabled=not winged),
                           "x_mm": st.column_config.NumberColumn("x (mm)", help=HELP.tooltip("motors.*.x_mm")),
                           "y_mm": st.column_config.NumberColumn("y (mm)", help=HELP.tooltip("motors.*.y_mm"))},
            column_order=["unit", "role", "tilts", "x_mm", "y_mm"] if winged else ["unit", "role", "x_mm", "y_mm"])
        data["motors"] = [{"unit": r["unit"], "role": "tilt" if r.get("tilts") else (r.get("role") or "lift"),
                           "x_mm": r["x_mm"], "y_mm": r["y_mm"]} for r in edited
                          if r.get("unit") is not None and r.get("x_mm") is not None and r.get("y_mm") is not None]
        c1, c2 = st.columns(2)
        with c1:
            data["cg_x_mm"] = forms.render_field(st, "cg_x_mm", Project.model_fields["cg_x_mm"], data.get("cg_x_mm"),
                                                 "cg_x_mm", errors, {}, gen)
        with c2:
            data["cg_y_mm"] = forms.render_field(st, "cg_y_mm", Project.model_fields["cg_y_mm"],
                                                 data.get("cg_y_mm", 0.0), "cg_y_mm", errors, {}, gen)
        with st.expander("Generate the motor positions from a few dimensions"):
            n_lift = sum(1 for m in data.get("motors") or [] if m.get("role") in ("lift", "tilt"))
            presets = layouts.presets_for(architecture, n_lift)
            st.caption("Recomputes the motor positions of **this** configuration from its dimensions (arm length, boom "
                       "span, stations...) and replaces the motor table. To change the configuration itself "
                       "(tricopter, quadcopter, quadplane...), use the Configuration selector in the sidebar.")
            preset = st.selectbox("Layout", list(presets), key=f"{gen}:preset")
            func = presets[preset]
            kwargs = {}
            for pname, param in inspect.signature(func).parameters.items():
                key = f"{gen}:preset.{preset}.{pname}"
                if pname.endswith("_unit") or pname == "unit":
                    kwargs[pname] = st.selectbox(pname.replace("_", " "), list(units) or [str(param.default)], key=key)
                elif pname in ("n", "per_boom"):
                    default = max(4, n_lift) if pname == "n" else (2 if param.default is inspect.Parameter.empty else param.default)
                    low = 4 if pname == "n" else 1
                    kwargs[pname] = int(st.number_input("number of arms" if pname == "n" else "motors per boom", low, 12,
                                                        int(default), key=key))
                else:
                    default = 300.0 if param.default is inspect.Parameter.empty else float(param.default)
                    kwargs[pname] = float(st.number_input(pname.replace("_", " "), value=default, key=key))
            if st.button("Replace the motors with this layout"):
                data["motors"] = func(**kwargs)
                st.session_state["layout_version"] = layout_version + 1
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
            if st.checkbox("Use a target mass range", value=sizing is not None, key=f"{gen}:sizing.on"):
                sizing = dict(sizing or {"target_mass_kg": [1.5, 2.5]})
                low, high = (sizing.get("target_mass_kg") or [1.5, 2.5])[:2]
                c1, c2 = st.columns(2)
                low = c1.number_input("Target mass min (kg) *", value=float(low), min_value=0.05, key=f"{gen}:sizing.min",
                                      help=HELP.tooltip("sizing.target_mass_kg"))
                high = c2.number_input("Target mass max (kg) *", value=float(high), min_value=0.05,
                                       key=f"{gen}:sizing.max", help=HELP.tooltip("sizing.target_mass_kg"))
                out = forms.render_model(st, SizingSpec, sizing, "sizing", errors, {}, gen, skip=("target_mass_kg",))
                data["sizing"] = {"target_mass_kg": [low, high], **out}
            else:
                data.pop("sizing", None)
            if ranges:
                table(pc.range_rows(ranges))
        with st.expander("Reference motor data (all the motors of the database; the 'fits unit types' column uses the "
                         "pre-selection above)"):
            table(pc.motor_rows(db, ranges))
    with right:
        if checked.project is not None:
            st.plotly_chart(geometry.top_view(checked.project), width="stretch")
            st.plotly_chart(geometry.front_view(checked.project), width="stretch")
        else:
            st.info("The geometry is drawn once the project is valid.")

with tabs["Masses and battery"]:
    left, right = st.columns(2)
    with left:
        st.subheader("Battery")
        data["battery"] = forms.render_model(st, BatterySpec, data.get("battery"), "battery", errors, {}, gen)
        info = Project.model_fields["max_takeoff_mass_kg"]
        data["max_takeoff_mass_kg"] = forms.render_field(
            st, "max_takeoff_mass_kg", info, data.get("max_takeoff_mass_kg"), "max_takeoff_mass_kg", errors, {}, gen)
    with right:
        st.subheader("Mass items")
        data["mass_items"] = forms.render_items(st, MassItem, data.get("mass_items") or [], "mass_items", errors, gen)
        if checked.project is not None:
            mass = AircraftModel(checked.project).mass
            fig = go.Figure(go.Bar(x=[1000 * v for v in mass["breakdown"].values()], y=list(mass["breakdown"]),
                                   orientation="h"))
            fig.update_layout(title=f"Mass breakdown — total {mass['total_kg']:.3f} kg", xaxis_title="mass (g)",
                              height=300, margin={"l": 10, "r": 10, "t": 40, "b": 10})
            st.plotly_chart(fig, width="stretch")

with tabs["Mission"]:
    left, right = st.columns(2)
    with left:
        st.subheader("Two-phase flight time")
        mission = dict(data.get("mission") or {})
        data["mission"] = forms.render_model(st, MissionSettings, mission, "mission", errors, {}, gen,
                                             skip=("target_speeds_m_s",))
        auto = st.checkbox("Target speeds: minimum aerodynamic power (V1) and maximum L/D (V2)",
                           value=not mission.get("target_speeds_m_s"), key=f"{gen}:mission.speeds_auto",
                           help=HELP.tooltip("mission.target_speeds_m_s"))
        if not auto:
            v1, v2 = (mission.get("target_speeds_m_s") or [12.0, 15.0])[:2]
            c1, c2 = st.columns(2)
            data["mission"]["target_speeds_m_s"] = [
                c1.number_input("V1 (m/s)", value=float(v1), min_value=1.0, key=f"{gen}:mission.v1", help=HELP.tooltip("V1")),
                c2.number_input("V2 (m/s)", value=float(v2), min_value=1.0, key=f"{gen}:mission.v2", help=HELP.tooltip("V2"))]
    with right:
        st.subheader("Environment")
        data["environment"] = forms.render_model(st, EnvironmentSpec, data.get("environment"), "environment",
                                                 errors, {}, gen)
    scenario_names = list((data.get("scenarios") or {}).keys())
    with st.expander("Scenario mode (MVP solver: segments, transitions)"):
        scenario = st.selectbox("Scenario", scenario_names, key=f"{gen}:scenario") if scenario_names else None
        if scenario:
            segments = (data["scenarios"][scenario] or {}).get("segments") or []
            data["scenarios"][scenario] = {"segments": forms.render_items(
                st, Segment, segments, f"scenarios.{scenario}.segments", errors, gen)}
        new = st.text_input("New scenario name", key=f"{gen}:new_scenario")
        if st.button("Add scenario (hover 90 s)") and new:
            data["scenarios"][new] = {"segments": [s.model_dump(mode="json", exclude_none=True) for s in
                                                   ui_state.hover_scenario(architecture).segments]}
            st.rerun()

with tabs["Cruise"]:
    if architecture != "quadplane":
        st.info("A multicopter does not use PredimRC: its cruise uses the body drag area (Drag tab) and the "
                "forward-flight model; the target speeds are its best-endurance and best-range speeds.")
    else:
        st.caption(f"PredimRC folder `{profiles_dir().resolve()}` — profiles: {', '.join(available_profiles()) or 'none'}. "
                   "Accessory surface (S.ac) forced to 0: the parasitic drag is in the Drag tab.")
        left, right = st.columns([2, 3])
        with left:
            data["aero"] = forms.render_model(st, AeroSpec, data.get("aero"), "aero", errors,
                                              {"aero.profile": available_profiles() or ["SD7003"]}, gen)
        with right:
            if two is None or two.curve is None:
                st.info("Press Run to compute the PredimRC curves.")
            else:
                passed, message = cv.iso_text(two)
                (st.success if passed else st.warning)(message)
                table(cv.results_rows(two))
                st.plotly_chart(cv.power_figure(two), width="stretch")
                st.plotly_chart(cv.imposed_figure(two), width="stretch")
                st.plotly_chart(cv.palier_figure(two), width="stretch")

with tabs["Drag"]:
    st.caption("The PredimRC accessory drag is set to 0: every parasitic drag outside the PredimRC airframe is a "
               "source below (shapes Profilé / Mixte / Non profilé with the PredimRC C_d).")
    if architecture == "multicopter":
        st.subheader("Body drag in cruise")
        st.caption("Drag of the body (frame, battery, payload) when the multicopter flies forward: C_d of the shape "
                   "(PredimRC values) × frontal area, or a C_d / CdS entered (advanced).")
        from predimrc_wrapper.data.drag_shapes import drag_shapes as _shapes  # noqa: E402

        c1, c2 = st.columns(2)
        with c1:
            data["body_shape"] = forms.render_field(st, "body_shape", Project.model_fields["body_shape"],
                                                    data.get("body_shape", "Non profilé"), "body_shape", errors,
                                                    {"body_shape": list(_shapes())}, gen)
        with c2:
            data["body_frontal_area_dm2"] = forms.render_field(st, "body_frontal_area_dm2",
                                                               Project.model_fields["body_frontal_area_dm2"],
                                                               data.get("body_frontal_area_dm2"), "body_frontal_area_dm2",
                                                               errors, {}, gen)
        with st.expander("Advanced: C_d or CdS entered"):
            for name in ("body_cd", "body_cds_m2"):
                data[name] = forms.render_field(st, name, Project.model_fields[name], data.get(name), name, errors, {}, gen)
        if checked.project is not None:
            st.info("Body drag model: " + checked.project.body_drag()[1])
    st.subheader("Parasitic drag sources")
    from predimrc_wrapper.data.drag_shapes import drag_shapes  # noqa: E402

    data["drag_sources"] = forms.render_items(st, DragSource, data.get("drag_sources") or [], "drag_sources",
                                              errors, gen, options={"shape": list(drag_shapes())})
    if checked.project is not None and checked.project.drag_sources:
        from predimrc_wrapper.aircraft.drag_sources import drag_report  # noqa: E402

        rho = AircraftModel(checked.project).rho
        v1 = two.cruise[0].v_m_s if two is not None else None
        rows = []
        for r in drag_report(checked.project):
            row = {"source": r.name, "kind": r.kind, "model": r.model, "formula": r.formula,
                   "frontal area (dm²)": None if not np.isfinite(r.frontal_area_m2) else round(100 * r.frontal_area_m2, 3),
                   "area from": r.area_from, "C_d": None if not np.isfinite(r.cd) else r.cd,
                   "CdS (dm²)": round(100 * r.cds_m2, 4), "coefficient source": r.coefficient_source}
            if v1 is not None:
                row["drag power at V1 (W)"] = round(0.5 * rho * v1**3 * r.cds_m2, 2)
            rows.append(row)
        table(rows)

with tabs["Power chain"]:
    from predimrc_wrapper.ui import wiring_view as wv  # noqa: E402

    left, right = st.columns([2, 3])
    with left:
        st.markdown(wv.TERMS)
        st.caption("The values below are the defaults used until you change them (no need to enter everything). "
                   + ("Lift ESC position: % of the **arm length** from the frame centre for separate ESCs; a 4-in-1 "
                      "board sits at the frame centre." if architecture == "multicopter" else
                      "ESC positions: % of the **fuselage length** from the nose."))
        skip = ("overrides",) + (("cruise_esc_position_pct",) if architecture == "multicopter" else ())
        wiring = forms.render_model(st, WiringSpec, data.get("wiring") or {}, "wiring", errors, {}, gen, skip=skip)
        with st.expander("Cable lengths entered per motor (replace the lengths from the geometry)"):
            from predimrc_wrapper.aircraft.project import BranchOverride  # noqa: E402

            wiring["overrides"] = forms.render_items(st, BranchOverride, (data.get("wiring") or {}).get("overrides") or [],
                                                     "wiring.overrides", errors, gen)
        data["wiring"] = wiring
    with right:
        if checked.project is not None:
            st.plotly_chart(wv.diagram(checked.project), width="stretch", key="chain.diagram")
            currents = None
            if two is not None:
                currents = [10.0] * len(checked.project.motors)
                for m in two.hover.motors:
                    currents[m.index] = m.motor_current_a
            table(wv.cable_rows(checked.project, currents))
        if two is not None:
            st.markdown("**Losses per segment** (W) at hover, V1, V2 — segments inside the test data marked")
            chain_rows = tpv.chain_rows(two)
            table(chain_rows)
            points = [c for c in chain_rows[0] if c.endswith("loss (W)")]
            fig = go.Figure([go.Bar(name=p.replace(" loss (W)", ""), x=[r["segment"] for r in chain_rows],
                                    y=[r[p] for r in chain_rows]) for p in points])
            fig.update_layout(barmode="group", yaxis_title="loss (W)", height=380, margin={"l": 10, "r": 10, "t": 30, "b": 10})
            st.plotly_chart(fig, width="stretch", key="chain.losses")
        else:
            st.info("Press Run to compute the losses (the cable gauges then use the hover currents).")

data = {k: v for k, v in data.items() if v is not None and v != {}}
app.data = data
checked = ui_state.check(data)

with tabs["Hover"]:
    if two is None:
        st.info("Press Run to compute the hover operating points.")
    else:
        st.markdown(f"Thrust of each lift motor from the mass and the balance of moments about the CG "
                    f"(x = {two.hover.cg_x_mm:.0f} mm). **Front / rear thrust ratio "
                    f"{tpv.fmt(two.hover.front_rear_ratio, '.2f')}**; hover battery power "
                    f"{two.hover.battery_power_w:.0f} ± {two.hover.battery_power_sd_w:.0f} W.")
        table(tpv.hover_rows(two))
        for pair, motors in hv.pairs(two).items():
            with st.container(border=True):
                st.plotly_chart(hv.pair_figure(two, pair), width="stretch", key=f"hover.{pair}")
                near = hv.points_near_rows(motors[0])
                if near:
                    st.caption("Test points closest to the operating thrust")
                    table(near)
                else:
                    st.caption("No test data for this pair: power predicted from similar pairs (larger uncertainty).")
    with st.expander("Error guarantee of the thrust–power surrogate (validation on the stored data)"):
        summary, per_pair = hv.validation_rows()
        table(summary)
        table(per_pair)
    with st.expander("Thrust–power test data (manufacturer tables)"):
        table([{"test": t.id, "motor": t.motor_id, "propeller": t.propeller_id, "voltage (V)": t.voltage_v,
                "points": len(t.thrust_n), "measured at": t.measured_at, "ESC": t.esc, "source": t.source}
               for t in default_tests().records.values()])

with tabs["Propeller sizing"]:
    with st.expander("How to choose the pitch"):
        st.markdown(pc.__doc__.split("\n\n", 2)[2])
    st.markdown("**Cruise motors** (cruise and tilting): the pitch is sized at the two cruise operating points, the "
                "target speeds V1 and V2 with the thrust each motor must give there (cruise drag of the last Run). "
                "**Lift-only motors**: sized in hover.")
    if two is None or checked.project is None:
        st.info("Press Run: the pitch is sized at the thrusts of the target speeds V1 and V2.")
    else:
        aircraft = AircraftModel(checked.project)
        for name, spec in checked.project.propulsion_units.items():
            with st.container(border=True):
                st.markdown(f"**{name}** — {spec.motor_id}, {spec.prop_diameter_in:g} x "
                            f"{tpv.fmt(spec.prop_pitch_in, 'g')} in; database propellers of this diameter: "
                            f"{', '.join(ps.database_propellers(spec.prop_diameter_in)) or 'none'}")
                rows, rec = ps.cruise_pitch_rows(aircraft, two, name)
                if rows:
                    points = [(c.index, c.v_m_s, m.thrust_n) for c in two.cruise for m in c.motors if m.unit == name][:2]
                    st.markdown("**Sizing point: cruise** — " + "; ".join(
                        f"V{k} = {v:.1f} m/s ({3.6 * v:.0f} km/h), thrust {t:.2f} N per motor" for k, v, t in points)
                        + " (thrust = cruise drag shared by the cruise motors, from the last Run).")
                    st.plotly_chart(ps.pitch_figure(rows, rec, f"{name}: efficiency versus pitch at the cruise points"),
                                    width="stretch", key=f"pitch.{name}")
                    table(rec)
                    with st.expander("Values per pitch"):
                        table(rows)
                    best = rec.get("best compromise V1 + V2 (in)")
                    if best is not None and st.button(f"Use {best:g} in for '{name}'", key=f"{gen}:usepitch.{name}"):
                        app.data["propulsion_units"][name]["prop_pitch_in"] = best
                        app.data["propulsion_units"][name].pop("propeller_id", None)
                        st.rerun()
                else:
                    hover_motors = [m for m in two.hover.motors if m.unit == name]
                    if hover_motors:
                        st.caption(f"'{name}' only lifts: its pitch is sized in hover, at the hover thrust of "
                                   f"{hover_motors[0].thrust_n / 9.81 * 1000:.0f} g per motor (lowest electric power).")
                        unit = aircraft.units[name]
                        table(pc.hover_pitch_rows(unit, spec.prop_diameter_in, pc.default_pitches(spec.prop_diameter_in),
                                                  hover_motors[0].thrust_n, aircraft.rho, two.hover.chain.bus_voltage_v))

with tabs["Test data"]:
    st.subheader("Measured flight points")
    data["test_data"] = forms.render_items(st, FlightPoint, data.get("test_data") or [], "test_data", errors, gen)
    if checked.project is not None and checked.project.test_data and st.button("Compare with the model"):
        try:
            backend = backend_for(checked.project) if ui_state.excel_available() is None else None
            st.session_state["comparison"] = tdv.compare_points(checked.project, backend)
        except Exception as error:  # noqa: BLE001
            st.error(f"Comparison failed: {error}")
    if st.session_state.get("comparison"):
        st.caption("Model without calibration, at the mass and conditions of each point.")
        table(st.session_state["comparison"])
    with st.expander("Calibration (scenario mode)"):
        calibration = dict(data.get("calibration") or {})
        c1, c2 = st.columns(2)
        for column, point, model_cls, default in (
            (c1, "hover", HoverReference, {"battery_power_w": 200.0}),
            (c2, "cruise", CruiseReference, {"speed_m_s": 15.0, "battery_power_w": 100.0}),
        ):
            with column:
                if st.checkbox(f"Calibrate on a {point} point", value=calibration.get(point) is not None,
                               key=f"{gen}:calibration.{point}.on"):
                    calibration[point] = forms.render_model(st, model_cls, calibration.get(point) or default,
                                                             f"calibration.{point}", errors, {}, gen)
                else:
                    calibration.pop(point, None)
        data["calibration"] = calibration if (calibration.get("hover") or calibration.get("cruise")) else None
        st.markdown(CALIBRATION_DOC)
    data = {k: v for k, v in data.items() if v is not None and v != {}}
    app.data = data

checked = ui_state.check(data)

# --- sidebar: validation, Run, save ------------------------------------------------------
with st.sidebar:
    if checked.missing:
        st.warning("Required fields missing: " + ", ".join(checked.missing))
    elif checked.errors:
        st.error("Invalid project:\n\n" + "\n\n".join(f"`{p or 'project'}`: {m}" for p, m in checked.errors.items()))
    excel_reason = ui_state.excel_available(data.get("aero", {}).get("profile", "SD7003")) if architecture == "quadplane" else None
    if excel_reason:
        st.info(excel_reason)
    run = st.button("Run", type="primary", disabled=not ui_state.run_enabled(checked) or bool(excel_reason),
                    help="Two-phase flight time (and the scenario mode).")
    st.divider()
    default_name = (f"{app.source_path.stem}_copy.yaml" if app.source_path else f"{data.get('name', 'project')}.yaml")
    target = st.text_input("Save as", default_name, key=f"{gen}:save_as")
    if st.button("Save", disabled=checked.project is None):
        st.success(f"Saved {ui_state.save_project(data, target).resolve()}")
    if checked.project is not None:
        st.download_button("Download YAML", yaml.safe_dump(checked.project.to_dict(), sort_keys=False,
                                                           allow_unicode=True), file_name=Path(target).name)

if run:
    with st.spinner("Evaluating…" + (" (PredimRC)" if architecture == "quadplane" else "")):
        try:
            backend = backend_for(checked.project)
            app.two_phase = evaluate_two_phase(checked.project, backend=backend)
            scenario_name = st.session_state.get(f"{gen}:scenario")
            app.result = evaluate(checked.project, scenario_name, backend=backend)
            app.result_key = ui_state.project_key(data)
            st.rerun()
        except Exception as error:  # noqa: BLE001
            st.error(f"Evaluation failed: {error}")
            with st.expander("Details"):
                st.code(traceback.format_exc())

with tabs["Results"]:
    if two is None:
        st.info("Press Run to compute the flight time.")
    else:
        if app.outdated:
            st.warning("Outdated: the project changed since this result. Press Run to update.")
        st.subheader("Flight time — hover then cruise (designer's process)")
        st.markdown(("feasible" if two.feasible else f":red[infeasible] (limiting: {two.limiting})")
                    + f" — hover {two.hover_time_s:.0f} s, reserve {100 * two.reserve_fraction:.0f} % of the nominal "
                    f"energy ({two.energy_nominal_j / 3600:.1f} Wh nominal, {two.energy_available_j / 3600:.1f} Wh available)")
        for row in tpv.kpi_rows(two):
            for col, (label, text, negative) in zip(st.columns(len(row)), row):
                metric(col, label, text, negative)
        for w in two.warnings:
            st.warning(w)
        for c in two.cruise:
            st.caption(f"V{c.index}: " + two.hand_check(c.index))
        st.markdown(f"Front / rear thrust ratio **{tpv.fmt(two.hover.front_rear_ratio, '.2f')}** — data behind each "
                    "power: Hover tab (test points, surrogate), Cruise tab (PredimRC), Power chain tab (losses).")
        left, right = st.columns(2)
        with left:
            table(tpv.hover_rows(two))
        with right:
            table(tpv.cruise_rows(two))
    result = app.result
    if result is not None:
        with st.expander("Scenario mode (MVP solver)"):
            st.markdown(f"**Scenario `{result.scenario}`** — "
                        + ("feasible" if result.feasible else f":red[infeasible] (limiting: {result.limiting})"))
            tiles = charts.kpis(result)
            for row in range(0, len(tiles), 5):
                for col, kpi in zip(st.columns(5), tiles[row:row + 5]):
                    metric(col, kpi.label, kpi.text(), kpi.negative)
            c1, c2 = st.columns(2)
            c1.plotly_chart(charts.power_figure(result), width="stretch")
            c2.plotly_chart(charts.mass_figure(result), width="stretch")
            table(charts.segment_rows(result))

# --- exploration, optimisation, studies --------------------------------------------------
try:
    from predimrc_wrapper.mdo.explore import explore
    from predimrc_wrapper.mdo.explore import pareto_mask
    from predimrc_wrapper.mdo.explore import study_from_optimisation
    from predimrc_wrapper.mdo.optimise import CONSTRAINTS_TWO_PHASE
    from predimrc_wrapper.mdo.optimise import available_algorithms
    from predimrc_wrapper.mdo.optimise import optimise
    from predimrc_wrapper.mdo.parameters import expand_overrides
    from predimrc_wrapper.mdo.studies import StudyStore
    from predimrc_wrapper.ui import optimisation as opt
    from predimrc_wrapper.ui import studies_view as sv
    MDO = True
except ImportError:
    MDO = False

TWO_PHASE_OBJECTIVES = {"flight_time_v1": "Maximise the flight time at V1", "flight_time_v2": "Maximise the flight time at V2",
                        "range_v2": "Maximise the range at V2", "mass_total": "Minimise the total mass"}


def _choices_ui(project: Project, prefix: str) -> dict[str, list]:
    """Motors and propellers per unit type, cell count."""
    out = {}
    cols = st.columns(len(project.propulsion_units) + 1)
    for col, (name, unit) in zip(cols, project.propulsion_units.items()):
        motor_options = list(dict.fromkeys([unit.motor_id, *(next((r.candidates for r in ranges or [] if r.unit == name),
                                                                  None) or db.ids())]))
        motors = col.multiselect(f"Motors of '{name}'", motor_options, default=[unit.motor_id],
                                 key=f"{gen}:{prefix}.motors.{name}", help=HELP.tooltip("propulsion_units.*.motor_id"))
        if motors and motors != [unit.motor_id]:
            out[f"propulsion_units.{name}.motor_id"] = motors
        props = col.multiselect(f"Propellers of '{name}' (database)", default_propellers().ids(),
                                key=f"{gen}:{prefix}.props.{name}", help=HELP.tooltip("propulsion_units.*.propeller_id"))
        if props:
            out[f"propulsion_units.{name}.propeller"] = props
    cells = cols[-1].multiselect("Cells in series", list(range(2, 13)), default=[project.battery.n_series],
                                 key=f"{gen}:{prefix}.cells", help=HELP.tooltip("battery.n_series"))
    if cells and cells != [project.battery.n_series]:
        out["battery.n_series"] = cells
    return out


def _variables_ui(project: Project, prefix: str):
    rows = st.session_state.setdefault(f"{gen}:{prefix}.rows", opt.default_variables(project))
    edited = st.data_editor(rows, key=f"{gen}:{prefix}.table", hide_index=True, width="stretch", disabled=["name", "path"])
    return opt.to_parameters(list(edited))


def _apply(project: Project, overrides: dict) -> None:
    app.load(project.with_overrides(expand_overrides(overrides)).to_dict(), app.source_path)
    st.rerun()


with tabs["Exploration"]:
    if not MDO:
        st.info("The exploration needs GEMSEO: pip install 'predimrc_wrapper[mdo]'.")
    elif checked.project is None:
        st.info("The exploration is set up once the project is valid.")
    else:
        project = checked.project
        st.markdown("Design of experiments on the continuous variables × every combination of the categorical "
                    "choices, two-phase flight time at each point. The study is stored in the studies folder.")
        variables = _variables_ui(project, "exp")
        choices = _choices_ui(project, "exp")
        c1, c2, c3, c4 = st.columns(4)
        method = c1.selectbox("Design", ["lhs", "full_factorial"], key=f"{gen}:exp.method",
                              help="Latin hypercube (lhs) or full factorial grid.")
        n = int(c2.number_input("Points per combination", 2, 500, 10, key=f"{gen}:exp.n"))
        seed = int(c3.number_input("Seed", 0, 10_000, 0, key=f"{gen}:exp.seed"))
        name = c4.text_input("Study name", f"exploration {project.name}", key=f"{gen}:exp.name")
        n_combos = int(np.prod([len(v) for v in choices.values()])) if choices else 1
        st.caption(f"{n_combos} combination(s) × {n} points")
        if st.button("Run the exploration", type="primary"):
            bar = st.progress(0.0, text="Starting…")
            try:
                study = explore(project, variables, choices, method, n, seed, backend=backend_for(project), name=name,
                                progress=lambda i, t: bar.progress(i / max(t, 1), text=f"Point {i + 1}/{t}"))
                StudyStore(Settings.load().studies_root).save(study)
                st.session_state["last_exploration"] = study
                bar.progress(1.0, text=f"Done — saved in {study.path}")
            except Exception as error:  # noqa: BLE001
                st.error(f"Exploration failed: {error}")
                with st.expander("Details"):
                    st.code(traceback.format_exc())
        study = st.session_state.get("last_exploration")
        if study is not None:
            cols = sv.numeric_columns(study.points)
            c1, c2 = st.columns(2)
            x = c1.selectbox("x", cols, index=cols.index("mass_total") if "mass_total" in cols else 0, key="exp.x")
            y = c2.selectbox("y", cols, index=cols.index("flight_time_v2") if "flight_time_v2" in cols else 0, key="exp.y")
            mask = pareto_mask(study.points, [("flight_time_v2", True), ("mass_total", False)])
            st.plotly_chart(sv.scatter_figure([study], x, y, [mask]), width="stretch", key="exp.scatter")
            table(sv.point_rows(study))

with tabs["Optimisation"]:
    if not MDO:
        st.info("The optimisation needs GEMSEO: pip install 'predimrc_wrapper[mdo]' (gemseo[all] for COBYLA).")
    elif checked.project is None:
        st.info("The optimisation is set up once the project is valid.")
    else:
        project = checked.project
        st.markdown("Outer loop over the categorical choices (motors, propellers, cells), optimiser on the continuous "
                    "variables, margins ≥ 0. Two-phase flight time; the study is stored.")
        c1, c2, c3 = st.columns(3)
        objective = c1.selectbox("Objective", list(TWO_PHASE_OBJECTIVES), format_func=TWO_PHASE_OBJECTIVES.get,
                                 key=f"{gen}:opt.objective")
        algo = c2.selectbox("Algorithm", available_algorithms(), key=f"{gen}:opt.algo",
                            help="SLSQP: gradient by finite differences; NLOPT_COBYLA, COBYQA: gradient-free.")
        max_iter = int(c3.number_input("Iterations per choice", 5, 500, 40, key=f"{gen}:opt.max_iter"))
        variables = _variables_ui(project, "opt")
        choices = _choices_ui(project, "opt")
        constraints = st.multiselect("Constraints (≥ 0)", ["margin_motor_power", "margin_motor_current",
                                                            "margin_hover_thrust", "margin_thrust_to_weight",
                                                            "margin_battery_c", "margin_mass"],
                                     default=list(CONSTRAINTS_TWO_PHASE), key=f"{gen}:opt.constraints")
        sd_on = st.checkbox("Constrain the surrogate uncertainty (σ_rel ≤ 5 %)", value=True, key=f"{gen}:opt.sd",
                            help=HELP.tooltip("max_sd_rel"))
        if st.button("Run the optimisation", type="primary"):
            bar = st.progress(0.0, text="Starting…")
            try:
                summary = optimise(project, variables, choices, objective=objective, constraints=tuple(constraints),
                                   algo=algo, max_iter=max_iter, backend=backend_for(project),
                                   progress=lambda i, n_, c: bar.progress(i / n_, text=f"Combination {i + 1}/{n_}: {c or 'base'}"),
                                   max_sd_rel=0.05 if sd_on else None)
                study = study_from_optimisation(summary, project, variables, choices, constraints, algo, max_iter,
                                                name=f"optimisation {project.name}", max_sd_rel=0.05 if sd_on else None)
                StudyStore(Settings.load().studies_root).save(study)
                st.session_state["optimisation"] = {"summary": summary, "continuous": variables, "study": study}
                bar.progress(1.0, text=f"Done in {summary.seconds:.0f} s — saved in {study.path}")
            except Exception as error:  # noqa: BLE001
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
                st.markdown(f"**Best:** {best.choice or 'base design'} — {summary.objective} = "
                            f"{best.outputs[summary.objective]:.4g}, " + ("feasible" if best.feasible else ":red[infeasible]"))
                if st.button("Apply the best design to the project"):
                    _apply(project, summary.best_overrides(stored["continuous"]))
            c1, c2 = st.columns([3, 2])
            with c1:
                table(sv.point_rows(stored["study"]))
            c2.plotly_chart(opt.history_figure(summary), width="stretch", key="opt.history")

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
            table([{k: s[k] for k in ("id", "name", "kind", "mode", "date", "points")} for s in listing])
            ids = [s["id"] for s in listing]
            chosen = st.multiselect("Open (one, or two to compare)", ids, default=ids[:1], max_selections=2,
                                    key="studies.open")
            studies = [store.load(i) for i in chosen]
            if studies:
                cols = sorted(set.intersection(*[set(sv.numeric_columns(s.points)) for s in studies]))
                c1, c2 = st.columns(2)
                x = c1.selectbox("x", cols, index=cols.index("mass_total") if "mass_total" in cols else 0, key="studies.x")
                y = c2.selectbox("y", cols, index=cols.index("flight_time_v2") if "flight_time_v2" in cols else 0,
                                 key="studies.y")
                masks = [pareto_mask(s.points, [("flight_time_v2", True), ("mass_total", False)]) for s in studies]
                st.plotly_chart(sv.scatter_figure(studies, x, y, masks), width="stretch", key="studies.scatter")
                for s in studies:
                    with st.container(border=True):
                        st.markdown(f"**{s.name}** ({s.definition.kind}, {s.definition.mode}) — {s.metadata.get('date')}"
                                    + (" — :orange[data changed since this study]" if StudyStore.data_changed(s) else ""))
                        table(sv.point_rows(s))
                        c1, c2, c3 = st.columns(3)
                        index = int(c1.number_input("Point to apply (row)", 0, max(0, len(s.points) - 1), 0,
                                                    key=f"studies.apply.{s.id}"))
                        if c1.button("Apply this point to the project", key=f"studies.applybtn.{s.id}"):
                            _apply(Project.model_validate(s.base_project), sv.overrides_of(s, index))
                        new_name = c2.text_input("Rename", s.name, key=f"studies.rename.{s.id}")
                        if c2.button("Rename", key=f"studies.renamebtn.{s.id}") and new_name != s.name:
                            store.rename(s.id, new_name)
                            st.rerun()
                        if c3.button("Delete", key=f"studies.delete.{s.id}"):
                            store.delete(s.id)
                            st.rerun()
