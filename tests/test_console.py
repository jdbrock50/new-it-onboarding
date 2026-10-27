
"""Tests for Google Workspace integration in the onboarding console."""

"""Tests for Google Workspace integration in the onboarding console."""

from datetime import date
from unittest.mock import patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src.console import create_new_onboarding, resolve_employee_email
from src.employee import Employee


@pytest.fixture(autouse=True)
def mock_group_directory():
    """Avoid real Groups API calls in console tests."""
    with patch("src.console.get_workspace_group_usernames", return_value=set()):
        yield


def make_employee(middle_name: str = "") -> Employee:
    """Create a fictional employee for testing."""
    return Employee(
        first_name="Joseph",
        middle_name=middle_name,
        last_name="Mercado",
        job_title="Technology Support Specialist",
        program="Technology",
        location="Cambridge",
        supervisor="Test Supervisor",
        start_date=date(2026, 11, 2),
        personal_email="test@example.org",
        device_needs=["Windows"],
    )


def test_live_workspace_collision_uses_numeric_suffix():
    """Use a numeric suffix when the base username exists."""
    employee = make_employee()

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado"},
        ),
    ):
        username, email = resolve_employee_email(employee)

    assert username == "jmercado1"
    assert email == "jmercado1@shorecollaborative.org"


def test_live_workspace_collision_uses_middle_initial():
    """Prefer a middle initial when the base username exists."""
    employee = make_employee(middle_name="David")

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado"},
        ),
    ):
        username, email = resolve_employee_email(employee)

    assert username == "jdmercado"
    assert email == "jdmercado@shorecollaborative.org"


def test_local_and_workspace_collisions_are_combined():
    """Check locally reserved and live Google Workspace usernames."""
    employee = make_employee()

    with (
        patch(
            "src.console.get_existing_usernames",
            return_value={"jmercado1"},
        ),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado", "jmercado2"},
        ),
    ):
        username, email = resolve_employee_email(employee)

    assert username == "jmercado3"
    assert email == "jmercado3@shorecollaborative.org"


def test_workspace_failure_uses_local_records(capsys):
    """Warn when live verification fails and use local reservations."""
    employee = make_employee()

    error = HttpError(
        resp=Response({"status": 403}),
        content=b'{"error": {"message": "Forbidden"}}',
    )

    with (
        patch(
            "src.console.get_existing_usernames",
            return_value={"jmercado"},
        ),
        patch("src.console.get_workspace_usernames", side_effect=error),
    ):
        username, email = resolve_employee_email(employee)

    output = capsys.readouterr().out

    assert username == "jmercado1"
    assert email == "jmercado1@shorecollaborative.org"
    assert "WARNING: Google Workspace verification failed." in output
    assert "Username availability is NOT verified." in output


def test_workspace_success_displays_confirmation(capsys):
    """Confirm that a successful directory lookup is reported."""
    employee = make_employee()

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado"},
        ),
    ):
        resolve_employee_email(employee)

    output = capsys.readouterr().out

    assert "Google Workspace directory check successful." in output
    assert "Directory addresses checked: 1" in output


def test_create_onboarding_uses_resolved_email_everywhere(capsys):
    """Pass the collision-resolved email to tasks, checklist, and history."""
    employee = make_employee()
    resolved_email = "jmercado1@shorecollaborative.org"
    captured_tasks = []

    def fake_create_checklist(received_employee, tasks, *, shore_email):
        assert received_employee is employee
        assert shore_email == resolved_email
        captured_tasks.extend(tasks)
        return "mock-checklist.txt"

    with (
        patch("src.console.collect_employee_information", return_value=employee),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value={"jmercado"}),
        patch("builtins.input", return_value="Y"),
        patch("src.console.create_checklist", side_effect=fake_create_checklist) as checklist,
        patch("src.console.save_onboarding_record", return_value="mock-history.csv") as history,
    ):
        create_new_onboarding()

    checklist.assert_called_once()
    history.assert_called_once_with(employee, shore_email=resolved_email)
    descriptions = [task.description for task in captured_tasks]
    assert "Verify proposed Shore username (jmercado1) is available" in descriptions
    assert f"Create {resolved_email} Google Workspace account" in descriptions
    assert f"Provide {resolved_email}" in descriptions
    assert "Create jmercado@shorecollaborative.org Google Workspace account" not in descriptions
    assert "Provide jmercado@shorecollaborative.org" not in descriptions
    assert f"Shore Email: {resolved_email}" in capsys.readouterr().out


def test_group_collision_uses_numeric_suffix():
    """A group address must reserve the same username as a user."""
    employee = make_employee()
    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value=set()),
        patch("src.console.get_workspace_group_usernames", return_value={"jmercado"}),
    ):
        username, email = resolve_employee_email(employee)
    assert username == "jmercado1"
    assert email == "jmercado1@shorecollaborative.org"


def test_group_lookup_failure_warns_and_preserves_user_collisions(capsys):
    """A failed group check must never claim full verification."""
    employee = make_employee()
    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", return_value={"jmercado"}),
        patch("src.console.get_workspace_group_usernames", side_effect=OSError("offline")),
    ):
        username, _ = resolve_employee_email(employee)
    assert username == "jmercado1"
    assert "Username availability is NOT verified." in capsys.readouterr().out


def test_user_lookup_failure_preserves_group_collisions(capsys):
    """A failed user check still respects successfully loaded groups."""
    employee = make_employee()
    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch("src.console.get_workspace_usernames", side_effect=OSError("offline")),
        patch("src.console.get_workspace_group_usernames", return_value={"jmercado"}),
    ):
        username, _ = resolve_employee_email(employee)
    assert username == "jmercado1"
    assert "Username availability is NOT verified." in capsys.readouterr().out
