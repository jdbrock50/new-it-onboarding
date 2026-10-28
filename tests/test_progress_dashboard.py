"""Tests for the read-only onboarding progress dashboard."""

from copy import deepcopy
from pathlib import Path

from src.progress_dashboard import build_progress_dashboard
from src.onboarding import generate_onboarding_tasks
from src.progress_dashboard import _employee_from_record
from src.task_progress import set_task_completed


def record(**overrides):
    base = {
        "first_name": "Test", "middle_name": "", "last_name": "Employee",
        "position": "Teacher", "program": "Test Program", "location": "Test Site",
        "supervisor": "Test Supervisor", "start_date": "2026-11-01",
        "personal_email": "test@example.invalid", "shore_email": "test@shorecollaborative.org",
        "devices": "Windows, Android", "status": "Pending", "onboarding_id": "test-id-001",
    }
    base.update(overrides)
    return base


def test_empty_history(tmp_path):
    result = build_progress_dashboard([], tmp_path / "missing.json")
    assert result["rows"] == []
    assert result["total_onboardings"] == 0
    assert result["errors"] == 0


def test_no_progress_file_is_read_only(tmp_path):
    path = tmp_path / "missing.json"
    result = build_progress_dashboard([record()], path)
    row = result["rows"][0]
    assert row["completed"] == 0
    assert row["total"] == 26
    assert row["percentage"] == 0
    assert not path.exists()


def test_saved_completion_is_restored(tmp_path):
    path = tmp_path / "progress.json"
    entry = record()
    task = generate_onboarding_tasks(_employee_from_record(entry), entry["shore_email"])[0]
    set_task_completed(entry["onboarding_id"], task, True, path=path)
    result = build_progress_dashboard([entry], path)
    assert result["rows"][0]["completed"] == 1
    assert result["rows"][0]["percentage"] == 4


def test_same_email_different_ids_are_isolated(tmp_path):
    path = tmp_path / "progress.json"
    first = record(onboarding_id="id-one")
    second = record(onboarding_id="id-two", status="Completed")
    task = generate_onboarding_tasks(_employee_from_record(first), first["shore_email"])[0]
    set_task_completed("id-one", task, True, path=path)
    rows = build_progress_dashboard([first, second], path)["rows"]
    assert [row["completed"] for row in rows] == [1, 0]
    assert rows[1]["status"] == "Completed"


def test_status_counts_do_not_depend_on_progress(tmp_path):
    entries = [record(), record(onboarding_id="id-two", status="Completed")]
    result = build_progress_dashboard(entries, tmp_path / "missing.json")
    assert result["status_counts"] == {"Pending": 1, "Completed": 1}
    assert result["incomplete_checklists"] == 2
    assert result["completed_checklists"] == 0


def test_missing_id_reports_error_without_crashing(tmp_path):
    entries = [record(onboarding_id=""), record(onboarding_id="valid")]
    result = build_progress_dashboard(entries, tmp_path / "missing.json")
    assert result["errors"] == 1
    assert "Missing onboarding ID" in result["rows"][0]["error"]
    assert result["rows"][1]["total"] == 26


def test_bad_start_date_reports_error(tmp_path):
    result = build_progress_dashboard([record(start_date="invalid")], tmp_path / "missing.json")
    assert result["errors"] == 1
    assert result["rows"][0]["percentage"] is None


def test_invalid_progress_file_reports_error(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text("[]", encoding="utf-8")
    result = build_progress_dashboard([record()], path)
    assert result["errors"] == 1
    assert path.read_text(encoding="utf-8") == "[]"


def test_does_not_mutate_input_records(tmp_path):
    entries = [record()]
    original = deepcopy(entries)
    build_progress_dashboard(entries, tmp_path / "missing.json")
    assert entries == original


def test_no_device_requirement(tmp_path):
    result = build_progress_dashboard([record(devices="None")], tmp_path / "missing.json")
    assert result["rows"][0]["total"] == 20
