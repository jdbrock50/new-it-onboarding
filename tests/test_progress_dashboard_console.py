"""Tests for read-only onboarding dashboard console integration."""
from unittest.mock import patch

from src import console


def _report():
    return {
        "rows": [
            {"employee": "Test Employee", "shore_email": "test@example.org",
             "status": "In Progress", "completed": 3, "total": 6,
             "percentage": 50, "error": None},
            {"employee": "Invalid Record", "shore_email": "",
             "status": "Pending", "completed": None, "total": None,
             "percentage": None, "error": "ValueError: Missing onboarding ID"},
        ],
        "total_onboardings": 2,
        "status_counts": {"In Progress": 1, "Pending": 1},
        "completed_checklists": 0,
        "incomplete_checklists": 1,
        "errors": 1,
    }


def test_menu_shows_dashboard_and_exit(capsys):
    console.display_menu()
    output = capsys.readouterr().out
    assert "11. View Onboarding Progress Dashboard" in output
    assert "12. Exit" in output


def test_dashboard_displays_rows_and_totals(capsys):
    records = [{"onboarding_id": "example"}]
    with patch.object(console, "load_onboarding_history", return_value=records), patch.object(
        console, "build_progress_dashboard", return_value=_report()
    ) as builder:
        console.view_onboarding_progress_dashboard()
    builder.assert_called_once_with(records)
    output = capsys.readouterr().out
    for text in ("Test Employee", "3/6 (50%)", "In Progress",
                 "Invalid Record", "Progress unavailable", "Total onboardings: 2",
                 "Completed checklists: 0", "Incomplete checklists: 1",
                 "Records with errors: 1", "Pending: 1"):
        assert text in output


def test_dashboard_empty_history(capsys):
    with patch.object(console, "load_onboarding_history", return_value=[]), patch.object(
        console, "build_progress_dashboard", return_value={**_report(), "rows": []}
    ):
        console.view_onboarding_progress_dashboard()
    assert "No onboarding records found." in capsys.readouterr().out


def test_dashboard_handles_history_read_error(capsys):
    with patch.object(console, "load_onboarding_history", side_effect=OSError("unavailable")):
        console.view_onboarding_progress_dashboard()
    assert "Unable to build progress dashboard (OSError)" in capsys.readouterr().out


def test_dashboard_option_routes_and_exit_does_not_pause():
    with patch.object(console, "display_header"), patch.object(console, "display_menu"), patch.object(
        console, "view_onboarding_progress_dashboard"
    ) as dashboard, patch("builtins.input", side_effect=["11", "", "12"]) as prompt:
        console.run_console()
    dashboard.assert_called_once_with()
    assert prompt.call_count == 3


def test_exit_option_twelve():
    with patch.object(console, "display_header"), patch.object(console, "display_menu"), patch(
        "builtins.input", return_value="12"
    ) as prompt:
        console.run_console()
    prompt.assert_called_once()
