"""Console interface for the Shore IT Onboarding application."""

from datetime import UTC, date, datetime
from pathlib import Path

from googleapiclient.errors import HttpError

from src.audit import AuditWriteError, load_audit_events, record_audit_event
from src.audit_export import export_audit_events_csv, export_audit_summary_csv
from src.audit_filters import filter_audit_events
from src.audit_summary import summarize_audit_events
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
from src.progress_dashboard import build_progress_dashboard
from src.task_progress import (
    apply_task_progress,
    calculate_task_progress,
    set_task_completed,
)
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
    print("6. View Audit Log")
    print("7. View Audit Summary")
    print("8. Export Audit Events to CSV")
    print("9. Export Audit Summary to CSV")
    print("10. Manage Onboarding Checklist")
    print("11. View Onboarding Progress Dashboard")
    print("12. Exit")
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


def _resolve_employee_email_with_details(
    employee: Employee,
) -> tuple[str, str, bool, dict[str, str]]:
    """Resolve an email and return each directory lookup's result."""
    existing_usernames = get_existing_usernames()

    print()
    print("Checking Shore Google Workspace directory...")

    verification_complete = True
    lookup_results: dict[str, str] = {}
    for label, lookup in (
        ("Users", get_workspace_usernames),
        ("Groups", get_workspace_group_usernames),
    ):
        try:
            reserved = lookup()
        except (HttpError, OSError, ValueError) as exc:
            verification_complete = False
            lookup_results[label.lower()] = "failed"
            print(f"WARNING: Google Workspace {label} lookup failed.")
            print(f"Error type: {type(exc).__name__}")
        else:
            lookup_results[label.lower()] = "success"
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

    return (
        username,
        f"{username}@{GOOGLE_DOMAIN}",
        verification_complete,
        lookup_results,
    )


def _resolve_employee_email_with_verification(
    employee: Employee,
) -> tuple[str, str, bool]:
    """Preserve the existing three-value verification interface."""
    username, email, verified, _results = _resolve_employee_email_with_details(
        employee
    )
    return username, email, verified


def resolve_employee_email(employee: Employee) -> tuple[str, str]:
    """Return a proposed username and email, preserving the public API."""
    username, email, _verified = _resolve_employee_email_with_verification(employee)
    return username, email


def confirm_unverified_email(shore_email: str) -> bool:
    """Require explicit approval when directory verification is incomplete."""
    print()
    print("WARNING: GOOGLE WORKSPACE VERIFICATION INCOMPLETE")
    print("-" * 60)
    print("The proposed Shore email was NOT fully verified.")
    print(f"Proposed Email: {shore_email}")
    print("Creating this onboarding could result in a duplicate address.")
    confirmation = input(
        "Proceed with an UNVERIFIED email? (Y/N): "
    ).strip().lower()
    return confirmation in {"y", "yes"}


def _record_required_audit_event(
    event_type: str,
    *,
    shore_email: str,
    details: dict[str, object],
) -> bool:
    """Record an event, stopping the current workflow on audit failure."""
    try:
        record_audit_event(
            event_type,
            employee_email=shore_email,
            details=details,
        )
    except AuditWriteError:
        print()
        print(f"ERROR: {event_type} audit could not be saved.")
        print("Onboarding stopped because audit logging is unavailable.")
        return False
    return True


