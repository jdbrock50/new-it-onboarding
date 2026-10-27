"""Console interface for the Shore IT Onboarding application."""

from datetime import date

from googleapiclient.errors import HttpError

from src.checklist import create_checklist
from src.config import GOOGLE_DOMAIN
from src.employee import Employee
from src.google_workspace import (
    get_workspace_group_usernames,
    get_workspace_usernames,
)
from src.history import (
    VALID_STATUSES,
    get_existing_usernames,
    get_pending_onboardings,
    get_upcoming_hires,
    load_onboarding_history,
    save_onboarding_record,
    update_onboarding_status,
)
from src.onboarding import generate_onboarding_tasks
from src.username import resolve_username

DEVICE_OPTIONS = {
    "1": "Chromebook",
    "2": "Windows",
    "3": "MacBook",
    "4": "iPhone",
    "5": "iPad",
    "6": "Android",
    "7": "None",
}

STATUS_OPTIONS = {
    "1": "Pending",
    "2": "In Progress",
    "3": "Completed",
    "4": "Cancelled",
}


def display_header() -> None:
    """Display the application header."""
    print()
    print("=" * 60)
    print("SHORE EDUCATIONAL COLLABORATIVE")
    print("IT ONBOARDING")
    print("=" * 60)


def display_menu() -> None:
    """Display the main application menu."""
    print()
    print("1. Create New Onboarding")
    print("2. View Pending Onboardings")
    print("3. View Upcoming Hires")
    print("4. View Onboarding History")
    print("5. Update Onboarding Status")
    print("6. Exit")
    print()


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
        print("-" * 30)
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
            print(
                "Invalid selection. "
                "Please choose options 1 through 7."
            )
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
    """Collect new employee information."""
    print()
    print("CREATE NEW ONBOARDING")
    print("=" * 60)
    print()

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


def resolve_employee_email(
    employee: Employee,
) -> tuple[str, str]:
    """Resolve a username using local and live directory records."""
    existing_usernames = get_existing_usernames()

    print()
    print("Checking Shore Google Workspace directory...")

    verification_complete = True
    for label, lookup in (
        ("Users", get_workspace_usernames),
        ("Groups", get_workspace_group_usernames),
    ):
        try:
            reserved = lookup()
        except (HttpError, OSError, ValueError) as exc:
            verification_complete = False
            print(f"WARNING: Google Workspace {label} lookup failed.")
            print(f"Error type: {type(exc).__name__}")
        else:
            existing_usernames.update(reserved)
            print(f"{label} directory addresses checked: {len(reserved)}")

    if verification_complete:
        print("Google Workspace directory check successful.")
        print(f"Directory addresses checked: {len(existing_usernames)}")
    else:
        print("WARNING: Google Workspace verification failed.")
        print("Only successful lookups and local reservations were checked.")
        print("Username availability is NOT verified.")

    username = resolve_username(
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        last_name=employee.last_name,
        existing_usernames=existing_usernames,
    )

    return username, f"{username}@{GOOGLE_DOMAIN}"


def create_new_onboarding() -> None:
    """Create a new employee onboarding."""
    employee = collect_employee_information()
    username, shore_email = resolve_employee_email(employee)

    base_username = employee.proposed_username
    collision_detected = username != base_username

    print()
    print("ONBOARDING SUMMARY")
    print("-" * 60)
    print(f"Employee: {employee.full_name}")
    print(f"Position: {employee.job_title}")
    print(f"Program/Department: {employee.program}")
    print(f"Location: {employee.location}")
    print(f"Supervisor: {employee.supervisor}")
    print(f"Start Date: {employee.start_date}")
    print(f"Personal Email: {employee.personal_email}")

    if collision_detected:
        print(f"Original Username: {base_username}")
        print("Username Collision: Yes")

    print(f"Resolved Username: {username}")
    print(f"Shore Email: {shore_email}")

    if employee.device_needs:
        print(f"Devices: {', '.join(employee.device_needs)}")
    else:
        print("Devices: None")

    print()
    confirmation = input(
        "Create this onboarding? (Y/N): "
    ).strip().lower()

    if confirmation not in {"y", "yes"}:
        print()
        print("Onboarding cancelled.")
        return

    tasks = generate_onboarding_tasks(
        employee,
        shore_email=shore_email,
    )

    checklist_path = create_checklist(
        employee,
        tasks,
        shore_email=shore_email,
    )

    history_path = save_onboarding_record(
        employee,
        shore_email=shore_email,
    )

    print()
    print("Onboarding created successfully.")
    print(f"Shore Email: {shore_email}")
    print(f"Checklist: {checklist_path}")
    print(f"History: {history_path}")


