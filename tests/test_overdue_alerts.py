"""Isolated tests for read-only onboarding alerts; no live employee data."""

from copy import deepcopy
from datetime import date

import pytest

from src.overdue_alerts import build_overdue_alerts
from src.onboarding import generate_onboarding_tasks
from src.progress_dashboard import _employee_from_record
from src.task_progress import set_task_completed


TODAY = date(2026, 11, 3)


def record(**overrides):
    item = {
        "first_name": "Taylor", "middle_name": "", "last_name": "Example",
        "position": "Teacher", "program": "Demo", "location": "Test Site",
        "supervisor": "Test Supervisor", "start_date": "2026-11-01",
        "personal_email": "test@example.invalid", "shore_email": "test@example.invalid",
        "devices": "None", "status": "Pending", "onboarding_id": "id-one",
    }
    item.update(overrides)
    return item


def report(records, tmp_path, **kwargs):
    return build_overdue_alerts(records, tmp_path / "missing.json", today=TODAY, **kwargs)


def test_overdue_counts_days_and_remaining(tmp_path):
    result = report([record()], tmp_path)
    alert = result["alerts"][0]
    assert (alert["alert"], alert["days_overdue"]) == ("Overdue", 2)
    assert alert["remaining"] == alert["total"]
    assert result["counts"]["Overdue"] == 1


def test_due_today(tmp_path):
    result = report([record(start_date="2026-11-03")], tmp_path)
    assert result["alerts"][0]["alert"] == "Due Today"


def test_upcoming_boundary(tmp_path):
    result = report([record(start_date="2026-11-10")], tmp_path)
    assert result["alerts"][0]["alert"] == "Upcoming"
    assert result["alerts"][0]["days_until_start"] == 7


def test_beyond_window_not_alerted(tmp_path):
    assert report([record(start_date="2026-11-11")], tmp_path)["alerts"] == []


def test_cancelled_is_excluded(tmp_path):
    assert report([record(status="Cancelled")], tmp_path)["total_alerts"] == 0


def test_completed_overall_status_does_not_hide_incomplete_tasks(tmp_path):
    result = report([record(status="Completed")], tmp_path)
    assert result["alerts"][0]["alert"] == "Overdue"


def test_fully_completed_checklist_is_excluded(tmp_path):
    path = tmp_path / "progress.json"
    entry = record()
    tasks = generate_onboarding_tasks(_employee_from_record(entry), shore_email=entry["shore_email"])
    for task in tasks:
        set_task_completed(entry["onboarding_id"], task, True, path=path)
    result = build_overdue_alerts([entry], path, today=TODAY)
    assert result["alerts"] == []


def test_missing_id_error_does_not_block_valid_alert(tmp_path):
    result = report([record(onboarding_id=""), record(onboarding_id="valid")], tmp_path)
    assert len(result["errors"]) == 1
    assert result["total_alerts"] == 1


def test_invalid_date_error(tmp_path):
    result = report([record(start_date="bad-date")], tmp_path)
    assert len(result["errors"]) == 1
    assert result["total_alerts"] == 0


def test_duplicate_email_different_ids_remain_separate(tmp_path):
    result = report([record(onboarding_id="one"), record(onboarding_id="two")], tmp_path)
    assert {a["onboarding_id"] for a in result["alerts"]} == {"one", "two"}


def test_does_not_modify_records_or_create_progress_file(tmp_path):
    entries = [record()]
    original = deepcopy(entries)
    path = tmp_path / "missing.json"
    build_overdue_alerts(entries, path, today=TODAY)
    assert entries == original
    assert not path.exists()


def test_empty_history(tmp_path):
    result = report([], tmp_path)
    assert result["total_alerts"] == 0
    assert result["errors"] == []


def test_invalid_window_rejected(tmp_path):
    with pytest.raises(ValueError, match="nonnegative"):
        report([], tmp_path, upcoming_days=-1)


def test_custom_upcoming_window(tmp_path):
    result = report([record(start_date="2026-11-05")], tmp_path, upcoming_days=1)
    assert result["total_alerts"] == 0
