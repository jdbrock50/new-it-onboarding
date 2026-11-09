"""Shore Google Workspace group catalog and conservative assignment policies.

This module is offline and read-only. It does not call Google Workspace APIs.
Group addresses are identifiers, not evidence of actual current membership.
"""

from dataclasses import dataclass
from enum import StrEnum


class GroupPolicy(StrEnum):
    AUTOMATIC = "automatic"
    IT_APPROVAL = "it_approval"
    MANUAL_REVIEW = "manual_review"
    INHERITED = "inherited"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class GroupDefinition:
    name: str
    email: str
    policy: GroupPolicy = GroupPolicy.MANUAL_REVIEW
    parent_emails: tuple[str, ...] = ()


DOMAIN = "shorecollaborative.org"

# Catalog entries use the verified export's exact group names and addresses.
# Unclassified entries default to MANUAL_REVIEW (fail closed).
_GROUPS = """
Adult Nurses Peabody|adult-nurses-peabody
Adult Nurses All|adult-nursing
Adult Services Staff All|adult-services-all-staff
Adult Services DSS2 Peabody|adult-services-dss2-peabody
Adult Services Managers Chelsea|adult-services-managers-chelsea
Adult Services Managers Peabody|adult-services-managers-peabody
Adult Services Managers Woburn|adult-services-managers-woburn
Adult Services Staff Peabody|adult-services-peabody
Adult Services Staff Chelsea|adult-services-staff-chelsea
Adult Services Staff Woburn|adult-services-staff-woburn
Adult Therapists Chelsea|adult-therapists-chelsea
Adult Therapists Peabody|adult-therapists-peabody
Adult Therapists Woburn|adult-therapists-woburn
Adult Managers|adult_managers
Adult Therapists All|adult_therapists
Adult Program Coordinators|adultprogramcoordinators
AS Status Change|as-status-change
ASL - January 2026|asl---january-2026
ASL - March, 2026|asl---march-2026
ASL - May, 2026|asl---may-2026
ASL - Mini Session|asl---mini-session
ASL - Summer 2026|asl---summer-2026
ASL Class Fall 2025|asl-class-fall-2025
Basketball|basketball
Board of Directors|boardofdirectors
Bridges|bridges
BurgayTeam|burgayteam
Cambridge|cambridge
CCFR|ccfr-group
Chelsea Remote|chelsearemote
Classroom Teachers|classroom_teachers
Discovery Paras|discoveryparas
Discovery Teachers|discoveryteachers
Division Directors|division_directors
Emergency|emergency
Enroll|enroll
Explorers E Team|explorerseteam
Explorers Paras|explorersparas
Explorers Teachers|explorersteachers
Facilities|facilities
Finance and Admin Staff|finance-and-administrative-staff
Home Trainers|home_trainers
Inspire SY26-27|inspire
Inspire|inspireprogram
IT|it
IT Tools|ittools
SendAll|ksgroup
Leadership Team|leadership-team
Lunch Group|lunchgroup
Med Web|med_web
Medicaid Billing Group|medicaidbilling
Nursing All|nursing_all
Operational Group|operational-group
Paraprofessionals|paraprofessionals
Pathfinders Joann F Class|pathfinders-joann-f-class
Pathfinders Paras|pathfindersparas
Pathfinders Teachers|pathfindersteachers
Professionals|professionals
Safety Care Trainers|safety-care-trainers
SAIL|sail
SAIL Team|sailteam
Shore ASL Learning Community (Fall)|shore-asl-learning-community-fall
Shore ASL Learning Community (Winter)|shore-asl-learning-community-winter
AppSheet|shoreappsheet
Shore Staff All|shorestaffall
Soar|soar
SS Nursing|ss_nursing
ss_staff|ss_staff
SS Counselors|sscounselor
SS Nurses eFax|ssnursesefax
Staff|staff
Summer Enrichment|summerenrichment
Teachers|teachers
Temp Shore Staff All|tempshorestaffall
Termination|termination
testforgene|testforgene
SS Therapists|therapist
""".strip()

