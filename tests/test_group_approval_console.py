
"""Tests for the Google Workspace group approval console."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import console


def test_menu_displays_group_review_and_new_exit(capsys):
    """The group review option precedes the Exit option."""
    console.display_menu()

    output = capsys.readouterr().out

    assert "12. View Overdue Onboarding Alerts" in output
    assert "13. Review Google Workspace Group Recommendations" in output
    assert "14. View Group Approval Reporting Dashboard" in output
    assert "15. Exit" in output
    assert "14. Exit" not in output


def test_group_review_handles_empty_onboarding_history(
    monkeypatch, capsys
):
    """No employee selection is attempted when history is empty."""
    history_loader = Mock(return_value=[])
    record_selector = Mock()

    monkeypatch.setattr(
        console,
        "load_onboarding_history",
        history_loader,
    )
    monkeypatch.setattr(
        console,
        "select_history_record",
        record_selector,
    )

    console.review_group_recommendations()

    output = capsys.readouterr().out

    assert "GOOGLE WORKSPACE GROUP RECOMMENDATION REVIEW" in output
    assert "No onboarding records found." in output

    history_loader.assert_called_once_with()
    record_selector.assert_not_called()


def test_group_review_lists_records_and_allows_cancellation(
    monkeypatch, capsys
):
    """A cancelled selection must not create an approval review."""
    records = [
        {
            "first_name": "Alex",
            "middle_name": "",
            "last_name": "Example",
            "position": "Teacher",
            "department": "Education",
            "program": "Harbors",
            "location": "Cambridge",
            "start_date": "2026-12-01",
            "shore_email": "alex.example@example.org",
            "devices": "Chromebook",
            "status": "Pending",
            "onboarding_id": "fictional-onboarding-001",
        }
    ]
    history_loader = Mock(return_value=records)
    record_selector = Mock(return_value=None)
    record_display = Mock()

    monkeypatch.setattr(console, "load_onboarding_history", history_loader)
    monkeypatch.setattr(console, "display_records", record_display)
    monkeypatch.setattr(console, "select_history_record", record_selector)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "GOOGLE WORKSPACE GROUP RECOMMENDATION REVIEW" in output
    assert "Group recommendation review cancelled." in output
    history_loader.assert_called_once_with()
    record_display.assert_called_once_with(records)
    record_selector.assert_called_once_with(records)


def test_group_review_displays_selected_employee_recommendations(
    monkeypatch, capsys
):
    """Selecting an employee previews recommendations without approval writes."""
    records = [
        {
            "first_name": "Alex",
            "middle_name": "",
            "last_name": "Example",
            "position": "Teacher",
            "department": "Education",
            "program": "Harbors",
            "location": "Cambridge",
            "start_date": "2026-12-01",
            "shore_email": "alex.example@example.org",
            "devices": "Chromebook",
            "status": "Pending",
            "onboarding_id": "fictional-onboarding-001",
        }
    ]
    fictional_employee = object()
    reconstruct_employee = Mock(return_value=fictional_employee)
    show_recommendations = Mock()

    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=records))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", reconstruct_employee)
    monkeypatch.setattr(console, "display_group_recommendations", show_recommendations)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Selected employee: Alex Example" in output
    reconstruct_employee.assert_called_once_with(records[0])
    show_recommendations.assert_called_once_with(fictional_employee)


def test_group_review_checks_for_existing_approval_review(monkeypatch, capsys):
    """An existing local review is looked up by onboarding ID, not recreated."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="fictional-onboarding-001",
        employee_email="alex.example@example.org",
        status=SimpleNamespace(value="in_progress"),
        groups={},
        unresolved_groups=[],
    )
    restore_review = Mock(return_value=existing_review)
    reconstruct_employee = Mock(return_value=object())
    show_recommendations = Mock()

    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", reconstruct_employee)
    monkeypatch.setattr(console, "display_group_recommendations", show_recommendations)
    monkeypatch.setattr(
        console, "restore_group_approval_review", restore_review, raising=False
    )

    console.review_group_recommendations()

    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    show_recommendations.assert_called_once()


def test_group_review_displays_existing_review_status_and_decisions(monkeypatch, capsys):
    """An existing review shows status, decisions, and unresolved groups."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="fictional-onboarding-001",
        employee_email="alex.example@example.org",
        status=SimpleNamespace(value="in_progress"),
        groups={
            "teachers@example.org": SimpleNamespace(
                group_name="Teachers",
                group_email="teachers@example.org",
                decision=SimpleNamespace(value="approved"),
            ),
            "harbors@example.org": SimpleNamespace(
                group_name="Harbors",
                group_email="harbors@example.org",
                decision=SimpleNamespace(value="not_reviewed"),
            ),
        },
        unresolved_groups=["harbors@example.org"],
    )

    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(
        console, "restore_group_approval_review", Mock(return_value=existing_review)
    )

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Review Status: In Progress" in output
    assert "Teachers" in output
    assert "Approved" in output
    assert "Harbors" in output
    assert "Not Reviewed" in output
    assert "Outstanding Decisions: 1" in output
    assert "No Google Workspace group memberships were changed." in output

def test_group_review_offers_new_review_when_none_exists(monkeypatch, capsys):
    """Missing reviews show a next step without creating an unaudited review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    restore_review = Mock(return_value=None)
    start_review = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(
        console, "start_group_approval_review", start_review, raising=False
    )

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "No existing group approval review found" in output
    assert "Start a new local group approval review" in output
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    start_review.assert_not_called()

