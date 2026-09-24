"""Generate onboarding checklist files."""

from collections import defaultdict
from pathlib import Path

from src.employee import Employee
from src.onboarding import OnboardingTask

OUTPUT_DIR = Path("output")

CATEGORY_ORDER = [
    "Accounts & Access",
    "Device",
    "Network",
    "Printing",
    "Software",
    "Security",
    "Needs Review",
    "Final Verification",
    "Employee Handoff",
]


def create_checklist(
    employee: Employee,
    tasks: list[OnboardingTask],
) -> Path:
    """Create a text onboarding checklist for an employee."""

    OUTPUT_DIR.mkdir(exist_ok=True)

    filename = (
        f"{employee.last_name.lower()}_"
        f"{employee.first_name.lower()}_onboarding.txt"
    )

    output_path = OUTPUT_DIR / filename

    lines = [
        "SHORE EDUCATIONAL COLLABORATIVE",
        "NEW EMPLOYEE IT ONBOARDING",
        "=" * 40,
        "",
        f"Employee: {employee.full_name}",
        f"Position: {employee.job_title}",
        f"Program/Department: {employee.program}",
        f"Location: {employee.location}",
        f"Supervisor: {employee.supervisor}",
        f"Start Date: {employee.start_date}",
        f"Personal Email: {employee.personal_email}",
        f"Proposed Shore Email: {employee.proposed_shore_email}",
        f"Device Needs: {', '.join(employee.device_needs) or 'None'}",
        "",
    ]

    grouped_tasks: dict[str, list[OnboardingTask]] = defaultdict(list)

    for task in tasks:
        grouped_tasks[task.category].append(task)

    for category in CATEGORY_ORDER:
        category_tasks = grouped_tasks.get(category)

        if not category_tasks:
            continue

        lines.extend(
            [
                category.upper(),
                "-" * len(category),
            ]
        )

        for task in category_tasks:
            checkbox = "[X]" if task.completed else "[ ]"
            lines.append(f"{checkbox} {task.description}")

        lines.append("")

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return output_path