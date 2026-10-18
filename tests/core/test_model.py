"""Tests of the Model foundation (MVP-002)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.core import Model
from predimrc_wrapper.core import Param
from predimrc_wrapper.core import Port
from predimrc_wrapper.core import ScalingLaw
from predimrc_wrapper.core import params
from predimrc_wrapper.core import ports
from predimrc_wrapper.core.mic import write_interface


class _Square(Model):
    mic_id = "MIC-TEST-SQUARE"
    inputs = ports(Port("x", "x", "m", "input", (0, None)))
    outputs = ports(Port("y", "y", "m²", "output"))
    parameters = params(
        Param("k", "k", "—", "gain", default=2.0, bounds=(0, None), source="test"),
        Param("c", "c", "m²", "offset", origin="project"),
    )
    expected_forms = [ScalingLaw("y", "x", 2.0, params={"c": 0.0})]

    def evaluate(self, x):
        return {"y": self.p.k * x["x"] ** 2 + self.p.c}


def test_missing_required_parameter():
    with pytest.raises(ValueError, match="'c' is required"):
        _Square()


def test_unknown_parameter():
    with pytest.raises(ValueError, match="unknown parameters"):
        _Square(c=0.0, z=1.0)


def test_parameter_out_of_bounds():
    with pytest.raises(ValueError, match="below its physical lower bound"):
        _Square(k=-1.0, c=0.0)


def test_check_io():
    model = _Square(c=0.0)
    model.check = True
    with pytest.raises(ValueError, match="x = -1"):
        model({"x": -1.0})
    assert model({"x": 2.0})["y"] == 8.0


def test_evaluate_does_not_mutate_input():
    x = {"x": 3.0}
    _Square(c=1.0).evaluate(x)
    assert x == {"x": 3.0}


def test_describe_tables():
    md = _Square.describe().to_markdown()
    assert "| `k` | k | — | gain | 2.0 | ≥ 0 | test |" in md
    assert "| `c` | c | m² | offset | project | — | — |" in md
    assert "### Inputs" in md and "### Outputs" in md


def test_write_interface(tmp_path):
    card = tmp_path / "card.md"
    card.write_text("# t\n<!-- interface:start -->\nold\n<!-- interface:end -->\nend\n", encoding="utf-8")
    assert write_interface(_Square, card)
    text = card.read_text(encoding="utf-8")
    assert "old" not in text and "`k`" in text and text.endswith("end\n")
    assert not write_interface(_Square, card)


def test_scaling_law_slope():
    law = _Square.expected_forms[0]
    assert law.slope(_Square(**law.params)) == pytest.approx(2.0, abs=1e-9)
