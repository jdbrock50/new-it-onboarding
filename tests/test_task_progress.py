"""Tests for persistent onboarding task completion tracking."""

import json

import pytest

from src.onboarding import OnboardingTask
from src.task_progress import (
    apply_task_progress,
    calculate_task_progress,
    load_task_progress,
    set_task_completed,
    task_id,
)


def make_tasks():
    return [
        OnboardingTask("Accounts & Access", "Create fictional account"),
        OnboardingTask("Printing", "Configure fictional printer"),
    ]


def test_missing_file_is_read_only(tmp_path):
    path = tmp_path / "progress.json"
    assert load_task_progress(path) == {}
    assert not path.exists()


def test_task_ids_are_stable_and_distinct():
    first, second = make_tasks()
    assert task_id(first) == task_id(make_tasks()[0])
    assert task_id(first) != task_id(second)


def test_completion_persists_across_regeneration(tmp_path):
    path = tmp_path / "progress.json"
    first = make_tasks()[0]
    set_task_completed("onboarding-1", first, True, path)
    tasks = apply_task_progress("onboarding-1", make_tasks(), path)
    assert [task.completed for task in tasks] == [True, False]
    assert calculate_task_progress(tasks) == {
        "completed": 1, "total": 2, "percentage": 50,
    }


def test_onboardings_are_isolated(tmp_path):
    path = tmp_path / "progress.json"
    set_task_completed("onboarding-1", make_tasks()[0], True, path)
    other = apply_task_progress("onboarding-2", make_tasks(), path)
    assert not any(task.completed for task in other)


def test_task_can_be_reopened(tmp_path):
    path = tmp_path / "progress.json"
    task = make_tasks()[0]
    set_task_completed("onboarding-1", task, True, path)
    set_task_completed("onboarding-1", task, False, path)
    assert not apply_task_progress("onboarding-1", make_tasks(), path)[0].completed


def test_storage_contains_timestamp(tmp_path):
    path = tmp_path / "progress.json"
    set_task_completed("onboarding-1", make_tasks()[0], True, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["onboarding-1"]["tasks"][task_id(make_tasks()[0])]["updated_at"]


def test_empty_task_list():
    assert calculate_task_progress([]) == {
        "completed": 0, "total": 0, "percentage": 0,
    }


def test_invalid_completion_rejected(tmp_path):
    with pytest.raises(TypeError, match="boolean"):
        set_task_completed("onboarding-1", make_tasks()[0], "yes", tmp_path / "p.json")


def test_invalid_json_shape_rejected(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_task_progress(path)
