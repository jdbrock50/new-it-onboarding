
"""Tests for IT onboarding checklist generation."""

from datetime import date

from src.employee import Employee
from src.onboarding import generate_onboarding_tasks


def make_employee(
    first_name: str = "Jane",
    last_name: str = "Smith",
    device_needs: list[str] | None = None,
) -> Employee:
    """Create a fictional employee for onboarding tests."""
    return Employee(
        first_name=first_name,
        last_name=last_name,
        job_title="Teacher",
        program="Shore",
        location="Main Campus",
        supervisor="Test Supervisor",
        start_date=date(2026, 10, 5),
        personal_email="test@example.com",
        device_needs=(
            ["Chromebook"]
            if device_needs is None
            else device_needs
        ),
    )


def test_generate_standard_onboarding_tasks():
    employee = make_employee()

    tasks = generate_onboarding_tasks(employee)

    assert len(tasks) > 0

    categories = {task.category for task in tasks}

    assert "Accounts & Access" in categories
    assert "Device" in categories
    assert "Printing" in categories
    assert "Security" in categories
    assert "Final Verification" in categories


def test_tasks_start_incomplete():
    employee = make_employee()

    tasks = generate_onboarding_tasks(employee)

    assert all(not task.completed for task in tasks)


def test_chromebook_uses_google_admin():
    employee = make_employee()

    tasks = generate_onboarding_tasks(employee)

    descriptions = [task.description for task in tasks]

    assert "Enroll/configure Chromebook using Google Admin" in descriptions


def test_android_management_requires_review():
    employee = make_employee(
        first_name="John",
        device_needs=["Android"],
    )

    tasks = generate_onboarding_tasks(employee)

    descriptions = [task.description for task in tasks]

    assert "Determine management platform for Android" in descriptions


def test_employee_handoff_tasks_are_created():
    employee = make_employee()

    tasks = generate_onboarding_tasks(employee)

    categories = {task.category for task in tasks}

    assert "Employee Handoff" in categories


def test_resolved_email_used_in_account_tasks():
    """Account tasks must use the collision-resolved email."""
    employee = make_employee(
        first_name="Joseph",
        last_name="Mercado",
    )

    resolved_email = "jmercado1@shorecollaborative.org"

    tasks = generate_onboarding_tasks(
        employee,
        shore_email=resolved_email,
    )

    account_descriptions = [
        task.description
        for task in tasks
        if task.category == "Accounts & Access"
    ]

    assert (
        "Verify proposed Shore username "
        "(jmercado1) is available"
    ) in account_descriptions

    assert (
        "Create jmercado1@shorecollaborative.org "
        "Google Workspace account"
    ) in account_descriptions

    assert not any(
        "Create jmercado@shorecollaborative.org "
        "Google Workspace account" == description
        for description in account_descriptions
    )


def test_resolved_email_used_in_employee_handoff():
    """Employee handoff must use the collision-resolved email."""
    employee = make_employee(
        first_name="Joseph",
        last_name="Mercado",
    )

    resolved_email = "jmercado1@shorecollaborative.org"

    tasks = generate_onboarding_tasks(
        employee,
        shore_email=resolved_email,
    )

    handoff_descriptions = [
        task.description
        for task in tasks
        if task.category == "Employee Handoff"
    ]

    assert f"Provide {resolved_email}" in handoff_descriptions
    assert (
        "Provide jmercado@shorecollaborative.org"
        not in handoff_descriptions
    )
