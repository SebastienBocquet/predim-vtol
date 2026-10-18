"""Forms generated from the project schema (REQ-UI-001, REQ-UI-006).

The pure helpers (levels, badges, labels, table conversions) are tested without
Streamlit; ``render_model`` draws the widgets and returns the edited values.
"""

from __future__ import annotations

import contextlib
import math
import types
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import Union
from typing import get_args
from typing import get_origin

import annotated_types
from pydantic import BaseModel

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

_UNSET = object()

HELP = None
"""Callable ``path -> tooltip`` set by the app (``ui.help.HelpRegistry``); None: field descriptions."""


def _help(path: str, fallback: str | None = None) -> str | None:
    return HELP(path) if HELP is not None else fallback


# --- pure helpers ------------------------------------------------------------


def field_level(info: FieldInfo) -> str:
    """``required``, ``default`` or ``advanced`` (fields without a level count as default)."""
    return (info.json_schema_extra or {}).get(
        "level", "required" if info.is_required() else "default"
    )


def field_badge(info: FieldInfo, value: Any = _UNSET) -> str:
    """``required``, ``advanced``, or for a default-level field ``default`` / ``entered``."""
    level = field_level(info)
    if level != "default":
        return level
    return "default" if value is _UNSET or value == info.default else "entered"


KMH_PER_M_S = 3.6


def is_airspeed(name: str) -> bool:
    """Airspeeds (``*speed*_m_s`` fields, not vertical) are shown and entered in km/h (REQ-NFR-002)."""
    return name.endswith("_m_s") and "speed" in name and "vertical" not in name


def _display_label(label: str, name: str) -> str:
    return label.replace("(m/s)", "(km/h)") if is_airspeed(name) else label