def test_group_review_requires_confirmation_before_starting_review(monkeypatch, capsys):
    """Declining explicit confirmation must not start a local approval review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    confirmation_input = Mock(return_value="n")
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "start_group_approval_review", start_review, raising=False)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Start a new local group approval review" in output
    confirmation_input.assert_called_once()
    assert "confirm" in confirmation_input.call_args.args[0].lower()
    start_review.assert_not_called()



def test_group_review_starts_review_only_after_explicit_confirmation(monkeypatch, capsys):
    """An explicit yes starts the existing local review service for the selected hire."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    employee = object()
    recommendations = object()
    review = SimpleNamespace(
        status=SimpleNamespace(value="in_progress"),
        unresolved_groups=[],
    )
    start_review = Mock(return_value=review)
    restore_review = Mock(return_value=None)
    confirmation_input = Mock(side_effect=["y", "Test Administrator"])

    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=employee))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "start_group_approval_review", start_review, raising=False)
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=recommendations))
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    assert confirmation_input.call_count == 2
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    start_review.assert_called_once()
    start_review.assert_called_once_with(
        onboarding_id="fictional-onboarding-001",
        employee_email="alex.example@example.org",
        recommendations=recommendations,
        administrator_name="Test Administrator",
    )
    output = capsys.readouterr().out
    assert "No existing group approval review found" in output
    assert "Local group approval review created successfully" in output


def test_group_review_audit_write_failure_does_not_claim_creation(monkeypatch, capsys):
    """An audit write failure must stop creation without reporting success."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock(side_effect=console.AuditWriteError("Audit storage unavailable"))
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    confirmation_input = Mock(side_effect=["y", "Test Administrator"])
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    start_review.assert_called_once()
    assert confirmation_input.call_count == 2
    assert "Unable to start group approval review (AuditWriteError)" in output
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output
    assert "No group memberships were changed" in output
    assert "Check the audit log before retrying" in output


def test_group_review_duplicate_creation_is_rejected_safely(monkeypatch, capsys):
    """A duplicate detected at creation time cannot be reported as a new review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    duplicate_error = console.GroupApprovalError(
        "A group approval review already exists for onboarding ID: "
        "fictional-onboarding-001"
    )
    start_review = Mock(side_effect=duplicate_error)
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    confirmation_input = Mock(side_effect=["y", "Test Administrator"])
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    start_review.assert_called_once()
    assert confirmation_input.call_count == 2
    assert "Unable to start group approval review (GroupApprovalError)" in output
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output
    assert "No group memberships were changed" in output
    assert "Check the audit log before retrying" in output

def test_group_review_corrupt_audit_history_blocks_new_review(monkeypatch, capsys):
    """Corrupt audit history must never be mistaken for a missing review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    restore_review = Mock(
        side_effect=console.GroupApprovalError("Invalid group approval audit history")
    )
    start_review = Mock()
    confirmation_input = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    confirmation_input.assert_not_called()
    start_review.assert_not_called()
    assert "Unable to restore group approval review (GroupApprovalError)" in output
    assert "No existing group approval review found" not in output
    assert "Start a new local group approval review" not in output
    assert "created successfully" not in output
    assert "No approvals were recorded and no group memberships were changed" in output

def test_group_review_blank_administrator_name_blocks_creation(monkeypatch, capsys):
    """A blank administrator identity must not initiate an audited review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    confirmation_input = Mock(side_effect=["y", "   "])
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert confirmation_input.call_count == 2
    start_review.assert_not_called()
    assert "administrator" in output.lower()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output

def test_group_review_interrupted_administrator_prompt_does_not_create_review(
    monkeypatch, capsys
):
    """Ctrl+C at the administrator-name prompt must stop before review creation."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    confirmation_input = Mock(side_effect=["y", KeyboardInterrupt()])
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    try:
        console.review_group_recommendations()
    except KeyboardInterrupt:
        pass  # Safe propagation is acceptable; review creation must not occur.

    output = capsys.readouterr().out
    assert confirmation_input.call_count == 2
    start_review.assert_not_called()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output

def test_group_review_eof_at_administrator_prompt_does_not_create_review(
    monkeypatch, capsys
):
    """EOF at administrator-name input must stop before any review creation."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    confirmation_input = Mock(side_effect=["y", EOFError()])
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    try:
        console.review_group_recommendations()
    except EOFError:
        pass  # Safe propagation is acceptable; no review may be created.

    output = capsys.readouterr().out
    assert confirmation_input.call_count == 2
    start_review.assert_not_called()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output



def test_group_review_recommendation_failure_does_not_create_review(
    monkeypatch, capsys
):
    """Recommendation generation failure must not create an unaudited review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    recommendation_service = Mock(side_effect=ValueError("Invalid group mapping"))
    confirmation_input = Mock(side_effect=["y", "Test Administrator"])
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", recommendation_service)
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert confirmation_input.call_count == 2
    recommendation_service.assert_called_once()
    start_review.assert_not_called()
    assert "Invalid group mapping" in output or "recommendation" in output.lower()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output

def test_group_review_blank_employee_email_blocks_creation(monkeypatch, capsys):
    """A missing employee email must never produce a local approval review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "   ",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    start_review = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=None))
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["y", "Test Administrator"]))

    console.review_group_recommendations()

    output = capsys.readouterr().out
    start_review.assert_not_called()
    assert "email" in output.lower() or "employee" in output.lower()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output

