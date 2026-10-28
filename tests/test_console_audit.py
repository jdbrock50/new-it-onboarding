
"""Tests for verification audit integration in the onboarding console."""

from datetime import date
from unittest.mock import patch

import pytest

from src import audit
from src.console import create_new_onboarding
from src.employee import Employee


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Keep audit events out of the real Shore data directory."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )


@pytest.fixture
def employee():
    """Return a fictional employee."""
    return Employee(
        first_name="Jane",
        middle_name="",
        last_name="Smith",
        job_title="Teacher",
        program="Education",
        location="Cambridge",
        supervisor="Test Supervisor",
        start_date=date(2026, 11, 2),
        personal_email="jane@example.org",
        device_needs=["Windows"],
    )


def test_successful_verification_is_audited(employee):
    """Record both successful directory lookups."""
    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_group_usernames",
            return_value=set(),
        ),
        patch("builtins.input", return_value="N"),
    ):
        create_new_onboarding()

    events = audit.load_audit_events()

    assert [event["event_type"] for event in events] == [
        "verification_completed", "onboarding_cancelled"
    ]
    assert events[0]["event_type"] == "verification_completed"
    assert events[0]["employee_email"] == (
        "jsmith@shorecollaborative.org"
    )
    assert events[0]["details"] == {
        "users_lookup": "success",
        "groups_lookup": "success",
        "verification_complete": True,
        "original_username": "jsmith",
        "resolved_username": "jsmith",
        "username_collision": False,
    }


@pytest.mark.parametrize(
    ("failed_directory", "expected_users", "expected_groups"),
    [
        ("users", "failed", "success"),
        ("groups", "success", "failed"),
    ],
)
def test_failed_directory_lookup_is_audited(
    employee,
    failed_directory,
    expected_users,
    expected_groups,
):
    """Record which Google Workspace directory lookup failed."""
    users_result = (
        OSError("Users unavailable")
        if failed_directory == "users"
        else set()
    )
    groups_result = (
        OSError("Groups unavailable")
        if failed_directory == "groups"
        else set()
    )

    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            side_effect=users_result
            if isinstance(users_result, OSError)
            else None,
            return_value=set(),
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            side_effect=groups_result
            if isinstance(groups_result, OSError)
            else None,
            return_value=set(),
        ),
        patch("builtins.input", return_value="N"),
    ):
        create_new_onboarding()

    events = audit.load_audit_events()

    assert [event["event_type"] for event in events] == [
        "verification_completed", "override_declined", "onboarding_cancelled"
    ]
    assert events[0]["details"]["users_lookup"] == expected_users
    assert events[0]["details"]["groups_lookup"] == expected_groups
    assert events[0]["details"]["verification_complete"] is False


def test_username_collision_is_audited(employee):
    """Record both the original and collision-resolved usernames."""
    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jsmith"},
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            return_value=set(),
        ),
        patch("builtins.input", return_value="N"),
    ):
        create_new_onboarding()

    event = audit.load_audit_events()[0]

    assert event["employee_email"] == (
        "jsmith1@shorecollaborative.org"
    )
    assert event["details"]["original_username"] == "jsmith"
    assert event["details"]["resolved_username"] == "jsmith1"
    assert event["details"]["username_collision"] is True


def test_audit_write_failure_blocks_onboarding(employee, capsys):
    """Do not create records when verification auditing fails."""
    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_group_usernames",
            return_value=set(),
        ),
        patch(
            "src.console.record_audit_event",
            side_effect=audit.AuditWriteError("Disk unavailable"),
        ),
        patch("builtins.input") as user_input,
        patch("src.console.create_checklist") as checklist,
        patch("src.console.save_onboarding_record") as history,
    ):
        create_new_onboarding()

    user_input.assert_not_called()
    checklist.assert_not_called()
    history.assert_not_called()

    output = capsys.readouterr().out
    assert "verification_completed audit could not be saved." in output
    assert "Onboarding stopped" in output


@pytest.fixture
def setup_onboarding(employee):
    """Patch the directories and employee collection for audit scenarios."""
    with (
        patch("src.console.collect_employee_information", return_value=employee),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_group_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value=set()) as users,
        patch("src.console.create_checklist", return_value="mock-checklist.txt") as checklist,
        patch("src.console.save_onboarding_record", return_value="mock-history.csv") as history,
    ):
        yield users, checklist, history


def event_types():
    """Return recorded audit event types in their original order."""
    return [event["event_type"] for event in audit.load_audit_events()]


def test_override_approved_records_administrator_and_reason(setup_onboarding):
    """Approved unverified email requires attribution and reason."""
    users, checklist, history = setup_onboarding
    users.side_effect = OSError("offline")
    with patch(
        "builtins.input",
        side_effect=["Y", "Jane Administrator", "HR urgent onboarding", "N"],
    ):
        create_new_onboarding()

    assert event_types() == [
        "verification_completed", "override_approved", "onboarding_cancelled"
    ]
    approval = audit.load_audit_events()[1]
    assert approval["details"] == {
        "administrator_name": "Jane Administrator",
        "approval_reason": "HR urgent onboarding",
        "verification_complete": False,
    }
    assert audit.load_audit_events()[2]["details"]["stage"] == "final_confirmation"
    checklist.assert_not_called()
    history.assert_not_called()


