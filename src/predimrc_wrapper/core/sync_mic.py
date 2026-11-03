"""Regenerate the Interface section of the MVP MIC cards from the code.

Usage: ``python -m predimrc_wrapper.core.sync_mic [cards_dir]``.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path

from predimrc_wrapper.core.mic import write_interface
from predimrc_wrapper.core.model import REGISTRY

DEFAULT_CARDS = Path(__file__).resolve().parents[3] / "docs" / "models"


def main(cards: Path = DEFAULT_CARDS) -> None:
    """Write the generated Interface into every existing card."""
    for module in (
        "propulsion",
        "aircraft",
        "mission.powers",
        "mission.two_phase",
        "sizing",
    ):
        with contextlib.suppress(ModuleNotFoundError):
            importlib.import_module(f"predimrc_wrapper.{module}")
    for mic_id, model_cls in sorted(REGISTRY.items()):
        card = cards / f"{mic_id}.md"
        if mic_id.startswith("MIC-TEST") or not card.is_file():
            continue
        changed = write_interface(model_cls, card)
        print(f"{mic_id}: {'updated' if changed else 'unchanged'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CARDS)