def test_group_review_blank_onboarding_id_blocks_creation(monkeypatch, capsys):
    """A blank onboarding ID must not create an untraceable approval review."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "   ",
    }
    start_review = Mock()
    restore_review = Mock(return_value=None)
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "recommend_groups", Mock(return_value=object()))
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["y", "Test Administrator"]))

    console.review_group_recommendations()

    output = capsys.readouterr().out
    start_review.assert_not_called()
    assert "onboarding" in output.lower() or "identifier" in output.lower()
    assert "created successfully" not in output
    assert "Groups Awaiting Decisions" not in output

def test_group_review_existing_review_employee_mismatch_blocks_display(
    monkeypatch, capsys
):
    """A restored review for another employee must not expose their decisions."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="fictional-onboarding-001",
        employee_email="different.employee@example.org",
        status=SimpleNamespace(value="in_progress"),
        groups={
            "sensitive-group@example.org": SimpleNamespace(
                group_name="Sensitive Group",
                group_email="sensitive-group@example.org",
                decision=SimpleNamespace(value="approved"),
            )
        },
        unresolved_groups=[],
    )
    restore_review = Mock(return_value=existing_review)
    start_review = Mock()
    confirmation_input = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    start_review.assert_not_called()
    confirmation_input.assert_not_called()
    assert "mismatch" in output.lower() or "different employee" in output.lower()
    assert "Sensitive Group" not in output
    assert "Review Status: In Progress" not in output
    assert "created successfully" not in output



def test_group_review_existing_review_missing_employee_identity_blocks_display(
    monkeypatch, capsys
):
    """A restored review without a verified employee email must not expose decisions."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="fictional-onboarding-001",
        employee_email="   ",
        status=SimpleNamespace(value="in_progress"),
        groups={
            "sensitive-group@example.org": SimpleNamespace(
                group_name="Sensitive Group",
                group_email="sensitive-group@example.org",
                decision=SimpleNamespace(value="approved"),
            )
        },
        unresolved_groups=[],
    )
    restore_review = Mock(return_value=existing_review)
    start_review = Mock()
    confirmation_input = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    start_review.assert_not_called()
    confirmation_input.assert_not_called()
    assert "identity" in output.lower() or "employee email" in output.lower()
    assert "Sensitive Group" not in output
    assert "Review Status: In Progress" not in output
    assert "created successfully" not in output


def test_group_review_existing_review_onboarding_id_mismatch_blocks_display(
    monkeypatch, capsys
):
    """A review restored with a different onboarding ID must not reveal decisions."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="different-onboarding-002",
        employee_email="alex.example@example.org",
        status=SimpleNamespace(value="in_progress"),
        groups={
            "sensitive-group@example.org": SimpleNamespace(
                group_name="Sensitive Group",
                group_email="sensitive-group@example.org",
                decision=SimpleNamespace(value="approved"),
            )
        },
        unresolved_groups=[],
    )
    restore_review = Mock(return_value=existing_review)
    start_review = Mock()
    confirmation_input = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", restore_review)
    monkeypatch.setattr(console, "start_group_approval_review", start_review)
    monkeypatch.setattr("builtins.input", confirmation_input)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    restore_review.assert_called_once_with(onboarding_id="fictional-onboarding-001")
    start_review.assert_not_called()
    confirmation_input.assert_not_called()
    assert "onboarding" in output.lower() and (
        "mismatch" in output.lower() or "does not match" in output.lower()
    )
    assert "Sensitive Group" not in output
    assert "Review Status: In Progress" not in output
    assert "created successfully" not in output


def test_group_review_existing_review_offers_decision_recording_without_automatic_write(
    monkeypatch, capsys
):
    """A verified existing review offers a local decision workflow, but does not write automatically."""
    record = {
        "first_name": "Alex",
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "department": "Education",
        "program": "Harbors",
        "location": "Cambridge",
        "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org",
        "devices": "Chromebook",
        "status": "Pending",
        "onboarding_id": "fictional-onboarding-001",
    }
    existing_review = SimpleNamespace(
        onboarding_id="fictional-onboarding-001",
        employee_email="alex.example@example.org",
        status=SimpleNamespace(value="in_progress"),
        groups={
            "teachers@example.org": SimpleNamespace(
                group_name="Teachers",
                group_email="teachers@example.org",
                decision=SimpleNamespace(value="not_reviewed"),
            )
        },
        unresolved_groups=["teachers@example.org"],
    )
    record_decision = Mock()
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(
        console, "restore_group_approval_review", Mock(return_value=existing_review)
    )
    monkeypatch.setattr(console, "record_group_decision", record_decision, raising=False)
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    console.review_group_recommendations()

    output = capsys.readouterr().out.lower()
    assert "decision" in output
    assert "No Google Workspace group memberships were changed.".lower() in output
    record_decision.assert_not_called()


# Step 454: isolated, read-only group selection tests.

def _fictional_group_selection_review():
    return SimpleNamespace(groups={
        "teachers@example.org": SimpleNamespace(
            group_name="Teachers", group_email="teachers@example.org",
            decision=SimpleNamespace(value="approved"),
        ),
        "harbors@example.org": SimpleNamespace(
            group_name="Harbors", group_email="harbors@example.org",
            decision=SimpleNamespace(value="not_reviewed"),
        ),
    })


def test_select_group_for_review_returns_selected_email(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(return_value="2"))
    result = console.select_group_for_review(_fictional_group_selection_review())
    output = capsys.readouterr().out
    assert result == "harbors@example.org"
    assert "Teachers" in output and "Harbors" in output
    assert "Approved" in output and "Not Reviewed" in output


def test_select_group_for_review_allows_case_insensitive_cancellation(monkeypatch, capsys):
    prompt = Mock(return_value=" C ")
    monkeypatch.setattr("builtins.input", prompt)
    assert console.select_group_for_review(_fictional_group_selection_review()) is None
    prompt.assert_called_once()
    assert "cancelled" in capsys.readouterr().out.lower()


