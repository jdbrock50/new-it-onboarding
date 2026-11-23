
"""Integration tests for the group approval reporting console."""

from unittest.mock import patch

import pytest

from src.console import (
    display_menu,
    run_console,
    view_group_approval_reporting_dashboard,
)
from src.group_approval import (
    GroupApprovalError,
    GroupReviewStatus,
)
from src.group_approval_reporting import (
    GroupApprovalReport,
    GroupReviewSummary,
)


def make_summary(
    onboarding_id="TEST-001",
    employee_email="alex.morgan@example.org",
    status=GroupReviewStatus.IN_PROGRESS,
    approved=0,
    rejected=0,
    deferred=0,
    not_reviewed=2,
    reopen_count=0,
):
    """Create a fictional group approval review summary."""
    return GroupReviewSummary(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        status=status,
        total_groups=approved + rejected + deferred + not_reviewed,
        approved=approved,
        rejected=rejected,
        deferred=deferred,
        not_reviewed=not_reviewed,
        reopen_count=reopen_count,
    )


def make_report(*summaries):
    return GroupApprovalReport(reviews=tuple(summaries))


def test_dashboard_empty_report(capsys):
    with patch(
        "src.console.generate_group_approval_report",
        return_value=make_report(),
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "GROUP APPROVAL REPORTING DASHBOARD" in output
    assert "No group approval reviews found." in output


def test_dashboard_displays_review_totals(capsys):
    report = make_report(
        make_summary(),
        make_summary(
            onboarding_id="TEST-002",
            employee_email="sam.taylor@example.org",
            status=GroupReviewStatus.COMPLETED,
            approved=1,
            rejected=1,
            not_reviewed=0,
        ),
    )

    with patch(
        "src.console.generate_group_approval_report",
        return_value=report,
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "Total reviews: 2" in output
    assert "Completed reviews: 1" in output
    assert "In-progress reviews: 1" in output
    assert "Reviews with unresolved groups: 1" in output
    assert "Total groups: 4" in output
    assert "Approved: 1" in output
    assert "Rejected: 1" in output
    assert "Not reviewed: 2" in output
    assert "Unresolved: 2" in output


def test_dashboard_displays_individual_reviews(capsys):
    report = make_report(
        make_summary(
            approved=1,
            deferred=1,
            not_reviewed=0,
            reopen_count=2,
        )
    )

    with patch(
        "src.console.generate_group_approval_report",
        return_value=report,
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "alex.morgan@example.org" in output
    assert "Onboarding ID: TEST-001" in output
    assert "Status: In Progress" in output
    assert "Groups: 2" in output
    assert "1 approved" in output
    assert "1 deferred" in output
    assert "Unresolved: 1" in output
    assert "Times reopened: 2" in output


def test_dashboard_displays_reopening_statistics(capsys):
    report = make_report(
        make_summary(
            approved=2,
            not_reviewed=0,
            reopen_count=2,
        ),
        make_summary(
            onboarding_id="TEST-002",
            employee_email="sam.taylor@example.org",
            status=GroupReviewStatus.COMPLETED,
            approved=2,
            not_reviewed=0,
            reopen_count=1,
        ),
    )

    with patch(
        "src.console.generate_group_approval_report",
        return_value=report,
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "Reviews reopened at least once: 2" in output
    assert "Total reopenings: 3" in output


@pytest.mark.parametrize(
    "error",
    [
        GroupApprovalError("Invalid audit history"),
        OSError("Audit file unavailable"),
        ValueError("Invalid audit data"),
        TypeError("Unexpected audit structure"),
    ],
)
def test_dashboard_handles_reporting_errors(error, capsys):
    with patch(
        "src.console.generate_group_approval_report",
        side_effect=error,
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "Unable to build group approval report" in output
    assert type(error).__name__ in output
    assert "Verify the local audit history" in output


def test_dashboard_displays_read_only_confirmation(capsys):
    report = make_report(make_summary())

    with patch(
        "src.console.generate_group_approval_report",
        return_value=report,
    ):
        view_group_approval_reporting_dashboard()

    output = capsys.readouterr().out

    assert "Reporting is local and read-only." in output
    assert "No group memberships were changed." in output


def test_dashboard_calls_reporting_service_once():
    report = make_report(make_summary())

    with patch(
        "src.console.generate_group_approval_report",
        return_value=report,
    ) as mock_report:
        view_group_approval_reporting_dashboard()

    mock_report.assert_called_once_with()


def test_menu_includes_reporting_and_exit(capsys):
    display_menu()

    output = capsys.readouterr().out

    assert "14. View Group Approval Reporting Dashboard" in output
    assert "15. Exit" in output


def test_menu_option_14_opens_reporting_dashboard():
    with (
        patch(
            "builtins.input",
            side_effect=["14", "", "15"],
        ),
        patch("src.console.display_header"),
        patch("src.console.display_menu"),
        patch(
            "src.console.view_group_approval_reporting_dashboard"
        ) as dashboard,
    ):
        run_console()

    dashboard.assert_called_once_with()


def test_menu_option_15_exits_without_opening_dashboard():
    with (
        patch("builtins.input", return_value="15"),
        patch("src.console.display_header"),
        patch("src.console.display_menu"),
        patch(
            "src.console.view_group_approval_reporting_dashboard"
        ) as dashboard,
    ):
        run_console()

    dashboard.assert_not_called()
