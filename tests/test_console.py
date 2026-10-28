
"""Tests for Google Workspace integration in the onboarding console."""

from datetime import date
from unittest.mock import patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src.console import (
    confirm_unverified_email,
    create_new_onboarding,
    resolve_employee_email,
)
from src.employee import Employee


@pytest.fixture(autouse=True)
def mock_group_directory():
    """Avoid real Groups API calls in console tests."""
    with patch(
        "src.console.get_workspace_group_usernames",
        return_value=set(),
    ):
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
        patch(
            "src.console.get_workspace_usernames",
            side_effect=error,
        ),
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
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado"},
        ),
        patch("builtins.input", return_value="Y"),
        patch(
            "src.console.create_checklist",
            side_effect=fake_create_checklist,
        ) as checklist,
        patch(
            "src.console.save_onboarding_record",
            return_value="mock-history.csv",
        ) as history,
    ):
        create_new_onboarding()

    checklist.assert_called_once()
    history.assert_called_once_with(
        employee,
        shore_email=resolved_email,
    )

    descriptions = [task.description for task in captured_tasks]

    assert (
        "Verify proposed Shore username (jmercado1) is available"
        in descriptions
    )
    assert (
        f"Create {resolved_email} Google Workspace account"
        in descriptions
    )
    assert f"Provide {resolved_email}" in descriptions
    assert (
        "Create jmercado@shorecollaborative.org Google Workspace account"
        not in descriptions
    )
    assert (
        "Provide jmercado@shorecollaborative.org"
        not in descriptions
    )
    assert (
        f"Shore Email: {resolved_email}"
        in capsys.readouterr().out
    )


def test_group_collision_uses_numeric_suffix():
    """A group address must reserve the same username as a user."""
    employee = make_employee()

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value=set(),
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            return_value={"jmercado"},
        ),
    ):
        username, email = resolve_employee_email(employee)

    assert username == "jmercado1"
    assert email == "jmercado1@shorecollaborative.org"


def test_group_lookup_failure_warns_and_preserves_user_collisions(capsys):
    """A failed group check must never claim full verification."""
    employee = make_employee()

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value={"jmercado"},
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            side_effect=OSError("offline"),
        ),
    ):
        username, _ = resolve_employee_email(employee)

    assert username == "jmercado1"
    assert (
        "Username availability is NOT verified."
        in capsys.readouterr().out
    )


def test_user_lookup_failure_preserves_group_collisions(capsys):
    """A failed user check still respects successfully loaded groups."""
    employee = make_employee()

    with (
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            side_effect=OSError("offline"),
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            return_value={"jmercado"},
        ),
    ):
        username, _ = resolve_employee_email(employee)

    assert username == "jmercado1"
    assert (
        "Username availability is NOT verified."
        in capsys.readouterr().out
    )


# ------------------------------------------------------------
# Administrator verification safeguard tests
# ------------------------------------------------------------


@pytest.mark.parametrize("answer", ["", "N", "no", "maybe"])
def test_unverified_confirmation_rejects_nonapproval(answer):
    """Only explicit approval may override incomplete verification."""
    with patch("builtins.input", return_value=answer):
        approved = confirm_unverified_email(
            "jmercado@shorecollaborative.org"
        )

    assert approved is False


@pytest.mark.parametrize("answer", ["Y", "yes"])
def test_unverified_confirmation_accepts_explicit_approval(answer):
    """Accept explicit administrator approval."""
    with patch("builtins.input", return_value=answer):
        approved = confirm_unverified_email(
            "jmercado@shorecollaborative.org"
        )

    assert approved is True