def test_select_group_for_review_retries_invalid_and_out_of_range(monkeypatch, capsys):
    prompt = Mock(side_effect=["abc", "0", "3", "1"])
    monkeypatch.setattr("builtins.input", prompt)
    assert console.select_group_for_review(_fictional_group_selection_review()) == "teachers@example.org"
    output = capsys.readouterr().out.lower()
    assert "valid group number" in output
    assert output.count("out of range") == 2
    assert prompt.call_count == 4


def test_select_group_for_review_empty_groups_never_prompts(monkeypatch, capsys):
    prompt = Mock()
    monkeypatch.setattr("builtins.input", prompt)
    assert console.select_group_for_review(SimpleNamespace(groups={})) is None
    prompt.assert_not_called()
    assert "no groups" in capsys.readouterr().out.lower()


def test_select_group_for_review_eof_cancels_safely(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError()))
    assert console.select_group_for_review(_fictional_group_selection_review()) is None
    assert "cancelled" in capsys.readouterr().out.lower()

# Step 458: isolated tests for the local decision-selection helper.


def test_select_group_decision_approve(monkeypatch, capsys):
    prompt = Mock(return_value="1")
    monkeypatch.setattr("builtins.input", prompt)
    assert console.select_group_decision() == "approved"
    output = capsys.readouterr().out
    assert "Approve" in output and "Reject" in output and "Defer" in output
    prompt.assert_called_once()


def test_select_group_decision_reject(monkeypatch):
    monkeypatch.setattr("builtins.input", Mock(return_value="2"))
    assert console.select_group_decision() == "rejected"


def test_select_group_decision_defer(monkeypatch):
    monkeypatch.setattr("builtins.input", Mock(return_value="3"))
    assert console.select_group_decision() == "deferred"


def test_select_group_decision_cancel(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(return_value="4"))
    assert console.select_group_decision() is None
    assert "cancelled" in capsys.readouterr().out.lower()


def test_select_group_decision_cancel_letter_case_insensitive(monkeypatch):
    monkeypatch.setattr("builtins.input", Mock(return_value=" C "))
    assert console.select_group_decision() is None


def test_select_group_decision_retries_invalid_input(monkeypatch, capsys):
    prompt = Mock(side_effect=["", "invalid", "5", "0", "2"])
    monkeypatch.setattr("builtins.input", prompt)
    assert console.select_group_decision() == "rejected"
    assert prompt.call_count == 5
    assert capsys.readouterr().out.count("Please choose") == 4


def test_select_group_decision_eof_cancels_safely(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError()))
    assert console.select_group_decision() is None
    assert "cancelled" in capsys.readouterr().out.lower()


def test_select_group_decision_keyboard_interrupt_cancels_safely(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=KeyboardInterrupt()))
    assert console.select_group_decision() is None
    assert "cancelled" in capsys.readouterr().out.lower()


def test_select_group_decision_os_error_cancels_safely(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=OSError("input unavailable")))
    assert console.select_group_decision() is None
    assert "cancelled" in capsys.readouterr().out.lower()



# Step 461: integrated decision preview remains strictly read-only.


def _setup_decision_preview(monkeypatch):
    """Provide a fictional, verified review with one unreviewed group."""
    record = {
        "first_name": "Alex", "middle_name": "", "last_name": "Example",
        "position": "Teacher", "department": "Education", "program": "Harbors",
        "location": "Cambridge", "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org", "devices": "Chromebook",
        "status": "Pending", "onboarding_id": "fictional-onboarding-001",
    }
    group = SimpleNamespace(
        group_name="Teachers", group_email="teachers@example.org",
        decision=SimpleNamespace(value="not_reviewed"),
    )
    review = SimpleNamespace(
        onboarding_id=record["onboarding_id"],
        employee_email=record["shore_email"],
        status=SimpleNamespace(value="in_progress"),
        groups={group.group_email: group},
        unresolved_groups=[group.group_email],
    )
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=review))
    audit_write = Mock()
    decision_write = Mock()
    monkeypatch.setattr(console, "record_audit_event", audit_write)
    monkeypatch.setattr(console, "record_group_decision", decision_write, raising=False)
    return review, group, audit_write, decision_write


