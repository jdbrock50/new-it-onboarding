"""Read-only console display tests for onboarding alert priorities."""

from unittest.mock import patch

from src import console


def _report(alerts=None, priority_counts=None, errors=None):
    alerts = [] if alerts is None else alerts
    errors = [] if errors is None else errors
    return {
        "as_of": "2026-11-03",
        "upcoming_days": 7,
        "counts": {"Overdue": 1, "Due Today": 0, "Upcoming": 0},
        "priority_counts": priority_counts or {
            "Critical": 1, "High": 0, "Medium": 0, "Low": 0,
        },
        "alerts": alerts,
        "total_alerts": len(alerts),
        "errors": errors,
    }


def _alert():
    return {
        "employee": "Sample Employee",
        "alert": "Overdue",
        "priority": "Critical",
        "start_date": "2026-10-01",
        "shore_email": "sample@example.invalid",
        "status": "In Progress",
        "program": "Sample Program",
        "location": "Sample Location",
        "days_overdue": 33,
        "days_until_start": 0,
        "remaining": 4,
        "completed": 2,
        "total": 6,
        "percentage": 33,
    }


def test_priority_summary_and_individual_label(capsys):
    with (
        patch("builtins.input", side_effect=["", ""]),
        patch.object(console, "load_onboarding_history", return_value=[{"status": "Pending"}]),
        patch.object(console, "build_overdue_alerts", return_value=_report([_alert()])),
    ):
        console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "PRIORITY SUMMARY" in output
    for level, count in (("Critical", 1), ("High", 0), ("Medium", 0), ("Low", 0)):
        assert f"{level}: {count}" in output
    assert "Priority: Critical" in output
    assert "Program: Sample Program" in output
    assert "Location: Sample Location" in output
    assert "Tasks Remaining: 4" in output


def test_filters_are_forwarded_and_priority_summary_remains_visible(capsys):
    with (
        patch("builtins.input", side_effect=[" Shore Middle ", " Cambridge "]),
        patch.object(console, "load_onboarding_history", return_value=[{"status": "Pending"}]),
        patch.object(console, "build_overdue_alerts", return_value=_report([])) as builder,
    ):
        console.view_overdue_onboarding_alerts()
    assert builder.call_args.kwargs == {"program": "Shore Middle", "location": "Cambridge"}
    output = capsys.readouterr().out
    assert "Program filter: Shore Middle" in output
    assert "Location filter: Cambridge" in output
    assert "PRIORITY SUMMARY" in output
    assert "No active onboarding alerts found." in output


def test_empty_history_still_shows_zero_priorities(capsys):
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    with (
        patch("builtins.input", side_effect=["", ""]),
        patch.object(console, "load_onboarding_history", return_value=[]),
        patch.object(console, "build_overdue_alerts", return_value=_report(priority_counts=counts)),
    ):
        console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "No onboarding records found." in output
    assert "Critical: 0" in output
    assert "Low: 0" in output


def test_error_review_still_prints(capsys):
    with (
        patch("builtins.input", side_effect=["", ""]),
        patch.object(console, "load_onboarding_history", return_value=[{"status": "Pending"}]),
        patch.object(console, "build_overdue_alerts", return_value=_report(errors=[{
            "employee": "Sample Employee", "error": "Invalid date",
        }])),
    ):
        console.view_overdue_onboarding_alerts()
    output = capsys.readouterr().out
    assert "RECORDS REQUIRING REVIEW" in output
    assert "Sample Employee: Invalid date" in output
    assert "Records with errors: 1" in output
