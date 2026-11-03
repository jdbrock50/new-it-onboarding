"""Console filtering integration tests; all data is synthetic."""

from unittest.mock import Mock

import pytest

from src import console


@pytest.mark.parametrize(
    ("answers", "expected_program", "expected_location"),
    [
        (["", ""], None, None),
        (["Adult Program", ""], "Adult Program", None),
        (["", "Peabody"], None, "Peabody"),
        ([" Adult Program ", " Peabody "], "Adult Program", "Peabody"),
    ],
)
def test_alert_console_passes_filters(monkeypatch, capsys, answers, expected_program, expected_location):
    records = [{"first_name": "Test", "last_name": "Employee"}]
    report = {
        "as_of": "2026-11-03", "upcoming_days": 7,
        "counts": {"Overdue": 0, "Due Today": 0, "Upcoming": 0},
        "total_alerts": 0, "errors": [], "alerts": [],
        "priority_counts": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0},
    }
    build = Mock(return_value=report)
    monkeypatch.setattr(console, "load_onboarding_history", lambda: records)
    monkeypatch.setattr(console, "build_overdue_alerts", build)
    prompts = iter([*answers, ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(prompts))

    console.view_overdue_onboarding_alerts()

    build.assert_called_once_with(records, program=expected_program, location=expected_location, priority=None)
    output = capsys.readouterr().out
    assert f"Program filter: {expected_program or 'All'}" in output
    assert f"Location filter: {expected_location or 'All'}" in output


def test_alert_console_shows_program_and_location(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [{"first_name": "Test"}])
    monkeypatch.setattr(console, "build_overdue_alerts", lambda *args, **kwargs: {
        "as_of": "2026-11-03", "upcoming_days": 7,
        "counts": {"Overdue": 1, "Due Today": 0, "Upcoming": 0},
        "total_alerts": 1, "errors": [],
        "priority_counts": {"Critical": 0, "High": 1, "Medium": 0, "Low": 0},
        "alerts": [{"employee": "Test Employee", "alert": "Overdue", "priority": "High",
                    "start_date": "2026-11-01", "shore_email": "",
                    "status": "Pending", "days_overdue": 2,
                    "remaining": 3, "completed": 1, "total": 4,
                    "percentage": 25, "program": "Adult Program", "location": "Peabody"}],
    })
    console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "Program: Adult Program" in output
    assert "Location: Peabody" in output
    assert "Test Employee" in output