@pytest.mark.parametrize(
    ("choice", "expected"),
    [("1", "Approved"), ("2", "Rejected"), ("3", "Deferred")],
)
def test_integrated_group_decision_preview_does_not_save(
    monkeypatch, capsys, choice, expected
):
    review, group, audit_write, decision_write = _setup_decision_preview(monkeypatch)
    prompt = Mock(side_effect=["y", "1", choice, "n"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "LOCAL GROUP DECISION PREVIEW (NOT SAVED)" in output
    assert "Group: teachers@example.org" in output
    assert f"Proposed Decision: {expected}" in output
    assert "No decision was saved" in output
    assert "no google workspace group memberships were changed" in output.lower()
    assert prompt.call_count == 4
    assert group.decision.value == "not_reviewed"
    assert review.unresolved_groups == ["teachers@example.org"]
    audit_write.assert_not_called()
    decision_write.assert_not_called()


@pytest.mark.parametrize("cancel_choice", ["4", "C"])
def test_integrated_decision_cancel_does_not_preview_or_save(
    monkeypatch, capsys, cancel_choice
):
    review, group, audit_write, decision_write = _setup_decision_preview(monkeypatch)
    prompt = Mock(side_effect=["y", "1", cancel_choice])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Decision selection cancelled" in output
    assert "LOCAL GROUP DECISION PREVIEW (NOT SAVED)" not in output
    assert "No decision was saved" in output
    assert prompt.call_count == 3
    assert group.decision.value == "not_reviewed"
    assert review.unresolved_groups == ["teachers@example.org"]
    audit_write.assert_not_called()
    decision_write.assert_not_called()


def test_integrated_group_selection_cancel_skips_decision_prompt(monkeypatch, capsys):
    review, group, audit_write, decision_write = _setup_decision_preview(monkeypatch)
    prompt = Mock(side_effect=["y", "c"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Group selection cancelled" in output
    assert "SELECT LOCAL GROUP DECISION" not in output
    assert "LOCAL GROUP DECISION PREVIEW (NOT SAVED)" not in output
    assert prompt.call_count == 2
    assert group.decision.value == "not_reviewed"
    assert review.unresolved_groups == ["teachers@example.org"]
    audit_write.assert_not_called()
    decision_write.assert_not_called()


def test_integrated_declined_opt_in_skips_all_selection(monkeypatch, capsys):
    review, group, audit_write, decision_write = _setup_decision_preview(monkeypatch)
    prompt = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "SELECT GROUP FOR LOCAL DECISION REVIEW" not in output
    assert "SELECT LOCAL GROUP DECISION" not in output
    assert "LOCAL GROUP DECISION PREVIEW (NOT SAVED)" not in output
    prompt.assert_called_once()
    assert group.decision.value == "not_reviewed"
    assert review.unresolved_groups == ["teachers@example.org"]
    audit_write.assert_not_called()
    decision_write.assert_not_called()

# Step 466: audited local decision-recording integration tests.


def _setup_audited_decision_workflow(monkeypatch, *, previous="not_reviewed", status="in_progress"):
    """Isolate the console workflow from audit storage and Workspace services."""
    review, group, audit_write, decision_write = _setup_decision_preview(monkeypatch)
    group.decision.value = previous
    review.status.value = status
    return review, group, audit_write, decision_write


@pytest.mark.parametrize(
    ("choice", "decision"),
    [("1", "approved"), ("2", "rejected"), ("3", "deferred")],
)
def test_audited_decision_confirmed_invokes_service_once(
    monkeypatch, capsys, choice, decision
):
    review, group, audit_write, decision_write = _setup_audited_decision_workflow(monkeypatch)
    prompt = Mock(side_effect=["y", "1", choice, "yes", "Test Administrator"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    decision_write.assert_called_once_with(
        review,
        group_email="teachers@example.org",
        decision=decision,
        administrator_name="Test Administrator",
        change_reason="",
    )
    audit_write.assert_not_called()  # The service, not the console, owns audit writes.
    assert group.decision.value == "not_reviewed"  # Mocked service cannot mutate review.
    assert "recorded successfully" in capsys.readouterr().out
    assert prompt.call_count == 5


@pytest.mark.parametrize("confirmation", ["n", "", "no"])
def test_audited_decision_declined_confirmation_never_records(
    monkeypatch, capsys, confirmation
):
    _, group, audit_write, decision_write = _setup_audited_decision_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["y", "1", "1", confirmation]))

    console.review_group_recommendations()

    decision_write.assert_not_called()
    audit_write.assert_not_called()
    assert group.decision.value == "not_reviewed"
    assert "Decision save cancelled" in capsys.readouterr().out


def test_audited_decision_blank_administrator_blocks_save(monkeypatch, capsys):
    _, _, _, decision_write = _setup_audited_decision_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["y", "1", "1", "y", "   "]))

    console.review_group_recommendations()

    decision_write.assert_not_called()
    assert "Administrator name is required" in capsys.readouterr().out


def test_audited_decision_change_requires_reason(monkeypatch, capsys):
    _, _, _, decision_write = _setup_audited_decision_workflow(
        monkeypatch, previous="approved"
    )
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["y", "1", "2", "y", "Test Administrator", "  "])
    )

    console.review_group_recommendations()

    decision_write.assert_not_called()
    assert "A change reason is required" in capsys.readouterr().out


def test_audited_decision_change_passes_reason_to_service(monkeypatch, capsys):
    review, _, _, decision_write = _setup_audited_decision_workflow(
        monkeypatch, previous="approved"
    )
    monkeypatch.setattr(
        "builtins.input",
        Mock(side_effect=["y", "1", "2", "y", "Test Administrator", "Role changed"]),
    )

    console.review_group_recommendations()

    decision_write.assert_called_once_with(
        review,
        group_email="teachers@example.org",
        decision="rejected",
        administrator_name="Test Administrator",
        change_reason="Role changed",
    )
    assert "recorded successfully" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error", [
        pytest.param(console.AuditWriteError("audit unavailable"), id="audit-write"),
        pytest.param(console.GroupApprovalError("invalid transition"), id="validation"),
    ],
)
def test_audited_decision_service_failure_never_claims_success(
    monkeypatch, capsys, error
):
    _, group, _, decision_write = _setup_audited_decision_workflow(monkeypatch)
    decision_write.side_effect = error
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["y", "1", "1", "y", "Test Administrator"])
    )

    console.review_group_recommendations()

    decision_write.assert_called_once()
    assert group.decision.value == "not_reviewed"
    output = capsys.readouterr().out
    assert "Unable to record local group decision" in output
    assert "Check the audit log before retrying" in output
    assert "recorded successfully" not in output
    assert "No Google Workspace group memberships were changed" in output


def test_audited_decision_completed_review_blocks_save(monkeypatch, capsys):
    _, _, _, decision_write = _setup_audited_decision_workflow(
        monkeypatch, status="completed"
    )
    prompt = Mock(side_effect=["y", "1", "1", "n"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    decision_write.assert_not_called()
    assert prompt.call_count == 4
    output = capsys.readouterr().out
    assert "must be reopened" in output
    assert "Review reopening cancelled" in output


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_audited_decision_interrupted_confirmation_never_records(
    monkeypatch, capsys, interruption
):
    _, _, _, decision_write = _setup_audited_decision_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["y", "1", "1", interruption]))

    console.review_group_recommendations()

    decision_write.assert_not_called()
    assert "Decision save cancelled" in capsys.readouterr().out


