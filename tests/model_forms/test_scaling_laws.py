"""Generic model-form tests: every registered model satisfies its declared relations.

These tests form level N0 of the credibility pyramid (REQ-VV-007 in the full
specification) and cover REQ-NFR-006 for the MVP.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from predimrc_wrapper.core import REGISTRY
from predimrc_wrapper.core import Invariant
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core.mic import END
from predimrc_wrapper.core.mic import START

# Import every package declaring models so that they are registered.
for _module in ("propulsion", "aircraft", "mission.solver", "mission.two_phase", "sizing"):
    try:
        importlib.import_module(f"predimrc_wrapper.{_module}")
    except ModuleNotFoundError:
        pass

CARDS = Path(__file__).resolve().parents[2] / "mvp" / "docs" / "models"
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
    card = CARDS / f"{mic_id}.md"
    assert card.is_file(), f"missing MIC card {card}"
    text = card.read_text(encoding="utf-8")
    current = text.split(START, 1)[1].split(END, 1)[0].strip()
    assert current == MODELS[mic_id].describe().to_markdown().strip(), (
        f"Interface of {card.name} is out of date: run "
        "`python -m predimrc_wrapper.core.sync_mic`."
    )
