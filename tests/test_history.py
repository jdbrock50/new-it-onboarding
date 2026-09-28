"""Tests for onboarding history."""

import csv
from datetime import date

import pytest

from src.employee import Employee
from src.history import (
    get_existing_usernames,
    get_pending_onboardings,
    get_upcoming_hires,
    load_onboarding_history,
    save_onboarding_record,
    update_onboarding_status,
)


def create_test_employee(
    first_name: str = "Maria",
    last_name: str = "Gonzalez",
    start_date: date = date(2026, 10, 5),
) -> Employee:
    """Create an employee for history tests."""

    return Employee(
        first_name=first_name,
        middle_name="",
        last_name=last_name,
        job_title="Teacher",
        program="Sail Middle School",
        location="Cambridge",
        supervisor="Jane Doe",
        start_date=start_date,
        personal_email="employee@example.com",
        device_needs=["Windows"],
    )


def test_save_onboarding_record(
    tmp_path,
    monkeypatch,
):
    """Test that an onboarding record is saved."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = Employee(
        first_name="Maria",
        middle_name="L",
        last_name="Gonzalez",
        job_title="Teacher",
        program="Sail Middle School",
        location="Cambridge",
        supervisor="Jane Doe",
        start_date=date(2026, 10, 5),
        personal_email="maria@example.com",
        device_needs=["Windows", "Android"],
    )

    result = save_onboarding_record(employee)

    assert result.exists()

    with result.open(
        newline="",
        encoding="utf-8",
    ) as file:
        records = list(csv.DictReader(file))

    assert len(records) == 1

    record = records[0]

    assert record["first_name"] == "Maria"
    assert record["middle_name"] == "L"
    assert record["last_name"] == "Gonzalez"
    assert record["shore_email"] == (
        "mgonzalez@shorecollaborative.org"
    )
    assert record["devices"] == "Windows, Android"
    assert record["status"] == "Pending"
    assert record["created_at"]
    assert record["updated_at"]


def test_save_multiple_onboarding_records(
    tmp_path,
    monkeypatch,
):
    """Test that multiple employees append to history."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    first_employee = create_test_employee(
        first_name="Maria",
        last_name="Gonzalez",
    )

    second_employee = create_test_employee(
        first_name="Mark",
        last_name="Smith",
    )

    save_onboarding_record(first_employee)
    save_onboarding_record(second_employee)

    records = load_onboarding_history()

    assert len(records) == 2
    assert records[0]["first_name"] == "Maria"
    assert records[1]["first_name"] == "Mark"


def test_save_resolved_shore_email(
    tmp_path,
    monkeypatch,
):
    """Test that a resolved Shore email can be stored."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = Employee(
        first_name="Mary",
        middle_name="Anne",
        last_name="Smith",
        job_title="Teacher",
        program="Sail Middle School",
        location="Cambridge",
        supervisor="Jane Doe",
        start_date=date(2026, 10, 5),
        personal_email="mary@example.com",
        device_needs=["Chromebook"],
    )

    save_onboarding_record(
        employee,
        shore_email="masmith@shorecollaborative.org",
    )

    records = load_onboarding_history()

    assert records[0]["shore_email"] == (
        "masmith@shorecollaborative.org"
    )


def test_get_existing_usernames(
    tmp_path,
    monkeypatch,
):
    """Test extracting usernames from Shore email addresses."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    first_employee = create_test_employee(
        first_name="Maria",
        last_name="Gonzalez",
    )

    second_employee = create_test_employee(
        first_name="Mark",
        last_name="Smith",
    )

    save_onboarding_record(
        first_employee,
        shore_email="mgonzalez@shorecollaborative.org",
    )

    save_onboarding_record(
        second_employee,
        shore_email="msmith@shorecollaborative.org",
    )

    usernames = get_existing_usernames()

    assert usernames == {
        "mgonzalez",
        "msmith",
    }