# Step 474: console displays decisions restored from real local audit events.

@pytest.fixture
def console_persistence_audit_file(tmp_path, monkeypatch):
    """Use isolated JSONL audit storage; never touch Shore's real records."""
    from src import audit

    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "onboarding_audit.jsonl")
    return audit.AUDIT_FILE


def _setup_real_audit_console(monkeypatch):
    """Mock only onboarding UI inputs, not group approval persistence."""
    record = {
        "first_name": "Alex", "middle_name": "", "last_name": "Example",
        "position": "Teacher", "department": "Education", "program": "Harbors",
        "location": "Cambridge", "start_date": "2026-12-01",
        "shore_email": "alex.example@example.org", "devices": "Chromebook",
        "status": "Pending", "onboarding_id": "fictional-onboarding-001",
    }
    monkeypatch.setattr(console, "load_onboarding_history", Mock(return_value=[record]))
    monkeypatch.setattr(console, "display_records", Mock())
    monkeypatch.setattr(console, "select_history_record", Mock(return_value=1))
    monkeypatch.setattr(console, "employee_from_history", Mock(return_value=object()))
    monkeypatch.setattr(console, "display_group_recommendations", Mock())
    return record


def _start_real_audit_review(record):
    from src.group_approval import start_group_approval_review
    from src.group_catalog import GroupPolicy
    from src.group_recommendations import GroupRecommendation, GroupRecommendationResult

    recommendations = GroupRecommendationResult(recommendations=(
        GroupRecommendation(
            email="teachers@example.org", name="Teachers",
            policy=GroupPolicy.IT_APPROVAL,
            reason="Fictional teaching assignment", inherited=False,
        ),
        GroupRecommendation(
            email="harbors@example.org", name="Harbors",
            policy=GroupPolicy.MANUAL_REVIEW,
            reason="Fictional program assignment", inherited=False,
        ),
    ))
    return start_group_approval_review(
        onboarding_id=record["onboarding_id"],
        employee_email=record["shore_email"],
        recommendations=recommendations,
        administrator_name="Test Administrator",
    )


@pytest.mark.parametrize(
    ("decision", "display"),
    [("approved", "Approved"), ("rejected", "Rejected"), ("deferred", "Deferred")],
)
def test_console_restores_saved_decision_from_real_audit(
    console_persistence_audit_file, monkeypatch, capsys, decision, display
):
    """A separate console invocation shows the real persisted decision."""
    from src import audit
    from src.group_approval import GroupDecision, record_group_decision

    record = _setup_real_audit_console(monkeypatch)
    review = _start_real_audit_review(record)
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision(decision),
        administrator_name="Test Administrator",
    )
    events_before = audit.load_audit_events()
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Existing local group approval review found" in output
    assert "Review Status: In Progress" in output
    assert "Teachers <teachers@example.org>" in output
    assert f"Decision: {display}" in output
    assert "Harbors <harbors@example.org>" in output
    assert "Decision: Not Reviewed" in output
    expected_outstanding = 2 if decision == "deferred" else 1
    assert f"Outstanding Decisions: {expected_outstanding}" in output
    assert "No Google Workspace group memberships were changed." in output
    assert audit.load_audit_events() == events_before


def test_console_restores_changed_decision_from_real_audit(
    console_persistence_audit_file, monkeypatch, capsys
):
    """The most recent audited decision wins when option 13 reloads the review."""
    from src import audit
    from src.group_approval import GroupDecision, record_group_decision

    record = _setup_real_audit_console(monkeypatch)
    review = _start_real_audit_review(record)
    record_group_decision(
        review, group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="First Administrator",
    )
    record_group_decision(
        review, group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Second Administrator",
        change_reason="Fictional role correction",
    )
    events_before = audit.load_audit_events()
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Existing local group approval review found" in output
    assert "Teachers <teachers@example.org>" in output
    assert "Decision: Rejected" in output
    assert "Decision: Approved" not in output
    assert "Outstanding Decisions: 1" in output
    assert audit.load_audit_events() == events_before


def test_console_restores_completed_review_from_real_audit(
    console_persistence_audit_file, monkeypatch, capsys
):
    """Completed review status and final decisions survive audit restoration."""
    from src import audit
    from src.group_approval import (
        GroupDecision, complete_group_approval_review, record_group_decision,
    )

    record = _setup_real_audit_console(monkeypatch)
    review = _start_real_audit_review(record)
    record_group_decision(
        review, group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Test Administrator",
    )
    record_group_decision(
        review, group_email="harbors@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Test Administrator",
    )
    complete_group_approval_review(review, administrator_name="Test Administrator")
    events_before = audit.load_audit_events()
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    console.review_group_recommendations()

    output = capsys.readouterr().out
    assert "Review Status: Completed" in output
    assert "Decision: Approved" in output
    assert "Decision: Rejected" in output
    assert "Outstanding Decisions: 0" in output
    assert audit.load_audit_events() == events_before


# Step 477: console completion is explicit, validated, and audit-backed.


def _setup_completion_workflow(monkeypatch, *, decisions=("approved", "rejected"),
                               status="in_progress", can_complete=None):
    """Create a fictional review without touching Workspace or audit storage."""
    record = _setup_real_audit_console(monkeypatch)
    groups = {
        email: SimpleNamespace(
            group_name=name,
            group_email=email,
            decision=SimpleNamespace(value=decision),
        )
        for email, name, decision in (
            ("teachers@example.org", "Teachers", decisions[0]),
            ("harbors@example.org", "Harbors", decisions[1]),
        )
    }
    unresolved = [email for email, group in groups.items()
                  if group.decision.value not in {"approved", "rejected"}]
    if can_complete is None:
        can_complete = status == "in_progress" and not unresolved
    review = SimpleNamespace(
        onboarding_id=record["onboarding_id"],
        employee_email=record["shore_email"],
        status=SimpleNamespace(value=status),
        groups=groups,
        unresolved_groups=unresolved,
        can_complete=can_complete,
    )
    monkeypatch.setattr(console, "restore_group_approval_review", Mock(return_value=review))
    completion = Mock()
    monkeypatch.setattr(console, "complete_group_approval_review", completion)
    return review, completion