@pytest.mark.parametrize("failed_lookup", ["Users", "Groups"])
def test_failed_directory_lookup_requires_approval_and_can_cancel(
    failed_lookup,
    capsys,
):
    """Cancelling an unverified onboarding must not save records."""
    employee = make_employee()

    user_result = (
        OSError("Users offline")
        if failed_lookup == "Users"
        else {"jmercado"}
    )
    group_result = (
        OSError("Groups offline")
        if failed_lookup == "Groups"
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
            side_effect=user_result
            if isinstance(user_result, OSError)
            else None,
            return_value=user_result
            if not isinstance(user_result, OSError)
            else None,
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            side_effect=group_result
            if isinstance(group_result, OSError)
            else None,
            return_value=group_result
            if not isinstance(group_result, OSError)
            else None,
        ),
        patch("builtins.input", return_value="N") as user_input,
        patch("src.console.create_checklist") as checklist,
        patch("src.console.save_onboarding_record") as history,
    ):
        create_new_onboarding()

    output = capsys.readouterr().out

    assert "GOOGLE WORKSPACE VERIFICATION INCOMPLETE" in output
    assert "Onboarding cancelled." in output
    assert user_input.call_count == 1
    assert "UNVERIFIED email" in user_input.call_args.args[0]
    checklist.assert_not_called()
    history.assert_not_called()


def test_both_directory_lookups_fail_and_blank_cancels(capsys):
    """A blank response must cancel when both lookups fail."""
    employee = make_employee()

    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            side_effect=OSError("Users offline"),
        ),
        patch(
            "src.console.get_workspace_group_usernames",
            side_effect=OSError("Groups offline"),
        ),
        patch("builtins.input", return_value="") as user_input,
        patch("src.console.create_checklist") as checklist,
        patch("src.console.save_onboarding_record") as history,
    ):
        create_new_onboarding()

    assert user_input.call_count == 1
    assert "NOT fully verified" in capsys.readouterr().out
    checklist.assert_not_called()
    history.assert_not_called()


def test_approval_still_requires_final_confirmation(capsys):
    """Approval of an unverified address is not final approval."""
    employee = make_employee()

    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            side_effect=OSError("Users offline"),
        ),
        patch(
            "builtins.input",
            side_effect=["Y", "N"],
        ) as user_input,
        patch("src.console.create_checklist") as checklist,
        patch("src.console.save_onboarding_record") as history,
    ):
        create_new_onboarding()

    output = capsys.readouterr().out

    assert user_input.call_count == 2
    assert "Onboarding cancelled." in output
    checklist.assert_not_called()
    history.assert_not_called()


def test_explicit_approval_allows_unverified_onboarding(capsys):
    """Two affirmative confirmations allow an unverified onboarding."""
    employee = make_employee()
    expected_email = "jmercado1@shorecollaborative.org"

    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch(
            "src.console.get_existing_usernames",
            return_value={"jmercado"},
        ),
        patch(
            "src.console.get_workspace_usernames",
            side_effect=OSError("Users offline"),
        ),
        patch(
            "builtins.input",
            side_effect=["Y", "Y"],
        ) as user_input,
        patch(
            "src.console.create_checklist",
            return_value="mock-checklist.txt",
        ) as checklist,
        patch(
            "src.console.save_onboarding_record",
            return_value="mock-history.csv",
        ) as history,
    ):
        create_new_onboarding()

    assert user_input.call_count == 2
    checklist.assert_called_once()
    history.assert_called_once_with(
        employee,
        shore_email=expected_email,
    )
    assert (
        "Onboarding created successfully."
        in capsys.readouterr().out
    )


def test_verified_onboarding_skips_extra_approval():
    """Successful directory checks require only normal confirmation."""
    employee = make_employee()

    with (
        patch(
            "src.console.collect_employee_information",
            return_value=employee,
        ),
        patch("src.console.get_existing_usernames", return_value=set()),
        patch(
            "src.console.get_workspace_usernames",
            return_value=set(),
        ),
        patch("builtins.input", return_value="N") as user_input,
        patch("src.console.create_checklist") as checklist,
        patch("src.console.save_onboarding_record") as history,
    ):
        create_new_onboarding()

    assert user_input.call_count == 1
    assert "Create this onboarding?" in user_input.call_args.args[0]
    checklist.assert_not_called()
    history.assert_not_called()