def get_record_full_name(record: dict[str, str]) -> str:
    """Return the full name stored in a history record."""
    name_parts = [
        record.get("first_name", "").strip(),
        record.get("middle_name", "").strip(),
        record.get("last_name", "").strip(),
    ]
    return " ".join(part for part in name_parts if part)


def display_records(records: list[dict[str, str]]) -> None:
    """Display onboarding records in a readable format."""
    if not records:
        print()
        print("No onboarding records found.")
        return

    print()
    for number, record in enumerate(records, start=1):
        full_name = get_record_full_name(record)
        print(f"{number}. {full_name}")
        print(f"   Position: {record.get('position', '')}")
        print(f"   Program: {record.get('program', '')}")
        print(f"   Location: {record.get('location', '')}")
        print(f"   Start Date: {record.get('start_date', '')}")
        print(f"   Shore Email: {record.get('shore_email', '')}")
        print(f"   Devices: {record.get('devices', '') or 'None'}")
        print(f"   Status: {record.get('status', '')}")
        print()


def view_pending_onboardings() -> None:
    """Display unfinished onboarding records."""
    print()
    print("PENDING ONBOARDINGS")
    print("=" * 60)
    display_records(get_pending_onboardings())


def view_upcoming_hires() -> None:
    """Display upcoming employee start dates."""
    print()
    print("UPCOMING HIRES")
    print("=" * 60)
    display_records(get_upcoming_hires())


def view_onboarding_history() -> None:
    """Display all onboarding history."""
    print()
    print("ONBOARDING HISTORY")
    print("=" * 60)
    display_records(load_onboarding_history())


def select_history_record(
    records: list[dict[str, str]],
) -> int | None:
    """Prompt the user to select an onboarding record."""
    while True:
        selection = input(
            "Select employee number or C to cancel: "
        ).strip()

        if selection.lower() == "c":
            return None

        try:
            record_number = int(selection)
        except ValueError:
            print("Please enter a valid employee number.")
            continue

        if record_number < 1 or record_number > len(records):
            print("Employee number is out of range.")
            continue

        return record_number


def select_new_status() -> str | None:
    """Prompt the user to select a new status."""
    print()
    print("1. Pending")
    print("2. In Progress")
    print("3. Completed")
    print("4. Cancelled")
    print("5. Cancel")
    print()

    while True:
        selection = input("Select new status: ").strip()

        if selection == "5":
            return None

        status = STATUS_OPTIONS.get(selection)
        if status in VALID_STATUSES:
            return status

        print("Please choose an option from 1 through 5.")


def update_status() -> None:
    """Allow the user to update an onboarding status."""
    print()
    print("UPDATE ONBOARDING STATUS")
    print("=" * 60)

    records = load_onboarding_history()
    if not records:
        print()
        print("No onboarding records found.")
        return

    display_records(records)
    record_number = select_history_record(records)

    if record_number is None:
        print()
        print("Status update cancelled.")
        return

    selected_record = records[record_number - 1]
    full_name = get_record_full_name(selected_record)

    print()
    print("-" * 60)
    print(f"Employee: {full_name}")
    print(
        "Current Status: "
        f"{selected_record.get('status', '')}"
    )

    new_status = select_new_status()
    if new_status is None:
        print()
        print("Status update cancelled.")
        return

    print()
    confirmation = input(
        f"Change status to '{new_status}'? (Y/N): "
    ).strip().lower()

    if confirmation not in {"y", "yes"}:
        print()
        print("Status update cancelled.")
        return

    updated_record = update_onboarding_status(
        record_number,
        new_status,
    )

    print()
    print("Onboarding status updated successfully.")
    print(f"Employee: {get_record_full_name(updated_record)}")
    print(f"Status: {updated_record['status']}")
    print(f"Updated: {updated_record['updated_at']}")


def run_console() -> None:
    """Run the Shore IT Onboarding console."""
    while True:
        display_header()
        display_menu()

        selection = input("Select an option: ").strip()

        if selection == "1":
            create_new_onboarding()
        elif selection == "2":
            view_pending_onboardings()
        elif selection == "3":
            view_upcoming_hires()
        elif selection == "4":
            view_onboarding_history()
        elif selection == "5":
            update_status()
        elif selection == "6":
            print()
            print("Exiting Shore IT Onboarding.")
            print()
            break
        else:
            print()
            print("Invalid selection. Please choose 1 through 6.")

        if selection in {"1", "2", "3", "4", "5"}:
            print()
            input("Press Enter to return to the main menu...")