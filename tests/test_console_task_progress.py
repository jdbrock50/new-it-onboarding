"""Isolated checklist-management tests; never use live employee data."""
from datetime import date
from unittest.mock import Mock

import src.console as console
from src.onboarding import OnboardingTask


def sample_record():
    return {
        "first_name": "Taylor", "middle_name": "", "last_name": "Example",
        "position": "Teacher", "program": "Demo", "location": "Test Site",
        "supervisor": "Supervisor", "start_date": "2026-11-02",
        "personal_email": "test@example.invalid",
        "shore_email": "texample@example.invalid",
        "devices": "Windows, iPad", "status": "Pending",
        "onboarding_id": "test-uuid-123",
    }


def setup_console(monkeypatch, responses):
    record = sample_record()
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [record])
    monkeypatch.setattr(console, "display_records", lambda records: None)
    monkeypatch.setattr(console, "select_history_record", lambda records: 1)
    monkeypatch.setattr(console, "generate_onboarding_tasks", lambda *a, **kw: [OnboardingTask("Test", "Test task")])
    monkeypatch.setattr(console, "apply_task_progress", lambda oid, tasks: tasks)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    return record


def test_reconstruct_employee_devices():
    employee = console.employee_from_history(sample_record())
    assert employee.device_needs == ["Windows", "iPad"]
    assert employee.start_date == date(2026, 11, 2)
    assert employee.full_name == "Taylor Example"


def test_reconstruct_employee_empty_devices():
    record = sample_record()
    record["devices"] = "None"
    assert console.employee_from_history(record).device_needs == []


def test_cancel_does_not_save(monkeypatch):
    setup_console(monkeypatch, iter(["c"]))
    save = Mock()
    monkeypatch.setattr(console, "set_task_completed", save)
    console.manage_onboarding_checklist()
    save.assert_not_called()


def test_confirmed_change_saves_and_refreshes_checklist(monkeypatch):
    setup_console(monkeypatch, iter(["1", "y", "c"]))
    audit = Mock(return_value=True)
    save = Mock()
    checklist = Mock(return_value="test-checklist.txt")
    monkeypatch.setattr(console, "_record_required_audit_event", audit)
    monkeypatch.setattr(console, "set_task_completed", save)
    monkeypatch.setattr(console, "create_checklist", checklist)
    console.manage_onboarding_checklist()
    assert audit.call_count == 1
    assert audit.call_args.args[0] == "task_progress_change_authorized"
    assert save.call_count == 1
    assert save.call_args.args[0] == "test-uuid-123"
    assert save.call_args.args[2] is True
    assert checklist.call_count == 1


def test_audit_failure_blocks_change(monkeypatch):
    setup_console(monkeypatch, iter(["1", "y"]))
    monkeypatch.setattr(console, "_record_required_audit_event", lambda *a, **kw: False)
    save = Mock()
    monkeypatch.setattr(console, "set_task_completed", save)
    console.manage_onboarding_checklist()
    save.assert_not_called()


def test_declined_confirmation_blocks_change(monkeypatch):
    setup_console(monkeypatch, iter(["1", "n", "c"]))
    save = Mock()
    monkeypatch.setattr(console, "set_task_completed", save)
    console.manage_onboarding_checklist()
    save.assert_not_called()


def test_missing_id_blocks_change(monkeypatch):
    record = setup_console(monkeypatch, iter([]))
    record["onboarding_id"] = ""
    save = Mock()
    monkeypatch.setattr(console, "set_task_completed", save)
    console.manage_onboarding_checklist()
    save.assert_not_called()


def test_invalid_task_number_does_not_save(monkeypatch):
    setup_console(monkeypatch, iter(["99", "abc", "c"]))
    save = Mock()
    monkeypatch.setattr(console, "set_task_completed", save)
    console.manage_onboarding_checklist()
    save.assert_not_called()


def test_menu_has_checklist_and_exit(capsys):
    console.display_menu()
    text = capsys.readouterr().out
    assert "10. Manage Onboarding Checklist" in text
    assert "11. Exit" in text
