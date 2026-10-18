"""Generation of the Interface section of the MIC cards from the model declarations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from predimrc_wrapper.core.model import Model

START = "<!-- interface:start -->"
END = "<!-- interface:end -->"


def _bounds(bounds: tuple) -> str:
    lower, upper = bounds
    if lower is None and upper is None:
        return "—"
    if upper is None:
        return f"≥ {lower:g}"
    if lower is None:
        return f"≤ {upper:g}"
    return f"[{lower:g}, {upper:g}]"


@dataclass(frozen=True)
class MicInterface:
    """The Interface tables of a MIC card."""

    inputs: list[list[str]]
    outputs: list[list[str]]
    parameters: list[list[str]]

    @classmethod
    def from_model(cls, model_cls: type[Model]) -> MicInterface:
        """Build the tables from the class-level declarations of a model."""

        def port_rows(items) -> list[list[str]]:
            return [
                [f"`{p.name}`", p.symbol, p.unit, p.description, _bounds(p.physical_bounds)]
                for p in items.values()
            ]

        return cls(
            inputs=port_rows(model_cls.inputs),
            outputs=port_rows(model_cls.outputs),
            parameters=[
                [f"`{p.name}`", p.symbol, p.unit, p.description, p.default_or_origin,
                 _bounds(p.bounds), p.source or "—"]
                for p in model_cls.parameters.values()
            ],
        )

    def to_markdown(self) -> str:
        """Render the three tables as Markdown."""

        def table(title: str, header: list[str], rows: list[list[str]]) -> str:
            lines = [f"### {title}", ""]
            if not rows:
                return "\n".join([*lines, "None."])
            lines.append("| " + " | ".join(header) + " |")
            lines.append("|" + "---|" * len(header))
            lines += ["| " + " | ".join(c.replace("|", r"\|") for c in r) + " |" for r in rows]
            return "\n".join(lines)

        port_header = ["Name", "Symbol", "Unit", "Description", "Physical bounds"]
        return "\n\n".join([
            table("Inputs", port_header, self.inputs),
            table("Outputs", port_header, self.outputs),
            table(
                "Parameters",
                ["Name", "Symbol", "Unit", "Description", "Default / origin",
                 "Physical bounds", "Source"],
                self.parameters,
            ),
        ])


def write_interface(model_cls: type[Model], card: Path) -> bool:
    """Replace the Interface section of a MIC card by the generated one.

    Args:
        model_cls: The model class.
        card: The Markdown card, containing the interface markers.

    Returns:
        Whether the card changed.
    """
    text = card.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        msg = f"{card}: interface markers not found."
        raise ValueError(msg)
    block = f"{START}\n{model_cls.describe().to_markdown()}\n{END}"
    new = pattern.sub(lambda _: block, text)
    if new != text:
        card.write_text(new, encoding="utf-8")
        return True
    return False
