
"""IT onboarding checklist generation."""

from dataclasses import dataclass

from src.config import (
    DEVICE_MANAGEMENT,
    SECURITY_REQUIREMENTS,
    STAFF_WIFI_SSID,
    STANDARD_SOFTWARE,
)
from src.employee import Employee


@dataclass
class OnboardingTask:
    """A single IT onboarding task."""

    category: str
    description: str
    required: bool = True
    completed: bool = False


def _create_device_tasks(device: str) -> list[OnboardingTask]:
    """Create onboarding tasks for a specific device."""

    tasks = [
        OnboardingTask(
            category="Device",
            description=f"Assign {device}",
        ),
        OnboardingTask(
            category="Device",
            description=f"Record asset/serial number for {device}",
        ),
    ]

    management_platform = DEVICE_MANAGEMENT.get(device)

    if management_platform == "Manual":
        tasks.append(
            OnboardingTask(
                category="Device",
                description=f"Configure {device} device manually",
            )
        )
    elif management_platform:
        tasks.append(
            OnboardingTask(
                category="Device",
                description=(
                    f"Enroll/configure {device} using "
                    f"{management_platform}"
                ),
            )
        )
    else:
        tasks.append(
            OnboardingTask(
                category="Needs Review",
                description=f"Determine management platform for {device}",
            )
        )

    return tasks


def generate_onboarding_tasks(
    employee: Employee,
    shore_email: str | None = None,
) -> list[OnboardingTask]:
    """Generate IT onboarding tasks using the resolved Shore email."""

    resolved_email = (
        shore_email
        if shore_email is not None
        else employee.proposed_shore_email
    )

    resolved_username = resolved_email.split("@", maxsplit=1)[0]

    tasks = [
        OnboardingTask(
            category="Accounts & Access",
            description=(
                "Verify proposed Shore username "
                f"({resolved_username}) is available"
            ),
        ),
        OnboardingTask(
            category="Accounts & Access",
            description=(
                f"Create {resolved_email} "
                "Google Workspace account"
            ),
        ),
        OnboardingTask(
            category="Accounts & Access",
            description="Enroll user in multi-factor authentication",
        ),
        OnboardingTask(
            category="Needs Review",
            description="Determine appropriate Google Groups",
        ),
    ]

    for device in employee.device_needs:
        tasks.extend(_create_device_tasks(device))

    tasks.append(
        OnboardingTask(
            category="Network",
            description=f"Configure access to {STAFF_WIFI_SSID} Wi-Fi",
        )
    )

    tasks.append(
        OnboardingTask(
            category="Printing",
            description="Configure Coreza Printing",
        )
    )

    for software in STANDARD_SOFTWARE:
        tasks.append(
            OnboardingTask(
                category="Software",
                description=f"Configure {software}",
            )
        )

    for requirement in SECURITY_REQUIREMENTS:
        tasks.append(
            OnboardingTask(
                category="Security",
                description=requirement,
            )
        )

    tasks.extend(
        [
            OnboardingTask(
                category="Needs Review",
                description="Determine SIS access requirements",
            ),
            OnboardingTask(
                category="Needs Review",
                description="Determine whether a phone extension is required",
            ),
        ]
    )

    tasks.extend(
        [
            OnboardingTask(
                category="Final Verification",
                description="Verify employee can sign in",
            ),
            OnboardingTask(
                category="Final Verification",
                description="Verify Shore email access",
            ),
            OnboardingTask(
                category="Final Verification",
                description="Verify required applications",
            ),
        ]
    )

    tasks.extend(
        [
            OnboardingTask(
                category="Employee Handoff",
                description=f"Provide {resolved_email}",
            ),
            OnboardingTask(
                category="Employee Handoff",
                description="Provide initial sign-in instructions",
            ),
            OnboardingTask(
                category="Employee Handoff",
                description="Confirm MFA enrollment with employee",
            ),
            OnboardingTask(
                category="Employee Handoff",
                description="Provide assigned equipment",
            ),
            OnboardingTask(
                category="Employee Handoff",
                description="Provide IT support contact information",
            ),
        ]
    )

    return tasks