def test_completion_confirmed_calls_service_once(monkeypatch, capsys):
    review, completion = _setup_completion_workflow(monkeypatch)
    prompt = Mock(side_effect=["n", "yes", "Test Administrator"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    completion.assert_called_once_with(review, administrator_name="Test Administrator")
    assert prompt.call_count == 3
    output = capsys.readouterr().out
    assert "All groups have final decisions" in output
    assert "Local group approval review completed successfully" in output
    assert "No Google Workspace group memberships were changed" in output


@pytest.mark.parametrize("answer", ["n", "", "no"])
def test_completion_declined_does_not_write(monkeypatch, capsys, answer):
    _, completion = _setup_completion_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", answer]))

    console.review_group_recommendations()

    completion.assert_not_called()
    assert "Review completion cancelled" in capsys.readouterr().out


def test_completion_blank_administrator_blocks_write(monkeypatch, capsys):
    _, completion = _setup_completion_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", "y", "   "]))

    console.review_group_recommendations()

    completion.assert_not_called()
    assert "Administrator name is required. Review was not completed" in capsys.readouterr().out


@pytest.mark.parametrize("decisions", [
    ("not_reviewed", "approved"),
    ("approved", "deferred"),
])
def test_completion_unresolved_decisions_never_offer_completion(
    monkeypatch, capsys, decisions
):
    _, completion = _setup_completion_workflow(monkeypatch, decisions=decisions)
    prompt = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    prompt.assert_called_once()
    completion.assert_not_called()
    assert "Complete this LOCAL group approval review?" not in capsys.readouterr().out


def test_completion_already_completed_never_offers_completion(monkeypatch, capsys):
    _, completion = _setup_completion_workflow(
        monkeypatch, status="completed", can_complete=True
    )
    prompt = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    assert prompt.call_count == 2  # Decision prompt and new reopening prompt.
    completion.assert_not_called()
    output = capsys.readouterr().out
    assert "Complete this LOCAL group approval review?" not in output
    assert "Review reopening cancelled" in output


@pytest.mark.parametrize("error", [
    pytest.param(console.AuditWriteError("audit unavailable"), id="audit-failure"),
    pytest.param(console.GroupApprovalError("invalid review state"), id="validation-failure"),
])
def test_completion_failure_never_claims_success(monkeypatch, capsys, error):
    _, completion = _setup_completion_workflow(monkeypatch)
    completion.side_effect = error
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["n", "y", "Test Administrator"])
    )

    console.review_group_recommendations()

    completion.assert_called_once()
    output = capsys.readouterr().out
    assert "Unable to complete local group approval review" in output
    assert "Check the audit log before retrying" in output
    assert "completed successfully" not in output
    assert "No Google Workspace group memberships were changed" in output


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_completion_interrupted_confirmation_does_not_write(
    monkeypatch, capsys, interruption
):
    _, completion = _setup_completion_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", interruption]))

    console.review_group_recommendations()

    completion.assert_not_called()
    assert "Review completion cancelled" in capsys.readouterr().out


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_completion_interrupted_administrator_does_not_write(
    monkeypatch, capsys, interruption
):
    _, completion = _setup_completion_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", "y", interruption]))

    console.review_group_recommendations()

    completion.assert_not_called()
    assert "Review was not completed" in capsys.readouterr().out


def test_console_completion_persists_real_audit_event(
    console_persistence_audit_file, monkeypatch, capsys
):
    """Complete through the console and restore through the real local audit service."""
    from src import audit
    from src.group_approval import (
        GroupDecision, record_group_decision, restore_group_approval_review,
    )

    record = _setup_real_audit_console(monkeypatch)
    review = _start_real_audit_review(record)
    for group_email, decision in (
        ("teachers@example.org", GroupDecision.APPROVED),
        ("harbors@example.org", GroupDecision.REJECTED),
    ):
        record_group_decision(
            review, group_email=group_email, decision=decision,
            administrator_name="Test Administrator",
        )
    before = audit.load_audit_events()
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["n", "y", "Completion Administrator"])
    )

    console.review_group_recommendations()

    restored = restore_group_approval_review(onboarding_id=record["onboarding_id"])
    assert restored is not None
    assert restored.status.value == "completed"
    assert not restored.unresolved_groups
    assert len(audit.load_audit_events()) == len(before) + 1
    output = capsys.readouterr().out
    assert "Local group approval review completed successfully" in output
    assert "No Google Workspace group memberships were changed" in output

# Step 482: reopening a completed review is explicit, local, and audit-backed.


def _setup_reopening_workflow(monkeypatch):
    review, completion = _setup_completion_workflow(
        monkeypatch, status="completed", can_complete=True
    )
    reopen = Mock()
    monkeypatch.setattr(console, "reopen_group_approval_review", reopen)
    return review, reopen, completion


def test_reopening_confirmed_calls_service_once(monkeypatch, capsys):
    review, reopen, completion = _setup_reopening_workflow(monkeypatch)
    previous = {email: group.decision.value for email, group in review.groups.items()}
    prompt = Mock(side_effect=["n", "yes", "Reopening Administrator", "Correct access decision"])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    reopen.assert_called_once_with(
        review,
        administrator_name="Reopening Administrator",
        reopen_reason="Correct access decision",
    )
    completion.assert_not_called()
    assert {email: group.decision.value for email, group in review.groups.items()} == previous
    assert prompt.call_count == 4
    output = capsys.readouterr().out
    assert "Local group approval review reopened successfully" in output
    assert "No Google Workspace group memberships were changed" in output


