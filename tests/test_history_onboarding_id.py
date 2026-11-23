
"""Tests for explicitly supplied and automatically generated onboarding IDs."""

import csv
from datetime import date
from uuid import UUID

import pytest

from src.employee import Employee
from src.history import save_onboarding_record


@pytest.fixture
def history_file(tmp_path, monkeypatch):
    """Isolate onboarding history from production data."""
    file_path = tmp_path / "onboarding_history.csv"

    monkeypatch.setattr(
        "src.history.HISTORY_FILE",
        file_path,
    )
    monkeypatch.setattr(
        "src.history.DATA_DIR",
        tmp_path,
    )

    return file_path


def make_employee():
    """Create a fictional employee for testing."""
    return Employee(
        first_name="Alex",
        middle_name="",
        last_name="Morgan",
        job_title="Teacher",
        program="Sail Middle School",
        location="Cambridge",
        supervisor="Jane Administrator",
        start_date=date(2026, 12, 1),
        personal_email="alex@example.org",
        device_needs=["Windows"],
    )


def read_records(history_file):
    """Read saved onboarding records."""
    with history_file.open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def test_explicit_onboarding_id_is_preserved(history_file):
    """An existing onboarding ID must be stored unchanged."""
    employee = make_employee()
    onboarding_id = "123e4567-e89b-42d3-a456-426614174000"

    save_onboarding_record(
        employee,
        onboarding_id=onboarding_id,
    )

    records = read_records(history_file)

    assert len(records) == 1
    assert records[0]["onboarding_id"] == onboarding_id


def test_omitted_onboarding_id_generates_uuid(history_file):
    """Existing callers must continue receiving generated UUIDs."""
    employee = make_employee()

    save_onboarding_record(employee)

    records = read_records(history_file)

    assert len(records) == 1
    assert UUID(records[0]["onboarding_id"]).version == 4


def test_explicit_id_does_not_change_employee_data(history_file):
    """Supplying an ID must preserve the existing record fields."""
    employee = make_employee()

    save_onboarding_record(
        employee,
        shore_email="alex.morgan@shorecollaborative.org",
        onboarding_id="123e4567-e89b-42d3-a456-426614174000",
    )

    record = read_records(history_file)[0]

    assert record["first_name"] == "Alex"
    assert record["last_name"] == "Morgan"
    assert record["position"] == "Teacher"
    assert record["shore_email"] == (
        "alex.morgan@shorecollaborative.org"
    )
    assert record["status"] == "Pending"


def test_multiple_generated_ids_are_unique(history_file):
    """Separate onboarding records must receive distinct IDs."""
    employee = make_employee()

    save_onboarding_record(employee)
    save_onboarding_record(employee)

    records = read_records(history_file)

    assert len(records) == 2
    assert records[0]["onboarding_id"] != records[1]["onboarding_id"]
