"""Store and retrieve employee onboarding history."""

import csv
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from src.config import GOOGLE_DOMAIN
from src.employee import Employee

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "onboarding_history.csv"

FIELDNAMES = [
    "created_at",
    "updated_at",
    "first_name",
    "middle_name",
    "last_name",
    "position",
    "program",
    "location",
    "supervisor",
    "start_date",
    "personal_email",
    "shore_email",
    "devices",
    "status",
    "onboarding_id",
]

VALID_STATUSES = {
    "Pending",
    "In Progress",
    "Completed",
    "Cancelled",
}


def current_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def save_onboarding_record(
    employee: Employee,
    shore_email: str | None = None,
) -> Path:
    """Save an employee onboarding record to CSV."""

    DATA_DIR.mkdir(exist_ok=True)

    file_exists = HISTORY_FILE.exists()
    timestamp = current_timestamp()

    record = {
        "created_at": timestamp,
        "updated_at": timestamp,
        "first_name": employee.first_name,
        "middle_name": employee.middle_name,
        "last_name": employee.last_name,
        "position": employee.job_title,
        "program": employee.program,
        "location": employee.location,
        "supervisor": employee.supervisor,
        "start_date": employee.start_date.isoformat(),
        "personal_email": employee.personal_email,
        "shore_email": shore_email or employee.proposed_shore_email,
        "devices": ", ".join(employee.device_needs),
        "status": "Pending",
        "onboarding_id": str(uuid4()),
    }

    if file_exists:
        ensure_current_schema()

    with HISTORY_FILE.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(record)

    return HISTORY_FILE


def load_onboarding_history() -> list[dict[str, str]]:
    """Load all onboarding history records."""

    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def write_onboarding_history(
    records: list[dict[str, str]],
) -> Path:
    """Write all onboarding records to the history file."""

    DATA_DIR.mkdir(exist_ok=True)

    with HISTORY_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
            extrasaction="ignore",
        )

        writer.writeheader()

        for record in records:
            complete_record = {
                field: record.get(field, "")
                for field in FIELDNAMES
            }

            writer.writerow(complete_record)

    return HISTORY_FILE


def ensure_current_schema() -> None:
    """Upgrade existing history records with stable onboarding IDs."""

    if not HISTORY_FILE.exists():
        return

    records = load_onboarding_history()

    with HISTORY_FILE.open(
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)
        existing_fields = reader.fieldnames or []

    needs_rewrite = existing_fields != FIELDNAMES
    existing_ids: set[str] = set()

    for record in records:
        if not record.get("updated_at"):
            record["updated_at"] = record.get("created_at", "")
            needs_rewrite = True

        onboarding_id = (record.get("onboarding_id") or "").strip()
        if not onboarding_id or onboarding_id in existing_ids:
            onboarding_id = str(uuid4())
            record["onboarding_id"] = onboarding_id
            needs_rewrite = True

        existing_ids.add(onboarding_id)

    if needs_rewrite:
        write_onboarding_history(records)


def get_existing_usernames() -> set[str]:
    """Return Shore usernames stored in onboarding history."""

    records = load_onboarding_history()
    usernames = set()

    domain_suffix = f"@{GOOGLE_DOMAIN}".lower()

    for record in records:
        shore_email = record.get(
            "shore_email",
            "",
        ).strip().lower()

        if not shore_email:
            continue

        if shore_email.endswith(domain_suffix):
            username = shore_email[
                : -len(domain_suffix)
            ]

            if username:
                usernames.add(username)

    return usernames


def get_pending_onboardings() -> list[dict[str, str]]:
    """Return onboarding records that are not finished."""

    records = load_onboarding_history()

    return [
        record
        for record in records
        if record.get("status") in {"Pending", "In Progress"}
    ]


def get_upcoming_hires(
    today: date | None = None,
) -> list[dict[str, str]]:
    """Return hires whose start date is today or later."""

    if today is None:
        today = datetime.now(UTC).date()

    records = load_onboarding_history()
    upcoming = []

    for record in records:
        start_date_value = record.get("start_date", "")

        try:
            start_date = date.fromisoformat(start_date_value)
        except ValueError:
            continue

        if (
            start_date >= today
            and record.get("status") != "Cancelled"
        ):
            upcoming.append(record)

    return sorted(
        upcoming,
        key=lambda record: record["start_date"],
    )


def update_onboarding_status(
    record_number: int,
    new_status: str,
) -> dict[str, str]:
    """Update the status of an onboarding record."""

    if new_status not in VALID_STATUSES:
        msg = f"Invalid onboarding status: {new_status}"
        raise ValueError(msg)

    ensure_current_schema()

    records = load_onboarding_history()

    if record_number < 1 or record_number > len(records):
        msg = "Invalid onboarding record number."
        raise IndexError(msg)

    record = records[record_number - 1]

    record["status"] = new_status
    record["updated_at"] = current_timestamp()

    write_onboarding_history(records)

    return record
