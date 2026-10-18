"""Help on every quantity of the GUI (REQ-UI-010).

One registry fed by (a) the project schema (field descriptions, units, defaults), (b) the
``Port`` / ``Param`` declarations of the models, (c) ``glossary.yaml`` for the displayed
quantities (KPI tiles, table columns, chart axes). A widget asks ``tooltip(key)``; a
missing entry falls back to the field description and is caught by the coverage test.
"""

from __future__ import annotations

import re
import types
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any
from typing import Union
from typing import get_args
from typing import get_origin

import yaml
from pydantic import BaseModel

UNIT_IN_TEXT = re.compile(r"\(([^()]*)\)\s*$")

CARDS = {
    "propulsion_units": "MIC-PROP-UNIT", "motors": "MIC-MIS-TWO", "cg_x_mm": "MIC-MIS-TWO", "cg_y_mm": "MIC-MIS-TWO",
    "battery": "MIC-PROP-BAT", "mass_items": "MIC-CFG-MASS", "max_takeoff_mass_kg": "MIC-CFG-MASS",
    "drag_sources": "MIC-CFG-DRAG", "body_cds_m2": "MIC-CFG-DRAG", "wiring": "MIC-PROP-CHAIN",
    "mission": "MIC-MIS-TWO", "sizing": "MIC-CFG-SIZ", "calibration": "MIC-CAL-REF", "test_data": "MIC-CAL-REF",
    "environment": "MIC-ATM-ISA", "scenarios": "MIC-MIS-SOL", "aero": "PredimRC (external model)",
}
"""MIC card of the model using each top-level project block."""


@dataclass(frozen=True)
class HelpEntry:
    """Definition of one quantity."""

    key: str
    name: str
    definition: str
    unit: str = ""
    symbol: str = ""
    default: str = ""
    default_source: str = ""
    model: str = ""

    def text(self) -> str:
        """Markdown tooltip."""
        parts = [f"**{self.name}**" + (f" ({self.symbol})" if self.symbol else ""), self.definition]
        if self.unit:
            parts.append(f"Unit: {self.unit}")
        if self.default:
            parts.append(f"Default: {self.default}" + (f" — source: {self.default_source}" if self.default_source else ""))
        if self.model:
            parts.append(f"Model card: {self.model}")
        return "  \n".join(parts)


def normalise(path: str) -> str:
    """Generic key of a project path: list indexes and propulsion unit names become ``*``."""
    keys = path.split(".")
    out = []
    for i, k in enumerate(keys):
        if k.isdigit() or (i == 1 and keys[0] in ("propulsion_units", "scenarios")):
            out.append("*")
        else:
            out.append(k)
    return ".".join(out)


def _models_of(annotation: Any) -> list[type[BaseModel]]:
    """Pydantic models inside an annotation (optional, list, dict values)."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    out = []
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType, list, dict):
        for arg in get_args(annotation):
            out += _models_of(arg)
    return out


def _container(annotation: Any) -> str:
    """``list`` or ``dict`` when the models are inside such a container."""
    for candidate in (annotation, *get_args(annotation)):
        if get_origin(candidate) in (list, dict):
            return "list"
    return ""


def schema_entries(model_cls: type[BaseModel], prefix: str = "", card: str = "") -> dict[str, HelpEntry]:
    """Entries of every field of a pydantic model, recursively."""
    entries = {}
    for name, info in model_cls.model_fields.items():
        key = f"{prefix}{name}"
        model = card or CARDS.get(name, "")
        subs = _models_of(info.annotation)
        description = info.description or ""
        unit_match = UNIT_IN_TEXT.search(description)
        default = "" if info.is_required() or info.default in (None, [], {}) else repr(info.default)
        extra = info.json_schema_extra or {}
        entries[key] = HelpEntry(
            key, name.replace("_", " "), description, unit_match.group(1) if unit_match else "", extra.get("symbol", ""),
            default, extra.get("source", "tool default" if default else ""), model)
        for sub in subs:
            sub_prefix = f"{key}.*." if (_container(info.annotation) or name in ("propulsion_units", "scenarios")) else f"{key}."
            entries.update(schema_entries(sub, sub_prefix, model))
    return entries


def model_entries() -> dict[str, HelpEntry]:
    """Entries of every port and parameter of the registered models, key ``<MIC>.<name>``."""
    import importlib  # noqa: PLC0415

    from predimrc_wrapper.core import REGISTRY  # noqa: PLC0415

    for module in ("propulsion", "aircraft", "mission.solver", "mission.two_phase", "sizing"):
        importlib.import_module(f"predimrc_wrapper.{module}")
    entries = {}
    for mic, cls in REGISTRY.items():
        if mic.startswith("MIC-TEST"):
            continue
        for port in (*cls.inputs.values(), *cls.outputs.values()):
            entries[f"{mic}.{port.name}"] = HelpEntry(f"{mic}.{port.name}", port.name, port.description,
                                                      "" if port.unit == "—" else port.unit, port.symbol, model=mic)
        for p in cls.parameters.values():
            entries[f"{mic}.{p.name}"] = HelpEntry(
                f"{mic}.{p.name}", p.name, p.description, "" if p.unit == "—" else p.unit, p.symbol,
                repr(p.default) if p.has_default else p.origin, p.source, mic)
    return entries


def glossary_entries() -> dict[str, HelpEntry]:
    """Displayed quantities of ``glossary.yaml``, keyed by their label."""
    data = yaml.safe_load(files("predimrc_wrapper.ui").joinpath("glossary.yaml").read_text(encoding="utf-8")) or {}
    return {label: HelpEntry(label, label, d["definition"], d.get("unit", ""), d.get("symbol", ""),
                             model=d.get("model", "")) for label, d in data.items()}


class HelpRegistry:
    """All the help entries."""

    def __init__(self, entries: dict[str, HelpEntry]) -> None:
        self.entries = entries

    @classmethod
    @cache
    def default(cls) -> HelpRegistry:
        from predimrc_wrapper.aircraft import Project  # noqa: PLC0415

        return cls({**model_entries(), **schema_entries(Project), **glossary_entries()})

    def entry(self, key: str) -> HelpEntry | None:
        return self.entries.get(key) or self.entries.get(normalise(key))

    def tooltip(self, key: str, fallback: str = "") -> str | None:
        e = self.entry(key)
        return e.text() if e else (fallback or None)

    def search(self, text: str) -> list[HelpEntry]:
        t = text.lower()
        return [e for e in self.entries.values() if t in e.key.lower() or t in e.name.lower() or t in e.definition.lower()]

    def missing(self, keys: list[str]) -> list[str]:
        """Keys without an entry or without a definition."""
        return [k for k in keys if (e := self.entry(k)) is None or not e.definition]