def field_label(name: str, info: FieldInfo, value: Any = _UNSET) -> str:
    label = _display_label(info.description or name.replace("_", " "), name)
    badge = field_badge(info, value)
    if badge == "required":
        return f"{label} *"
    if badge in ("default", "entered"):
        return f"{label} — {badge}"
    return label


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """(annotation without None, whether None is allowed)."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) < len(get_args(annotation)):
            return (args[0] if len(args) == 1 else Union[tuple(args)]), True  # ruff: ignore[non-pep604-annotation-union]
    return annotation, False


def is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def bounds(info: FieldInfo) -> tuple[float | None, float | None]:
    """(min, max) usable by a number input: only inclusive bounds."""
    low = high = None
    for m in info.metadata:
        if isinstance(m, annotated_types.Ge):
            low = m.ge
        elif isinstance(m, annotated_types.Le):
            high = m.le
    return low, high


def panel_fields(model_cls: type[BaseModel]) -> list[str]:
    """The ``list[float]`` fields edited together as a panel table."""
    return [n for n, f in model_cls.model_fields.items() if f.annotation == list[float]]


def panels_to_rows(
    values: dict[str, Any], names: list[str], n_panels: int
) -> dict[str, list[float]]:
    """Rows of the panel table, truncated or padded with the last value to ``n_panels``."""
    rows = {}
    for name in names:
        current = list(values.get(name) or [0.0])
        rows[name] = (current + [current[-1]] * n_panels)[:n_panels]
    return rows


def _empty(value: Any) -> bool:
    return (
        value is None or value == "" or (isinstance(value, float) and math.isnan(value))
    )


def rows_to_items(
    rows: list[dict[str, Any]], item_cls: type[BaseModel]
) -> list[dict[str, Any]]:
    """Table rows to item dicts: empty cells removed, numbers restored in text columns."""
    items = []
    for row in rows:
        item = {}
        for name, value in row.items():
            if _empty(value) or name not in item_cls.model_fields:
                continue
            if isinstance(value, str):
                with contextlib.suppress(ValueError):
                    value = float(value)
            if hasattr(value, "item"):  # numpy scalar
                value = value.item()
            item[name] = value
        if item:
            items.append(item)
    return items


# --- Streamlit ---------------------------------------------------------------


def _key(path: str, generation: int) -> str:
    return f"{generation}:{path}"


def _show_errors(st, path: str, errors: dict[str, str], prefix: bool = False) -> None:
    for p, msg in errors.items():
        if p == path or (prefix and p.startswith(f"{path}.")):
            st.error(f"{p}: {msg}" if prefix else msg)


def _column_config(
    st,
    item_cls: type[BaseModel],
    options: dict[str, list[str]] | None = None,
    path: str = "",
) -> dict[str, Any]:
    config = {}
    for name, info in item_cls.model_fields.items():
        ann, _ = unwrap_optional(info.annotation)
        label = _display_label(info.description or name, name)
        tip = _help(f"{path}.0.{name}", info.description)
        if options and name in options:
            config[name] = st.column_config.SelectboxColumn(
                label, options=list(options[name]), help=tip
            )
        elif get_origin(ann) is Literal:
            config[name] = st.column_config.SelectboxColumn(
                label, options=list(get_args(ann)), help=tip
            )
        elif ann is bool:
            config[name] = st.column_config.CheckboxColumn(label, help=tip)
        elif ann in (int, float):
            config[name] = st.column_config.NumberColumn(
                label, step=1 if ann is int else None, help=tip
            )
        else:
            config[name] = st.column_config.TextColumn(label, help=tip)
    return config


def render_items(
    st,
    item_cls: type[BaseModel],
    values: list[dict],
    path: str,
    errors: dict[str, str],
    generation: int,
    options: dict[str, list[str]] | None = None,
    key_suffix: str = "",
) -> list[dict]:
    """A list of models edited as one table; ``options`` gives the choices of text columns."""
    import pandas as pd  # noqa: PLC0415

    columns = list(item_cls.model_fields)
    frame = pd.DataFrame(
        [{c: v.get(c) for c in columns} for v in values], columns=columns
    )
    scaled = {n: KMH_PER_M_S for n in columns if is_airspeed(n)}
    for name, info in item_cls.model_fields.items():
        ann, _ = unwrap_optional(info.annotation)
        if not (ann in (int, float, bool) or get_origin(ann) is Literal):
            frame[name] = frame[name].map(lambda v: None if _empty(v) else str(v))
        elif name in scaled:
            frame[name] = frame[name].astype(float) * scaled[name]
    st.caption(
        "Add a row with ＋ at the bottom; delete rows by ticking them in the left column, then the bin icon "
        "at the top right of the table."
    )
    edited = st.data_editor(
        frame,
        key=_key(path, generation) + key_suffix,
        num_rows="dynamic",
        hide_index=False,
        column_config=_column_config(st, item_cls, options, path),
        width="stretch",
    )
    _show_errors(st, path, errors, prefix=True)
    records = edited.to_dict("records")
    for r in records:
        for name, factor in scaled.items():
            if not _empty(r.get(name)):
                r[name] = float(r[name]) / factor
    return rows_to_items(records, item_cls)


def _render_panels(
    st, model_cls, values, names, path, errors, generation
) -> dict[str, list[float]]:
    import pandas as pd  # noqa: PLC0415

    n0 = len(values.get(names[0]) or [1])
    n = int(
        st.number_input("Panels", 1, 5, n0, key=_key(f"{path}.n_panels", generation))
    )
    rows = panels_to_rows(values, names, n)
    frame = pd.DataFrame.from_dict(
        rows, orient="index", columns=[f"P{i + 1}" for i in range(n)]
    )
    frame.index = [model_cls.model_fields[k].description or k for k in names]
    edited = st.data_editor(
        frame, key=_key(f"{path}.panels.{n}", generation), width="stretch"
    )
    for name in names:
        _show_errors(st, f"{path}.{name}", errors, prefix=True)
    return {
        name: [float(v) for v in edited.iloc[i].tolist()]
        for i, name in enumerate(names)
    }


def render_field(
    st,
    name: str,
    info: FieldInfo,
    value: Any,
    path: str,
    errors: dict[str, str],
    choices: dict[str, list[str]],
    generation: int,
) -> Any:
    ann, optional = unwrap_optional(info.annotation)
    label = field_label(name, info, value)
    key = _key(path, generation)
    tip = _help(path, info.description)
    if path in choices:
        options = list(choices[path])
        if value not in options:
            options.insert(0, value)
        out = st.selectbox(
            label, options, index=options.index(value), key=key, help=tip
        )
    elif get_origin(ann) is Literal:
        options = list(get_args(ann))
        out = st.selectbox(
            label,
            options,
            index=options.index(value) if value in options else 0,
            key=key,
            help=tip,
        )
    elif ann is bool:
        out = st.checkbox(label, value=bool(value), key=key, help=tip)
    elif ann in (int, float):
        low, high = bounds(info)
        cast = int if ann is int else float
        airspeed = ann is float and is_airspeed(name)

        def shown(v):
            if v is None:
                return None
            return cast(v) * KMH_PER_M_S if airspeed else cast(v)

        out = st.number_input(
            label,
            value=shown(value),
            min_value=shown(low),
            max_value=shown(high),
            step=1 if ann is int else None,
            key=key,
            placeholder="not set" if optional else "required",
            help=tip,
        )
        if out is not None and airspeed:
            out /= KMH_PER_M_S
    else:
        out = st.text_input(
            label, value="" if value is None else str(value), key=key, help=tip
        )
        out = None if optional and out == "" else out
    _show_errors(st, path, errors)
    return out


def render_model(
    st,
    model_cls: type[BaseModel],
    values: dict[str, Any] | None,
    path: str = "",
    errors: dict[str, str] | None = None,
    choices: dict[str, list[str]] | None = None,
    generation: int = 0,
    skip: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Draw the widgets of a model and return the edited values (plain data)."""
    values, errors, choices = dict(values or {}), errors or {}, choices or {}
    out: dict[str, Any] = {}
    prefix = f"{path}." if path else ""
    panels = [p for p in panel_fields(model_cls) if p not in skip]
    if panels:
        out.update(
            _render_panels(st, model_cls, values, panels, path, errors, generation)
        )
    advanced = []
    for name, info in model_cls.model_fields.items():
        if name in skip or name in panels:
            continue
        if field_level(info) == "advanced":
            advanced.append((name, info))
            continue
        _render_one(st, name, info, values, prefix, errors, choices, generation, out)
    if advanced:
        with st.expander("Advanced"):
            for name, info in advanced:
                _render_one(
                    st, name, info, values, prefix, errors, choices, generation, out
                )
    return {k: v for k, v in out.items() if v is not None}


def _render_one(
    st, name, info, values, prefix, errors, choices, generation, out
) -> None:
    ann, _ = unwrap_optional(info.annotation)
    value = values.get(
        name,
        None if info.is_required() else info.get_default(call_default_factory=True),
    )
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    path = f"{prefix}{name}"
    if is_model(ann):
        if value is None:
            return
        st.markdown(f"**{info.description or name.replace('_', ' ')}**")
        out[name] = render_model(st, ann, value, path, errors, choices, generation)
    elif get_origin(ann) is list and is_model(get_args(ann)[0]):
        st.markdown(f"**{info.description or name.replace('_', ' ')}**")
        out[name] = render_items(
            st, get_args(ann)[0], value or [], path, errors, generation
        )
    else:
        out[name] = render_field(
            st, name, info, value, path, errors, choices, generation
        )
