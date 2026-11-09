"""Read-only Google Workspace group recommendations for Shore onboarding.

This module evaluates the local, reviewed group catalog. It does not import
Google API clients, access the network, or change group memberships.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.employee import Employee
from src.group_catalog import DOMAIN, GroupPolicy, get_group, inherited_parent_emails


@dataclass(frozen=True)
class GroupRecommendation:
    """A catalog-backed recommendation or inherited membership explanation."""

    email: str
    name: str
    policy: GroupPolicy
    reason: str
    parent_emails: tuple[str, ...] = ()
    inherited: bool = False


@dataclass(frozen=True)
class GroupRecommendationResult:
    """Recommendations plus review notes for a single employee."""

    recommendations: tuple[GroupRecommendation, ...]
    review_notes: tuple[str, ...] = ()

    @property
    def automatic(self) -> tuple[GroupRecommendation, ...]:
        return tuple(r for r in self.recommendations if r.policy is GroupPolicy.AUTOMATIC)

    @property
    def needs_review(self) -> tuple[GroupRecommendation, ...]:
        return tuple(
            r for r in self.recommendations
            if r.policy in {GroupPolicy.IT_APPROVAL, GroupPolicy.MANUAL_REVIEW}
        )

    @property
    def inherited(self) -> tuple[GroupRecommendation, ...]:
        return tuple(r for r in self.recommendations if r.inherited)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def recommend_groups(employee: Employee) -> GroupRecommendationResult:
    """Recommend catalog-backed groups without making any directory changes.

    Unknown or excluded group addresses are not returned. Inherited groups
    are explanatory only and must never be provisioned directly.
    """
    recommendations: dict[str, GroupRecommendation] = {}
    notes: list[str] = []
    department = _normalized(employee.department)
    title = _normalized(employee.job_title)
    location = _normalized(employee.location)
    programs = {_normalized(program) for program in employee.all_programs}
    is_teacher = "teacher" in title
    is_para = "paraprofessional" in title or "paraeducator" in title or title.startswith("para")
    is_nurse = "nurs" in title
    is_therapist = any(word in title for word in ("therapist", "therapy", "slp", "speech-language pathologist"))
    is_manager = any(word in title for word in ("manager", "director", "supervisor"))
    is_coordinator = "program coordinator" in title
    adult = "adult" in department or any("adult" in program for program in programs)
    student_services = "student services" in department

    def add(local_part: str, reason: str) -> None:
        email = f"{local_part}@{DOMAIN}".casefold()
        group = get_group(email)
        if group is None or group.policy in {GroupPolicy.EXCLUDED, GroupPolicy.INHERITED}:
            return
        if email not in recommendations:
            recommendations[email] = GroupRecommendation(
                email=group.email,
                name=group.name,
                policy=group.policy,
                reason=reason,
                parent_emails=inherited_parent_emails(email),
            )

    add("shorestaffall", "All Shore employees")
    if "cambridge" in location:
        add("cambridge", "Cambridge work location")
    if student_services:
        add("ss_staff", "Student Services department")
    if department in {"it", "information technology", "technology", "technology services"}:
        add("it", "Information Technology department")
    if "facilit" in department:
        add("facilities", "Facilities department")
    if any(word in department for word in ("enrollment", "admissions")):
        add("enroll", "Enrollment or Admissions department")

    if is_teacher:
        add("teachers", "Teacher position")
        add("classroom_teachers", "Teacher position; classroom membership requires verification")
    if is_para:
        add("paraprofessionals", "Paraprofessional position")

    program_groups = {
        "sail": ("sail", "sailteam"),
        "bridges": ("bridges",),
        "soar": ("soar",),
        "inspire": ("inspireprogram", "inspire"),
    }
    for program, group_names in program_groups.items():
        if program in programs:
            for group_name in group_names:
                add(group_name, f"Assigned to {program.upper() if program == 'sail' else program.title()} program")

    for program, stem in (
        ("discovery", "discovery"),
        ("explorers", "explorers"),
        ("pathfinders", "pathfinders"),
    ):
        if program in programs:
            if is_teacher:
                add(f"{stem}teachers", f"Teacher assigned to {program.title()}")
            if is_para:
                add(f"{stem}paras", f"Paraprofessional assigned to {program.title()}")
            if program == "explorers":
                notes.append("Explorers E Team membership requires manual IT verification.")
            if program == "pathfinders":
                notes.append("Pathfinders Joann F Class membership requires manual IT selection.")

    if adult:
        add("adult-services-all-staff", "Adult Services department or program")
        location_groups = {
            "peabody": "adult-services-peabody",
            "chelsea": "adult-services-staff-chelsea",
            "woburn": "adult-services-staff-woburn",
        }
        matching_locations = [place for place in location_groups if place in location]
        for place in matching_locations:
            add(location_groups[place], f"Adult Services at {place.title()}")
            if is_therapist:
                add(f"adult-therapists-{place}", f"Adult Services therapist at {place.title()}")
            if is_manager:
                add(f"adult-services-managers-{place}", f"Adult Services manager at {place.title()}")
        if is_coordinator:
            add("adultprogramcoordinators", "Adult Services Program Coordinator")
        if is_nurse:
            if "peabody" in matching_locations:
                add("adult-nurses-peabody", "Adult Services nurse at Peabody")
            else:
                notes.append("Adult Services nursing membership requires manual IT review for this location.")
        if not matching_locations:
            notes.append("Adult Services location-specific group assignment requires IT review.")

    if student_services:
        if is_nurse:
            add("ss_nursing", "Student Services nursing position")
        if is_therapist:
            add("therapist", "Student Services therapist position")

    # Include only known, explicitly cataloged inherited groups for explanation.
    inherited: dict[str, GroupRecommendation] = {}
    for direct in recommendations.values():
        for parent_email in direct.parent_emails:
            parent = get_group(parent_email)
            if parent is None or parent.policy is not GroupPolicy.INHERITED:
                continue
            inherited[parent.email] = GroupRecommendation(
                email=parent.email,
                name=parent.name,
                policy=parent.policy,
                reason=f"Inherited through {direct.email}; do not add directly",
                parent_emails=inherited_parent_emails(parent.email),
                inherited=True,
            )

    return GroupRecommendationResult(
        recommendations=tuple(sorted((*recommendations.values(), *inherited.values()), key=lambda r: r.email)),
        review_notes=tuple(dict.fromkeys(notes)),
    )
