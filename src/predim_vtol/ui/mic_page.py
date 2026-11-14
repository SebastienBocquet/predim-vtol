"""MIC cards page (REQ-UI-009): list and render the model identity cards."""

from __future__ import annotations

import re

from predim_vtol.core.mic import CARDS_DIR

TITLE = re.compile(r"^# (MIC-[A-Z0-9-]+) — (.*)$", re.MULTILINE)
STATUS = re.compile(r"\*\*Verification status:\*\* ([^\n]*)")
TRACEABILITY = re.compile(r"^## Traceability\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
"""Links to the development specifications, not shown to the users."""


def cards() -> list[dict[str, str]]:
    """Id, title, verification status and path of every card."""
    out = []
    for path in sorted(CARDS_DIR.glob("MIC-*.md")):
        text = path.read_text(encoding="utf-8")
        m = TITLE.search(text)
        s = STATUS.search(text)
        out.append({
            "id": m.group(1) if m else path.stem,
            "title": m.group(2) if m else path.stem,
            "verification": s.group(1).strip() if s else "",
            "path": str(path),
        })
    return out


def render_text(card_id: str) -> str:
    """Markdown of a card for the users: Mermaid blocks shown as code, no traceability."""
    text = (CARDS_DIR / f"{card_id}.md").read_text(encoding="utf-8")
    text = text.replace("<!-- interface:start -->", "").replace(
        "<!-- interface:end -->", ""
    )
    return TRACEABILITY.sub("", text).rstrip() + "\n"