_AUTOMATIC = frozenset({
    "adult-nurses-peabody", "adult-services-all-staff",
    "adult-services-managers-chelsea", "adult-services-managers-peabody", "adult-services-managers-woburn",
    "adult-services-peabody", "adult-services-staff-chelsea", "adult-services-staff-woburn",
    "adult-therapists-chelsea", "adult-therapists-peabody", "adult-therapists-woburn",
    "adultprogramcoordinators", "bridges", "cambridge", "classroom_teachers", "discoveryparas", "discoveryteachers",
    "enroll", "explorersparas", "explorersteachers", "facilities", "inspire", "inspireprogram", "it", "paraprofessionals",
    "pathfindersparas", "pathfindersteachers", "sail", "sailteam", "shorestaffall", "soar", "ss_nursing", "ss_staff",
    "teachers", "therapist",
})

_APPROVAL = frozenset({
    "adult-services-dss2-peabody", "as-status-change", "asl---january-2026", "asl---march-2026",
    "asl---may-2026", "asl---mini-session", "asl---summer-2026", "asl-class-fall-2025",
    "basketball", "boardofdirectors", "burgayteam", "ccfr-group", "chelsearemote", "division_directors",
    "emergency", "finance-and-administrative-staff", "home_trainers", "ksgroup", "leadership-team",
    "lunchgroup", "med_web", "medicaidbilling", "operational-group", "safety-care-trainers",
    "shore-asl-learning-community-fall", "shore-asl-learning-community-winter", "shoreappsheet",
    "ssnursesefax", "summerenrichment", "termination",
})

_INHERITED = frozenset({"adult-nursing", "adult_managers", "adult_therapists", "nursing_all", "staff"})
_EXCLUDED = frozenset({"ittools", "tempshorestaffall", "testforgene"})

# Child -> immediate parent(s). Parent groups are informational, not direct tasks.
_PARENTS = {
    "adult-nurses-peabody": ("adult-nursing",),
    "adult-nursing": ("nursing_all",),
    "ss_nursing": ("nursing_all",),
    "adult-services-managers-chelsea": ("adult_managers",),
    "adult-services-managers-peabody": ("adult_managers",),
    "adult-services-managers-woburn": ("adult_managers",),
    "adult-therapists-chelsea": ("adult_therapists",),
    "adult-therapists-peabody": ("adult_therapists",),
    "adult-therapists-woburn": ("adult_therapists",),
}


def _policy(local_part: str) -> GroupPolicy:
    if local_part in _EXCLUDED:
        return GroupPolicy.EXCLUDED
    if local_part in _INHERITED:
        return GroupPolicy.INHERITED
    if local_part in _APPROVAL:
        return GroupPolicy.IT_APPROVAL
    if local_part in _AUTOMATIC:
        return GroupPolicy.AUTOMATIC
    return GroupPolicy.MANUAL_REVIEW


def _build_catalog() -> dict[str, GroupDefinition]:
    catalog: dict[str, GroupDefinition] = {}
    for line in _GROUPS.splitlines():
        name, local_part = line.split("|", maxsplit=1)
        email = f"{local_part}@{DOMAIN}"
        if email in catalog:
            raise ValueError(f"Duplicate group email: {email}")
        catalog[email] = GroupDefinition(
            name=name,
            email=email,
            policy=_policy(local_part),
            parent_emails=tuple(f"{parent}@{DOMAIN}" for parent in _PARENTS.get(local_part, ())),
        )
    return catalog


GROUP_CATALOG = _build_catalog()


def get_group(email: str) -> GroupDefinition | None:
    """Find a group by email, case-insensitively."""
    return GROUP_CATALOG.get(email.strip().lower())


def get_group_policy(email: str) -> GroupPolicy:
    """Unknown groups always require manual review, never automatic access."""
    group = get_group(email)
    return group.policy if group else GroupPolicy.MANUAL_REVIEW


def inherited_parent_emails(email: str) -> tuple[str, ...]:
    """Return known transitive parent groups without claiming live membership."""
    result: list[str] = []
    visited: set[str] = set()

    def visit(address: str) -> None:
        group = get_group(address)
        if not group:
            return
        for parent in group.parent_emails:
            if parent not in visited:
                visited.add(parent)
                result.append(parent)
                visit(parent)

    visit(email)
    return tuple(result)