def test_existing_usernames_are_lowercase(
    tmp_path,
    monkeypatch,
):
    """Test usernames are normalized to lowercase."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = create_test_employee()

    save_onboarding_record(
        employee,
        shore_email="MGONZALEZ@shorecollaborative.org",
    )

    usernames = get_existing_usernames()

    assert usernames == {"mgonzalez"}


def test_load_history_when_file_does_not_exist(
    tmp_path,
    monkeypatch,
):
    """Test loading history when no history file exists."""

    history_file = tmp_path / "missing.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    records = load_onboarding_history()

    assert records == []


def test_get_pending_onboardings(
    tmp_path,
    monkeypatch,
):
    """Test pending and in-progress records are unfinished."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    pending_employee = create_test_employee(
        first_name="Pending",
        last_name="Employee",
    )

    progress_employee = create_test_employee(
        first_name="Progress",
        last_name="Employee",
    )

    completed_employee = create_test_employee(
        first_name="Completed",
        last_name="Employee",
    )

    save_onboarding_record(pending_employee)
    save_onboarding_record(progress_employee)
    save_onboarding_record(completed_employee)

    update_onboarding_status(
        2,
        "In Progress",
    )

    update_onboarding_status(
        3,
        "Completed",
    )

    records = get_pending_onboardings()

    assert len(records) == 2
    assert records[0]["first_name"] == "Pending"
    assert records[1]["first_name"] == "Progress"


def test_get_upcoming_hires(
    tmp_path,
    monkeypatch,
):
    """Test filtering employees by upcoming start date."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    past_employee = create_test_employee(
        first_name="Past",
        last_name="Employee",
        start_date=date(2026, 9, 1),
    )

    current_employee = create_test_employee(
        first_name="Current",
        last_name="Employee",
        start_date=date(2026, 9, 28),
    )

    future_employee = create_test_employee(
        first_name="Future",
        last_name="Employee",
        start_date=date(2026, 10, 15),
    )

    save_onboarding_record(past_employee)
    save_onboarding_record(current_employee)
    save_onboarding_record(future_employee)

    records = get_upcoming_hires(
        today=date(2026, 9, 28),
    )

    assert len(records) == 2
    assert records[0]["first_name"] == "Current"
    assert records[1]["first_name"] == "Future"


def test_cancelled_employee_not_upcoming(
    tmp_path,
    monkeypatch,
):
    """Test cancelled employees are excluded from upcoming hires."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = create_test_employee(
        first_name="Cancelled",
        last_name="Employee",
        start_date=date(2026, 10, 15),
    )

    save_onboarding_record(employee)

    update_onboarding_status(
        1,
        "Cancelled",
    )

    records = get_upcoming_hires(
        today=date(2026, 9, 28),
    )

    assert records == []


def test_update_onboarding_status(
    tmp_path,
    monkeypatch,
):
    """Test updating an onboarding record status."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = create_test_employee()

    save_onboarding_record(employee)

    updated = update_onboarding_status(
        1,
        "Completed",
    )

    assert updated["status"] == "Completed"
    assert updated["updated_at"]

    records = load_onboarding_history()

    assert records[0]["status"] == "Completed"


def test_invalid_status_is_rejected(
    tmp_path,
    monkeypatch,
):
    """Test that an invalid onboarding status is rejected."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = create_test_employee()

    save_onboarding_record(employee)

    with pytest.raises(
        ValueError,
        match="Invalid onboarding status",
    ):
        update_onboarding_status(
            1,
            "Bananas",
        )


def test_invalid_record_number_is_rejected(
    tmp_path,
    monkeypatch,
):
    """Test that an invalid record number is rejected."""

    history_file = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        history_file,
    )

    employee = create_test_employee()

    save_onboarding_record(employee)

    with pytest.raises(
        IndexError,
        match="Invalid onboarding record number",
    ):
        update_onboarding_status(
            99,
            "Completed",
        )