"""Main entry point for the New Employee IT Onboarding application."""

import logging
from datetime import date
from pathlib import Path

from src.checklist import create_checklist
from src.employee import Employee
from src.onboarding import generate_onboarding_tasks

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger(__name__)

DEVICE_OPTIONS = {
    "1": "Chromebook",
    "2": "Windows",
    "3": "MacBook",
    "4": "iPhone",
    "5": "iPad",
    "6": "Android",
    "7": "None",
}


def configure_logging() -> None:
    """Configure application logging."""
    LOG_DIR.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ],
    )


def get_required_input(prompt: str) -> str:
    """Prompt until the user enters a non-empty value."""
    while True:
        value = input(prompt).strip()

        if value:
            return value

        print("This field is required. Please try again.")


def get_start_date() -> date:
    """Prompt for and validate an employee start date."""
    while True:
        value = input("Start date (YYYY-MM-DD): ").strip()

        try:
            return date.fromisoformat(value)
        except ValueError:
            print("Invalid date. Please use YYYY-MM-DD.")


def get_device_needs() -> list[str]:
    """Display the device menu and return selected devices."""
    while True:
        print()
        print("Device Needs")
        print("------------")
        print("1. Chromebook")
        print("2. Windows Laptop")
        print("3. MacBook")
        print("4. iPhone")
        print("5. iPad")
        print("6. Android")
        print("7. None")
        print()
        print("Enter multiple selections separated by commas.")
        print("Example: 2,6")

        selection = input("Selection: ").strip()

        if not selection:
            print("Please make a selection.")
            continue

        choices = [
            choice.strip()
            for choice in selection.split(",")
            if choice.strip()
        ]

        if any(choice not in DEVICE_OPTIONS for choice in choices):
            print("Invalid selection. Please choose options 1 through 7.")
            continue

        if "7" in choices and len(choices) > 1:
            print("'None' cannot be selected with another device.")
            continue

        if "7" in choices:
            return []

        devices = []

        for choice in choices:
            device = DEVICE_OPTIONS[choice]

            if device not in devices:
                devices.append(device)

        return devices


def collect_employee_information() -> Employee:
    """Collect new employee information from the user."""
    print()
    print("New Employee Information")
    print("------------------------")

    first_name = get_required_input("First name: ")
    middle_name = input("Middle name (optional): ").strip()
    last_name = get_required_input("Last name: ")
    job_title = get_required_input("Position: ")
    program = get_required_input("Program/Department: ")
    location = get_required_input("Location: ")
    supervisor = get_required_input("Supervisor: ")
    personal_email = get_required_input("Personal email: ")
    start_date = get_start_date()
    device_needs = get_device_needs()

    return Employee(
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        job_title=job_title,
        program=program,
        location=location,
        supervisor=supervisor,
        start_date=start_date,
        personal_email=personal_email,
        device_needs=device_needs,
    )


def main() -> None:
    """Run the New Employee IT Onboarding application."""
    configure_logging()

    logger.info("New Employee IT Onboarding application started.")

    print()
    print("SHORE EDUCATIONAL COLLABORATIVE")
    print("New Employee IT Onboarding")
    print("=" * 40)

    employee = collect_employee_information()

    tasks = generate_onboarding_tasks(employee)
    checklist_path = create_checklist(employee, tasks)

    logger.info(
        "Onboarding checklist created for %s.",
        employee.full_name,
    )

    print()
    print("=" * 40)
    print("Onboarding checklist created successfully.")
    print(f"Employee: {employee.full_name}")
    print(f"Position: {employee.job_title}")
    print(f"Program/Department: {employee.program}")

    if employee.device_needs:
        print(f"Devices: {', '.join(employee.device_needs)}")
    else:
        print("Devices: None")

    print(f"Checklist: {checklist_path}")


if __name__ == "__main__":
    main()