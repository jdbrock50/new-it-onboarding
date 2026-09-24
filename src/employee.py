"""Employee data model."""

from dataclasses import dataclass, field
from datetime import date

from src.config import GOOGLE_DOMAIN
from src.username import (
    generate_base_username,
    generate_middle_initial_username,
)


@dataclass
class Employee:
    """Represent a new Shore employee."""

    first_name: str
    last_name: str
    job_title: str
    program: str
    location: str
    supervisor: str
    start_date: date
    personal_email: str
    device_needs: list[str] = field(default_factory=list)
    middle_name: str = ""
    employee_type: str = "Full-Time"

    @property
    def full_name(self) -> str:
        """Return the employee's full name."""

        if self.middle_name:
            return (
                f"{self.first_name} "
                f"{self.middle_name} "
                f"{self.last_name}"
            )

        return f"{self.first_name} {self.last_name}"

    @property
    def proposed_username(self) -> str:
        """Generate the employee's proposed Shore username."""

        return generate_base_username(
            self.first_name,
            self.last_name,
        )

    @property
    def proposed_shore_email(self) -> str:
        """Generate the employee's proposed Shore email address."""

        return f"{self.proposed_username}@{GOOGLE_DOMAIN}"

    def username_with_middle_initial(self) -> str:
        """Generate an alternate username using the middle initial."""

        return generate_middle_initial_username(
            self.first_name,
            self.middle_name,
            self.last_name,
        )

    def username_with_number(self, number: int) -> str:
        """Generate an alternate username using a numeric suffix."""

        return f"{self.proposed_username}{number}"

    def __str__(self) -> str:
        """Return a readable employee description."""

        devices = (
            ", ".join(self.device_needs)
            if self.device_needs
            else "None"
        )

        return (
            f"{self.full_name} | "
            f"{self.job_title} | "
            f"{self.program} | "
            f"{self.location} | "
            f"Start: {self.start_date} | "
            f"Devices: {devices}"
        )