"""Drag tab: the booms with their model, the drag sources form (REQ-CFG-004, REQ-CFG-014).

The drag sources are edited one form per source, with only the fields of its kind; a kind
chosen in a list and the Add button append a new source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from predimrc_wrapper.ui import forms

if TYPE_CHECKING:
    from predimrc_wrapper.aircraft import Project
    from predimrc_wrapper.mission.two_phase import TwoPhaseResult

BOOM_DRAG_LATEX = (
    r"D_i = \tfrac12\rho V^2\Big(C_{d,section}\,\sin^2\theta_i\;A_i + C_f\,p\,L_i\Big),"
    r"\qquad A_i = t\,L_i\,\sin\theta_i"
)
"""Drag of a diagonal boom (cross-flow principle on the frontal area, plus skin friction)."""


def boom_rows(project: Project, two: TwoPhaseResult | None = None) -> list[dict]:
    """One row per boom: geometry, frontal area, effective C_d, CdS and drag power at V1."""
    from predimrc_wrapper.aircraft import AircraftModel  # noqa: PLC0415
    from predimrc_wrapper.aircraft.booms import boom_drag  # noqa: PLC0415

    aircraft = AircraftModel(project)
    model = aircraft.drag_model
    v1 = two.cruise[0].v_m_s if two is not None and two.cruise else None
    rows = []
    for k, b in enumerate(boom_drag(project, model.p.boom_cf, model.p.boom_cd_end), 1):
        row = {
            "boom": k,
            "motors": ", ".join(str(i + 1) for i in b.boom.motors),
            "layout": b.layout,
            "section": b.section,
            "length (mm)": round(b.boom.length_mm),
            "angle to the flow θ (°)": round(b.boom.angle_to_flow_deg, 1),
            "frontal area (dm²)": round(100 * b.frontal_area_m2, 3),
            "C_d effective": None
            if not np.isfinite(b.cd_effective)
            else round(b.cd_effective, 3),
            "CdS (dm²)": round(100 * b.cds_m2, 4),
            "formula": b.formula,
            "coefficient source": b.coefficient_source,
        }
        if v1 is not None:
            row["drag power at V1 (W)"] = round(
                0.5 * aircraft.rho * v1**3 * b.cds_m2, 2
            )
        rows.append(row)
    return rows


SOURCE_KINDS = {
    "stopped_rotor": "Stopped rotor (lift propeller stopped in cruise)",
    "body_part": "Body part (shape + frontal area: camera, landing gear, pod...)",
    "v_arms": "V-arms (motor arms under the fuselage)",
    "cds": "Free drag area CdS",
    "boom": "Boom (prefer the booms of the configuration tab)",
}
"""Kinds offered by the Add list, with their label."""

SOURCE_FIELDS = {
    "stopped_rotor": ("count", "n_blades", "blade_chord_mm", "radius_mm"),
    "body_part": ("count", "shape", "frontal_area_dm2"),
    "v_arms": (
        "shape",
        "thickness_mm",
        "motors",
        "motor_z_mm",
        "attach_x_mm",
        "attach_z_mm",
        "attach_half_width_mm",
        "frontal_area_dm2",
    ),
    "cds": ("count", "cds_m2"),
    "boom": ("count", "diameter_mm", "length_mm"),
}
"""Fields of each kind shown after the name, the required ones first."""


def new_source(kind: str, names: list[str], shape: str) -> dict:
    """A new source of ``kind``: a free name, the default shape; the required numbers empty."""
    base = SOURCE_KINDS[kind].split(" (")[0].lower()
    name, k = base, 2
    while name in names:
        name, k = f"{base} {k}", k + 1
    source = {"name": name, "kind": kind}
    if "shape" in SOURCE_FIELDS[kind]:
        source["shape"] = shape
    return source


def render_sources(
    st,
    values: list[dict],
    errors: dict[str, str],
    generation: int,
    shapes: list[str],
    n_motors: int,
) -> list[dict]:
    """One form per drag source with the fields of its kind, a Remove button each, then the
    kind list and the Add button; returns the edited sources."""
    from predimrc_wrapper.aircraft.project import DragSource  # noqa: PLC0415

    fields = DragSource.model_fields
    # Removing a source shifts the next ones: a new version resets their widgets.
    version = st.session_state.setdefault("drag_sources.version", 0)
    gen = f"{generation}.{version}"
    out = []
    removed = None
    for i, source in enumerate(values):
        path = f"drag_sources.{i}"
        kind = source.get("kind", "cds")
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(
                f"**{source.get('name', '')}** — {SOURCE_KINDS.get(kind, kind)}"
            )
            if c2.button("Remove", key=forms._key(f"{path}.remove", gen)):
                removed = i
            edited = {"kind": kind}
            names = ("name", *SOURCE_FIELDS.get(kind, ()))
            columns = st.columns(2)
            for j, name in enumerate(names):
                with columns[j % 2]:
                    if name == "motors":
                        chosen = st.multiselect(
                            "Motors carried (all lift motors when empty)",
                            list(range(n_motors)),
                            default=[
                                m for m in source.get("motors") or [] if m < n_motors
                            ],
                            format_func=lambda m: f"motor {m + 1}",
                            key=forms._key(f"{path}.motors", gen),
                            help=fields["motors"].description,
                        )
                        edited["motors"] = chosen or None
                        continue
                    edited[name] = forms.render_field(
                        st,
                        name,
                        fields[name],
                        source.get(
                            name,
                            None
                            if fields[name].is_required()
                            else fields[name].get_default(),
                        ),
                        f"{path}.{name}",
                        errors,
                        {f"{path}.shape": shapes},
                        gen,
                    )
            if errors.get(path):
                st.error(errors[path])
        out.append({k: v for k, v in edited.items() if v is not None})
    if removed is not None:
        values[:] = out[:removed] + out[removed + 1 :]
        st.session_state["drag_sources.version"] = version + 1
        st.rerun()
    c1, c2 = st.columns([4, 1])
    kind = c1.selectbox(
        "Type of the new drag source",
        list(SOURCE_KINDS),
        format_func=SOURCE_KINDS.get,
        key=forms._key("drag_sources.new_kind", generation),
    )
    c2.markdown("&nbsp;")
    if c2.button("Add", key=forms._key("drag_sources.add", generation)):
        out.append(new_source(kind, [s.get("name") for s in out], shapes[0]))
        values[:] = out
        st.rerun()
    return out
