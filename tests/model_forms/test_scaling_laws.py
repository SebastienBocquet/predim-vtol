"""Generic model-form tests: every registered model satisfies its declared relations.

These tests form level N0 of the credibility pyramid (REQ-VV-007 in the full
specification) and cover REQ-NFR-006 for the MVP.
"""

from __future__ import annotations

import contextlib
import importlib

import pytest

from predim_vtol.core import REGISTRY
from predim_vtol.core import Invariant
from predim_vtol.core import ScalingLaw
from predim_vtol.core.mic import CARDS_DIR
from predim_vtol.core.mic import END
from predim_vtol.core.mic import START

# Import every package declaring models so that they are registered.
for _module in (
    "propulsion",
    "aircraft",
    "mission.powers",
    "mission.two_phase",
    "sizing",
):
    with contextlib.suppress(ModuleNotFoundError):
        importlib.import_module(f"predim_vtol.{_module}")

MODELS = {k: v for k, v in REGISTRY.items() if not k.startswith("MIC-TEST")}
FORMS = [
    pytest.param(model_cls, form, id=f"{mic}:{i}")
    for mic, model_cls in MODELS.items()
    for i, form in enumerate(model_cls.expected_forms)
]


@pytest.mark.parametrize(("model_cls", "form"), FORMS)
def test_expected_form(model_cls, form):
    model = model_cls(**form.params)
    if isinstance(form, ScalingLaw):
        assert form.slope(model) == pytest.approx(form.exponent, abs=form.tol)
    else:
        assert isinstance(form, Invariant)
        assert form.check(model), form.description


@pytest.mark.parametrize("mic_id", sorted(MODELS))
def test_mic_card_interface_is_generated(mic_id):
    """The Interface section of the card equals the one generated from the code."""
    card = CARDS_DIR / f"{mic_id}.md"
    assert card.is_file(), f"missing MIC card {card}"
    text = card.read_text(encoding="utf-8")
    current = text.split(START, 1)[1].split(END, 1)[0].strip()
    assert current == MODELS[mic_id].describe().to_markdown().strip(), (
        f"Interface of {card.name} is out of date: run "
        "`python -m predim_vtol.core.sync_mic`."
    )
