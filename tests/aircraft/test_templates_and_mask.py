"""User templates, tilt mask, overlap message (REQ-CFG-013, REQ-CFG-002)."""

from __future__ import annotations

import pytest

from predimrc_wrapper.aircraft import Project
from predimrc_wrapper.aircraft import templates
from predimrc_wrapper.api import evaluate_two_phase
from tests.helpers import ParabolicAero


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDIMRC_TEMPLATES", str(tmp_path))
    return tmp_path


def test_user_template_round_trip(folder):
    project = Project.template("tiltrotor")
    path = templates.save_user(project.to_dict(), "my wing tricopter")
    assert path.parent == folder
    key = "user:my_wing_tricopter"
    assert key in templates.all_templates()
    assert Project.template(key).to_dict() == project.to_dict()
    with pytest.raises(FileExistsError):
        templates.save_user(project.to_dict(), "my wing tricopter")
    templates.rename_user(key, "renamed")
    assert "user:renamed" in templates.user_templates()
    templates.delete_user("user:renamed")
    assert templates.user_templates() == {}


def test_invalid_project_is_not_saved(folder):
    data = Project.template("tricopter").to_dict()
    data["motors"] = data["motors"][:2]
    with pytest.raises(ValueError, match="3"):
        templates.save_user(data, "broken")
    assert not list(folder.iterdir())


def test_rear_tilt_mask_evaluates():
    """Tricopter with wing, only the rear motor tilting (mask {3})."""
    project = Project.template("tiltrotor").with_overrides({
        "motors.0.role": "lift",
        "motors.1.role": "lift",
        "motors.2.role": "tilt",
    })
    assert [m.role for m in project.cruise_motors()] == ["tilt"]
    result = evaluate_two_phase(project, backend=ParabolicAero())
    assert [[m.index for m in c.motors] for c in result.cruise] == [[2], [2]]
    assert len(result.hover.motors) == 3


def test_overlap_message_names_the_motors():
    data = Project.template("tricopter").to_dict()
    data["motors"][1]["y_mm"] = 100.0  # motor 2 next to motor 1
    with pytest.raises(ValueError) as info:
        Project.model_validate(data)
    text = str(info.value)
    assert "motor 1 (12 in" in text
    assert "motor 2 (12 in" in text
    assert "need at least 305 mm" in text
    assert "smaller propellers" in text