@pytest.mark.parametrize("answer", ["n", "", "no", "N"])
def test_reopening_declined_does_not_write(monkeypatch, capsys, answer):
    _, reopen, completion = _setup_reopening_workflow(monkeypatch)
    prompt = Mock(side_effect=["n", answer])
    monkeypatch.setattr("builtins.input", prompt)

    console.review_group_recommendations()

    reopen.assert_not_called()
    completion.assert_not_called()
    assert prompt.call_count == 2
    assert "Review reopening cancelled" in capsys.readouterr().out


def test_reopening_blank_administrator_blocks_write(monkeypatch, capsys):
    _, reopen, _ = _setup_reopening_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", "y", "   "]))

    console.review_group_recommendations()

    reopen.assert_not_called()
    assert "Administrator name is required. Review was not reopened" in capsys.readouterr().out


def test_reopening_blank_reason_blocks_write(monkeypatch, capsys):
    _, reopen, _ = _setup_reopening_workflow(monkeypatch)
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["n", "y", "Test Administrator", "  "])
    )

    console.review_group_recommendations()

    reopen.assert_not_called()
    assert "A reopening reason is required. Review was not reopened" in capsys.readouterr().out


@pytest.mark.parametrize("error", [
    pytest.param(console.AuditWriteError("audit unavailable"), id="audit-write"),
    pytest.param(console.GroupApprovalError("invalid status"), id="validation"),
    pytest.param(OSError("storage unavailable"), id="os-error"),
])
def test_reopening_failure_never_claims_success(monkeypatch, capsys, error):
    _, reopen, completion = _setup_reopening_workflow(monkeypatch)
    reopen.side_effect = error
    monkeypatch.setattr(
        "builtins.input",
        Mock(side_effect=["n", "y", "Test Administrator", "Correction needed"]),
    )

    console.review_group_recommendations()

    reopen.assert_called_once()
    completion.assert_not_called()
    output = capsys.readouterr().out
    assert "Unable to reopen local group approval review" in output
    assert "Check the audit log before retrying" in output
    assert "reopened successfully" not in output
    assert "No Google Workspace group memberships were changed" in output


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_reopening_interrupted_confirmation_never_writes(
    monkeypatch, capsys, interruption
):
    _, reopen, _ = _setup_reopening_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", interruption]))

    console.review_group_recommendations()

    reopen.assert_not_called()
    assert "Review reopening cancelled" in capsys.readouterr().out


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_reopening_interrupted_administrator_never_writes(
    monkeypatch, capsys, interruption
):
    _, reopen, _ = _setup_reopening_workflow(monkeypatch)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", "y", interruption]))

    console.review_group_recommendations()

    reopen.assert_not_called()
    assert "Review was not reopened" in capsys.readouterr().out


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt(), OSError("unavailable")])
def test_reopening_interrupted_reason_never_writes(
    monkeypatch, capsys, interruption
):
    _, reopen, _ = _setup_reopening_workflow(monkeypatch)
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=["n", "y", "Test Administrator", interruption])
    )

    console.review_group_recommendations()

    reopen.assert_not_called()
    assert "Review was not reopened" in capsys.readouterr().out


def test_in_progress_review_never_offers_reopening(monkeypatch, capsys):
    _, completion = _setup_completion_workflow(monkeypatch, status="in_progress")
    reopen = Mock()
    monkeypatch.setattr(console, "reopen_group_approval_review", reopen)
    monkeypatch.setattr("builtins.input", Mock(side_effect=["n", "n"]))

    console.review_group_recommendations()

    reopen.assert_not_called()
    completion.assert_not_called()
    assert "Reopen this completed LOCAL" not in capsys.readouterr().out


def test_console_reopening_persists_real_audit_event(
    console_persistence_audit_file, monkeypatch, capsys
):
    """Reopening via console persists an event and keeps the final decisions."""
    from src import audit
    from src.group_approval import (
        GroupDecision, complete_group_approval_review, record_group_decision,
        restore_group_approval_review,
    )

    record = _setup_real_audit_console(monkeypatch)
    review = _start_real_audit_review(record)
    for group_email, decision in (
        ("teachers@example.org", GroupDecision.APPROVED),
        ("harbors@example.org", GroupDecision.REJECTED),
    ):
        record_group_decision(
            review, group_email=group_email, decision=decision,
            administrator_name="Test Administrator",
        )
    complete_group_approval_review(review, administrator_name="Test Administrator")
    before = audit.load_audit_events()
    monkeypatch.setattr(
        "builtins.input",
        Mock(side_effect=["n", "y", "Reopening Administrator", "Correct an access decision"]),
    )

    console.review_group_recommendations()

    restored = restore_group_approval_review(onboarding_id=record["onboarding_id"])
    assert restored.status.value == "in_progress"
    assert restored.groups["teachers@example.org"].decision is GroupDecision.APPROVED
    assert restored.groups["harbors@example.org"].decision is GroupDecision.REJECTED
    after = audit.load_audit_events()
    assert len(after) == len(before) + 1
    assert after[-1]["event_type"] == "group_review_reopened"
    assert after[-1]["details"]["reopen_reason"] == "Correct an access decision"
    assert after[-1]["details"]["administrator_name"] == "Reopening Administrator"
    output = capsys.readouterr().out
    assert "Local group approval review reopened successfully" in output
    assert "No Google Workspace group memberships were changed" in output