def create_new_onboarding() -> None:
    """Create a new employee onboarding with required audit checkpoints."""
    employee = collect_employee_information()
    username, shore_email, verified, lookup_results = (
        _resolve_employee_email_with_details(employee)
    )

    if not _record_required_audit_event(
        "verification_completed",
        shore_email=shore_email,
        details={
            "users_lookup": lookup_results["users"],
            "groups_lookup": lookup_results["groups"],
            "verification_complete": verified,
            "original_username": employee.proposed_username,
            "resolved_username": username,
            "username_collision": username != employee.proposed_username,
        },
    ):
        print("No checklist or history was created.")
        return

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

    administrator_name = None
    approval_reason = None
    if not verified:
        if not confirm_unverified_email(shore_email):
            if not _record_required_audit_event(
                "override_declined",
                shore_email=shore_email,
                details={"verification_complete": False},
            ):
                return
            if not _record_required_audit_event(
                "onboarding_cancelled",
                shore_email=shore_email,
                details={
                    "stage": "unverified_email_override",
                    "verification_complete": False,
                },
            ):
                return
            print()
            print("Onboarding cancelled. No records were created.")
            return

        administrator_name = get_required_input("Approving administrator name: ")
        approval_reason = get_required_input("Override approval reason: ")
        if not _record_required_audit_event(
            "override_approved",
            shore_email=shore_email,
            details={
                "administrator_name": administrator_name,
                "approval_reason": approval_reason,
                "verification_complete": False,
            },
        ):
            return

    print()
    confirmation = input("Create this onboarding? (Y/N): ").strip().lower()
    if confirmation not in {"y", "yes"}:
        if not _record_required_audit_event(
            "onboarding_cancelled",
            shore_email=shore_email,
            details={
                "stage": "final_confirmation",
                "verification_complete": verified,
                "override_approved": not verified,
            },
        ):
            return
        print()
        print("Onboarding cancelled.")
        return

    # A durable authorization event must exist before creating any records.
    if not _record_required_audit_event(
        "onboarding_creation_authorized",
        shore_email=shore_email,
        details={
            "verification_complete": verified,
            "override_approved": not verified,
            "administrator_name": administrator_name,
        },
    ):
        return

    tasks = generate_onboarding_tasks(employee, shore_email=shore_email)
    checklist_path = create_checklist(
        employee,
        tasks,
        shore_email=shore_email,
    )
    history_path = save_onboarding_record(
        employee,
        shore_email=shore_email,
    )

    # This event follows the side effects: it must never claim success early.
    if not _record_required_audit_event(
        "onboarding_created",
        shore_email=shore_email,
        details={
            "verification_complete": verified,
            "override_approved": not verified,
            "administrator_name": administrator_name,
            "checklist_path": str(checklist_path),
            "history_path": str(history_path),
        },
    ):
        print("WARNING: Checklist/history may already exist; review them manually.")
        return

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


def view_audit_log() -> None:
    """Display recent audit events with optional email, type, and date filters."""
    print()
    print("AUDIT LOG — 20 MOST RECENT EVENTS")
    print("=" * 60)

    try:
        events = load_audit_events()
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to read audit log ({type(exc).__name__}).")
        return

    if not events:
        print("No audit events found.")
        return

    print()
    print("Search audit events (leave all fields blank to show all).")
    email_query = input("Employee email contains (optional): ").strip()
    type_query = input("Event type (optional): ").strip()
    start_query = input("Start date (YYYY-MM-DD, optional): ").strip()
    end_query = input("End date (YYYY-MM-DD, optional): ").strip()
    try:
        matching_events = filter_audit_events(
            events,
            employee_email=email_query,
            event_type=type_query,
            start_date=start_query,
            end_date=end_query,
        )
    except ValueError as exc:
        print(f"Invalid audit search: {exc}")
        return

    if not matching_events:
        print("No matching audit events found.")
        return

    print(f"Matching events: {len(matching_events)}")
    print("Showing up to 20 most recent matching events.")
    for number, event in enumerate(reversed(matching_events[-20:]), start=1):
        print(f"{number}. {event.get('timestamp', 'Unknown timestamp')}")
        print(f"   Event: {event.get('event_type', 'Unknown event')}")
        print(f"   Employee: {event.get('employee_email', 'Unknown email')}")
        print()



def view_audit_summary() -> None:
    """Display read-only summary counts from recorded onboarding audit events."""
    print()
    print("AUDIT SUMMARY REPORT")
    print("=" * 60)

    try:
        events = load_audit_events()
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to read audit log ({type(exc).__name__}).")
        return

    if not events:
        print("No audit events found.")
        return

    summary = summarize_audit_events(events)
    print(f"Total audit events: {summary['total_events']}")
    print(f"Unique employee emails: {summary['unique_employee_emails']}")
    print()
    print("EVENT COUNTS BY TYPE")
    print("-" * 60)
    for event_type, count in summary["events_by_type"].items():
        print(f"{event_type}: {count}")

    outcomes = summary["verification_outcomes"]
    print()
    print("GOOGLE WORKSPACE VERIFICATION OUTCOMES")
    print("-" * 60)
    print(f"Successful: {outcomes['successful']}")
    print(f"Incomplete: {outcomes['incomplete']}")
    print(f"Unknown: {outcomes['unknown']}")

    print()
    print("ADMINISTRATOR OVERRIDES")
    print("-" * 60)
    print(f"Approved: {summary['overrides_approved']}")
    print(f"Declined: {summary['overrides_declined']}")

    print()
    print("ONBOARDING OUTCOMES")
    print("-" * 60)
    print(f"Created: {summary['onboardings_created']}")
    print(f"Cancelled: {summary['onboardings_cancelled']}")



