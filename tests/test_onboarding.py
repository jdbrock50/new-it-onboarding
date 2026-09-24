"""Tests for IT onboarding checklist generation."""

from datetime import date

from src.employee import Employee
from src.onboarding import generate_onboarding_tasks


def test_generate_standard_onboarding_tasks():
    employee = Employee(
        first_name="Jane",
        last_name="Smith",
        job_title="Teacher",
        program="Shore",
        location="Main Campus",
        supervisor="John Doe",
        start_date=date(2026, 10, 5),
        personal_email="jane.smith@example.com",
        device_needs=["Chromebook"],
    )

    tasks = generate_onboarding_tasks(employee)

    assert len(tasks) > 0

    categories = {task.category for task in tasks}

    assert "Accounts & Access" in categories
    assert "Device" in categories
    assert "Printing" in categories
    assert "Security" in categories
    assert "Final Verification" in categories


def test_tasks_start_incomplete():
    employee = Employee(
        first_name="Jane",
        last_name="Smith",
        job_title="Teacher",
        program="Shore",
        location="Main Campus",
        supervisor="John Doe",
        start_date=date(2026, 10, 5),
        personal_email="jane.smith@example.com",
        device_needs=["Chromebook"],
    )

    tasks = generate_onboarding_tasks(employee)

    assert all(not task.completed for task in tasks)

def test_chromebook_uses_google_admin():
    employee = Employee(
        first_name="Jane",
        last_name="Smith",
        job_title="Teacher",
        program="Shore",
        location="Main Campus",
        supervisor="John Doe",
        start_date=date(2026, 10, 5),
        personal_email="jane.smith@example.com",
        device_needs=["Chromebook"],
    )

    tasks = generate_onboarding_tasks(employee)

    descriptions = [task.description for task in tasks]

    assert "Enroll/configure Chromebook using Google Admin" in descriptions

def test_android_management_requires_review():
    employee = Employee(
        first_name="John",
        last_name="Smith",
        job_title="Paraprofessional",
        program="Inspire",
        location="Chelsea",
        supervisor="Test Supervisor",
        start_date=date(2026, 10, 4),
        personal_email="john@example.com",
        device_needs=["Android"],
    )

    tasks = generate_onboarding_tasks(employee)

    descriptions = [task.description for task in tasks]

    assert "Determine management platform for Android" in descriptions


def test_employee_handoff_tasks_are_created():
    employee = Employee(
        first_name="John",
        last_name="Smith",
        job_title="Paraprofessional",
        program="Inspire",
        location="Chelsea",
        supervisor="Test Supervisor",
        start_date=date(2026, 10, 4),
        personal_email="john@example.com",
        device_needs=["Chromebook"],
    )

    tasks = generate_onboarding_tasks(employee)

    categories = {task.category for task in tasks}

    assert "Employee Handoff" in categories