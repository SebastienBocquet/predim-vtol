"""MIC cards page (REQ-UI-009): list and render the model identity cards."""

from __future__ import annotations

import re
from pathlib import Path

TITLE = re.compile(r"^# (MIC-[A-Z0-9-]+) — (.*)$", re.MULTILINE)
STATUS = re.compile(r"\*\*Verification status:\*\* ([^\n]*)")


def cards_dir() -> Path | None:
    """Folder of the cards: the repository's ``mvp/docs/models`` (development install)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "mvp" / "docs" / "models"
        if candidate.is_dir():
            return candidate
    return None


def cards() -> list[dict[str, str]]:
    """Id, title, verification status and path of every card."""
    folder = cards_dir()
    out = []
    if folder is None:
        return out
    for path in sorted(folder.glob("MIC-*.md")):
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
    """Markdown of a card, Mermaid blocks shown as code."""
    folder = cards_dir()
    text = (folder / f"{card_id}.md").read_text(encoding="utf-8")
    return text.replace("<!-- interface:start -->", "").replace(
        "<!-- interface:end -->", ""
    )