def _audit_report_path(report_type: str) -> Path:
    """Choose a timestamped report path without replacing an existing file."""
    folder = Path("reports")
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"audit_{report_type}_{stamp}.csv"


def export_audit_events_report() -> None:
    """Export audit events, optionally filtered by email, type, and dates."""
    print()
    print("EXPORT AUDIT EVENTS TO CSV")
    print("=" * 60)
    try:
        events = load_audit_events()
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to read audit log ({type(exc).__name__}).")
        return
    if not events:
        print("No audit events found. No CSV was created.")
        return

    print("Filter events (leave all fields blank to export all events).")
    email_query = input("Employee email contains (optional): ").strip()
    type_query = input("Event type (optional): ").strip()
    start_query = input("Start date (YYYY-MM-DD, optional): ").strip()
    end_query = input("End date (YYYY-MM-DD, optional): ").strip()
    try:
        matching = filter_audit_events(
            events,
            employee_email=email_query,
            event_type=type_query,
            start_date=start_query,
            end_date=end_query,
        )
    except ValueError as exc:
        print(f"Invalid audit search: {exc}")
        return
    if not matching:
        print("No matching audit events found. No CSV was created.")
        return
    try:
        path = export_audit_events_csv(matching, _audit_report_path("events"))
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to export audit events ({type(exc).__name__}).")
        return
    print(f"Exported {len(matching)} audit events to: {path}")


def export_audit_summary_report() -> None:
    """Export aggregated audit statistics to CSV without changing the log."""
    print()
    print("EXPORT AUDIT SUMMARY TO CSV")
    print("=" * 60)
    try:
        events = load_audit_events()
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to read audit log ({type(exc).__name__}).")
        return
    if not events:
        print("No audit events found. No CSV was created.")
        return
    try:
        summary = summarize_audit_events(events)
        path = export_audit_summary_csv(summary, _audit_report_path("summary"))
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to export audit summary ({type(exc).__name__}).")
        return
    print(f"Exported summary of {len(events)} audit events to: {path}")


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


def employee_from_history(record: dict[str, str]) -> Employee:
    """Reconstruct an employee from an existing history row."""
    devices = [item.strip() for item in record.get("devices", "").split(",")]
    return Employee(
        first_name=record["first_name"],
        middle_name=record.get("middle_name", ""),
        last_name=record["last_name"],
        job_title=record["position"],
        program=record["program"],
        location=record["location"],
        supervisor=record["supervisor"],
        start_date=date.fromisoformat(record["start_date"]),
        personal_email=record["personal_email"],
        device_needs=[item for item in devices if item and item.lower() != "none"],
    )


