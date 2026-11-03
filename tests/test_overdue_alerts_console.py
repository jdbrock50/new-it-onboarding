"""Integration checks for the read-only overdue alert console option."""

from unittest.mock import Mock

from src import console


def _report(alerts=None, errors=None):
    alerts = alerts or []
    errors = errors or []
    return {
        "as_of": "2026-11-03", "upcoming_days": 7,
        "counts": {"Overdue": 1 if alerts else 0, "Due Today": 0, "Upcoming": 0},
        "total_alerts": len(alerts), "alerts": alerts, "errors": errors,
        "priority_counts": {"Critical": 0, "High": len(alerts), "Medium": 0, "Low": 0},
    }


def test_menu_shows_alerts_and_new_exit(capsys):
    console.display_menu()
    output = capsys.readouterr().out
    assert "12. View Overdue Onboarding Alerts" in output
    assert "13. Exit" in output
    assert "11. View Onboarding Progress Dashboard" in output


def test_alert_screen_displays_summary_and_remaining_tasks(monkeypatch, capsys):
    records = [{"onboarding_id": "fake-1"}]
    alert = {
        "employee": "Test Employee", "alert": "Overdue", "priority": "High", "start_date": "2026-11-01",
        "shore_email": "test@example.invalid", "status": "Pending", "days_overdue": 2,
        "remaining": 18, "completed": 2, "total": 20, "percentage": 10,
    }
    loader = Mock(return_value=records)
    builder = Mock(return_value=_report([alert]))
    monkeypatch.setattr(console, "load_onboarding_history", loader)
    monkeypatch.setattr(console, "build_overdue_alerts", builder)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "Overdue: 1" in output
    assert "Test Employee" in output
    assert "Days Overdue: 2" in output
    assert "Tasks Remaining: 18" in output
    assert "2/20 (10%)" in output
    builder.assert_called_once_with(records, program=None, location=None, priority=None)


def test_empty_history_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [])
    monkeypatch.setattr(console, "build_overdue_alerts", lambda records, **kwargs: _report())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    assert "No onboarding records found." in capsys.readouterr().out


def test_no_active_alerts(monkeypatch, capsys):
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [{"onboarding_id": "fake"}])
    monkeypatch.setattr(console, "build_overdue_alerts", lambda records, **kwargs: _report())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    assert "No active onboarding alerts found." in capsys.readouterr().out


def test_error_records_display(monkeypatch, capsys):
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [{"onboarding_id": "fake"}])
    monkeypatch.setattr(console, "build_overdue_alerts", lambda records, **kwargs: _report(errors=[{
        "employee": "Invalid Example", "error": "ValueError: bad date"
    }]))
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "Records with errors: 1" in output
    assert "Invalid Example: ValueError: bad date" in output


def test_history_read_failure_is_handled(monkeypatch, capsys):
    def fail():
        raise OSError("test failure")
    monkeypatch.setattr(console, "load_onboarding_history", fail)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    assert "Unable to build overdue alerts (OSError)." in capsys.readouterr().out


def test_menu_option_12_dispatches_and_13_exits(monkeypatch, capsys):
    called = Mock()
    monkeypatch.setattr(console, "view_overdue_onboarding_alerts", called)
    responses = iter(["12", "", "13"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    console.run_console()
    called.assert_called_once_with()
    assert "Exiting Shore IT Onboarding." in capsys.readouterr().out