def test_declined_override_records_cancellation(setup_onboarding):
    """A rejected override records both decision and cancellation."""
    users, checklist, history = setup_onboarding
    users.side_effect = OSError("offline")
    with patch("builtins.input", return_value="N"):
        create_new_onboarding()
    assert event_types() == [
        "verification_completed", "override_declined", "onboarding_cancelled"
    ]
    assert audit.load_audit_events()[2]["details"]["stage"] == "unverified_email_override"
    checklist.assert_not_called()
    history.assert_not_called()


def test_verified_final_cancellation_is_audited(setup_onboarding):
    """A verified email can still be cancelled at final confirmation."""
    _users, checklist, history = setup_onboarding
    with patch("builtins.input", return_value="N"):
        create_new_onboarding()
    assert event_types() == ["verification_completed", "onboarding_cancelled"]
    cancellation = audit.load_audit_events()[1]
    assert cancellation["details"]["verification_complete"] is True
    assert cancellation["details"]["override_approved"] is False
    checklist.assert_not_called()
    history.assert_not_called()


def test_verified_creation_audit_is_after_file_operations(setup_onboarding):
    """Creation event follows checklist and history creation."""
    _users, checklist, history = setup_onboarding
    with patch("builtins.input", return_value="Y"):
        create_new_onboarding()
    assert event_types() == [
        "verification_completed", "onboarding_creation_authorized", "onboarding_created"
    ]
    checklist.assert_called_once()
    history.assert_called_once()
    created = audit.load_audit_events()[-1]
    assert created["details"]["checklist_path"] == "mock-checklist.txt"
    assert created["details"]["history_path"] == "mock-history.csv"


def test_unverified_creation_has_override_and_created_events(setup_onboarding):
    """Both authorization and completed creation are audited."""
    users, checklist, history = setup_onboarding
    users.side_effect = OSError("offline")
    with patch(
        "builtins.input",
        side_effect=["Y", "Jane Administrator", "Approved by HR", "Y"],
    ):
        create_new_onboarding()
    assert event_types() == [
        "verification_completed", "override_approved",
        "onboarding_creation_authorized", "onboarding_created"
    ]
    assert audit.load_audit_events()[-1]["details"]["administrator_name"] == (
        "Jane Administrator"
    )
    checklist.assert_called_once()
    history.assert_called_once()


@pytest.mark.parametrize("failed_event", ["override_approved", "onboarding_creation_authorized"])
def test_precreation_audit_failure_blocks_records(setup_onboarding, failed_event):
    """No checklist/history may be written if a required audit checkpoint fails."""
    users, checklist, history = setup_onboarding
    users.side_effect = OSError("offline")
    original = audit.record_audit_event

    def fail_selected(event_type, *, employee_email, details):
        if event_type == failed_event:
            raise audit.AuditWriteError("Disk unavailable")
        return original(event_type, employee_email=employee_email, details=details)

    with (
        patch("src.console.record_audit_event", side_effect=fail_selected),
        patch(
            "builtins.input",
            side_effect=["Y", "Jane Administrator", "HR approved", "Y"],
        ),
    ):
        create_new_onboarding()

    checklist.assert_not_called()
    history.assert_not_called()
    assert failed_event not in event_types()
    assert "onboarding_created" not in event_types()


def test_blank_admin_fields_are_reprompted(setup_onboarding, capsys):
    """Blank administrator identity and reason are not accepted."""
    users, checklist, history = setup_onboarding
    users.side_effect = OSError("offline")
    with patch(
        "builtins.input",
        side_effect=["Y", " ", "Jane Administrator", "", "HR approved", "N"],
    ) as prompt:
        create_new_onboarding()
    assert prompt.call_count == 6
    assert capsys.readouterr().out.count("This field is required") == 2
    approval = audit.load_audit_events()[1]
    assert approval["details"]["administrator_name"] == "Jane Administrator"
    assert approval["details"]["approval_reason"] == "HR approved"
    checklist.assert_not_called()
    history.assert_not_called()


def test_creation_audit_failure_does_not_claim_success(setup_onboarding, capsys):
    """If post-creation audit fails, report partial state instead of success."""
    _users, checklist, history = setup_onboarding
    original = audit.record_audit_event

    def fail_creation(event_type, *, employee_email, details):
        if event_type == "onboarding_created":
            raise audit.AuditWriteError("Disk unavailable")
        return original(event_type, employee_email=employee_email, details=details)

    with (
        patch("src.console.record_audit_event", side_effect=fail_creation),
        patch("builtins.input", return_value="Y"),
    ):
        create_new_onboarding()
    checklist.assert_called_once()
    history.assert_called_once()
    output = capsys.readouterr().out
    assert "review them manually" in output
    assert "Onboarding created successfully." not in output
    assert "onboarding_created" not in event_types()
