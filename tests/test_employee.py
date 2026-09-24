from datetime import date

from src.employee import Employee


def test_employee_full_name():
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

    assert employee.full_name == "Jane Smith"


def test_employee_device_needs():
    employee = Employee(
        first_name="Jane",
        last_name="Smith",
        job_title="Administrator",
        program="Shore",
        location="Main Campus",
        supervisor="John Doe",
        start_date=date(2026, 10, 5),
        personal_email="jane.smith@example.com",
        device_needs=["MacBook", "iPhone"],
    )

    assert "MacBook" in employee.device_needs
    assert "iPhone" in employee.device_needs
    assert len(employee.device_needs) == 2