def manage_onboarding_checklist() -> None:
    """Manage saved task states without changing overall onboarding status."""
    print()
    print("MANAGE ONBOARDING CHECKLIST")
    print("=" * 60)
    try:
        records = load_onboarding_history()
    except (OSError, ValueError) as exc:
        print(f"Unable to read onboarding history ({type(exc).__name__}).")
        return
    if not records:
        print("No onboarding records found.")
        return

    display_records(records)
    number = select_history_record(records)
    if number is None:
        print("Checklist management cancelled.")
        return

    record = records[number - 1]
    onboarding_id = record.get("onboarding_id", "").strip()
    if not onboarding_id:
        print("This record has no onboarding ID. No changes were made.")
        return
    try:
        employee = employee_from_history(record)
        tasks = generate_onboarding_tasks(
            employee, shore_email=record.get("shore_email", "")
        )
        apply_task_progress(onboarding_id, tasks)
    except (KeyError, ValueError, TypeError, OSError) as exc:
        print(f"Unable to load checklist ({type(exc).__name__}).")
        return

    while True:
        progress = calculate_task_progress(tasks)
        print()
        print(f"Employee: {get_record_full_name(record)}")
        print(f"Progress: {progress['completed']}/{progress['total']} "
              f"({progress['percentage']}%)")
        print("Overall onboarding status: " + record.get("status", ""))
        print("-" * 60)
        for index, task in enumerate(tasks, start=1):
            mark = "X" if task.completed else " "
            print(f"{index}. [{mark}] {task.category}: {task.description}")
        print()
        choice = input("Task number to toggle, or C to return: ").strip()
        if choice.lower() == "c":
            return
        try:
            index = int(choice)
        except ValueError:
            print("Please enter a valid task number.")
            continue
        if index < 1 or index > len(tasks):
            print("Task number is out of range.")
            continue

        task = tasks[index - 1]
        new_state = not task.completed
        label = "complete" if new_state else "pending"
        confirmation = input(
            f"Mark '{task.description}' as {label}? (Y/N): "
        ).strip().lower()
        if confirmation not in {"y", "yes"}:
            print("No changes made.")
            continue

        # Authorization audit is written before changing persisted task state.
        if not _record_required_audit_event(
            "task_progress_change_authorized",
            shore_email=record.get("shore_email", ""),
            details={
                "onboarding_id": onboarding_id,
                "task_category": task.category,
                "task_description": task.description,
                "previous_completed": task.completed,
                "requested_completed": new_state,
            },
        ):
            return
        try:
            set_task_completed(onboarding_id, task, new_state)
        except (OSError, ValueError, TypeError) as exc:
            print(f"Unable to save task progress ({type(exc).__name__}).")
            print("The authorization was audited, but the change was not saved.")
            return
        task.completed = new_state
        print(f"Task marked {label}.")
        try:
            path = create_checklist(
                employee, tasks, shore_email=record.get("shore_email", "")
            )
        except (OSError, ValueError) as exc:
            print(f"WARNING: Text checklist could not be updated ({type(exc).__name__}).")
            print("Progress was saved. Reopen this menu to retry later.")
        else:
            print(f"Updated checklist: {path}")


def view_onboarding_progress_dashboard() -> None:
    """Display read-only task completion and onboarding status totals."""
    print()
    print("ONBOARDING PROGRESS DASHBOARD")
    print("=" * 60)
    try:
        records = load_onboarding_history()
        report = build_progress_dashboard(records)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Unable to build progress dashboard ({type(exc).__name__}).")
        return

    if not report["rows"]:
        print("No onboarding records found.")
        return

    for number, row in enumerate(report["rows"], start=1):
        print()
        print(f"{number}. {row['employee']}")
        print(f"   Shore Email: {row['shore_email'] or 'Not assigned'}")
        print(f"   Overall Status: {row['status']}")
        if row["error"]:
            print(f"   Progress unavailable: {row['error']}")
        else:
            print(
                f"   Checklist Progress: {row['completed']}/{row['total']} "
                f"({row['percentage']}%)"
            )

    print()
    print("DASHBOARD SUMMARY")
    print("-" * 60)
    print(f"Total onboardings: {report['total_onboardings']}")
    print(f"Completed checklists: {report['completed_checklists']}")
    print(f"Incomplete checklists: {report['incomplete_checklists']}")
    print(f"Records with errors: {report['errors']}")
    print("Overall onboarding statuses:")
    for status, count in sorted(report["status_counts"].items()):
        print(f"   {status}: {count}")


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
            view_audit_log()
        elif selection == "7":
            view_audit_summary()
        elif selection == "8":
            export_audit_events_report()
        elif selection == "9":
            export_audit_summary_report()
        elif selection == "10":
            manage_onboarding_checklist()
        elif selection == "11":
            view_onboarding_progress_dashboard()
        elif selection == "12":
            print()
            print("Exiting Shore IT Onboarding.")
            print()
            break
        else:
            print()
            print("Invalid selection. Please choose 1 through 12.")

        if selection in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"}:
            print()
            input("Press Enter to return to the main menu...")