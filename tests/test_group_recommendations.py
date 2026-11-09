"""Read-only regression tests for Shore group recommendations."""

from datetime import date

import pytest

from src.employee import Employee
from src.group_catalog import GroupPolicy
from src.group_recommendations import recommend_groups

DOMAIN = "shorecollaborative.org"


def make_employee(*, job_title="Teacher", department="Student Services", program="SAIL", additional_programs=None, location="Cambridge"):
    return Employee(
        first_name="Test",
        last_name="Employee",
        job_title=job_title,
        department=department,
        program=program,
        additional_programs=additional_programs or [],
        location=location,
        supervisor="Test Supervisor",
        start_date=date(2026, 12, 1),
        personal_email="test.employee@example.com",
    )


def by_local_part(result):
    return {recommendation.email.split("@", 1)[0]: recommendation for recommendation in result.recommendations}


def test_multi_program_teacher_has_exact_expected_groups():
    result = recommend_groups(make_employee(additional_programs=["Bridges", "Soar"]))
    assert set(by_local_part(result)) == {
        "bridges", "cambridge", "classroom_teachers", "sail", "sailteam",
        "shorestaffall", "soar", "ss_staff", "teachers",
    }
    assert not result.review_notes


def test_duplicate_programs_do_not_duplicate_groups():
    result = recommend_groups(make_employee(additional_programs=["SAIL", "sail", "Bridges", "bridges"]))
    emails = [r.email for r in result.recommendations]
    assert len(emails) == len(set(emails))
    assert "bridges" in by_local_part(result)


def test_adult_peabody_nurse_inheritance():
    result = recommend_groups(make_employee(job_title="Nurse", department="Adult Services", program="Adult Services", location="Peabody"))
    groups = by_local_part(result)
    assert set(groups) == {"adult-nurses-peabody", "adult-nursing", "adult-services-all-staff", "adult-services-peabody", "nursing_all", "shorestaffall"}
    assert groups["adult-nurses-peabody"].policy is GroupPolicy.AUTOMATIC
    assert not groups["adult-nurses-peabody"].inherited
    assert groups["adult-nursing"].inherited
    assert groups["nursing_all"].inherited
    assert all(r.policy is GroupPolicy.INHERITED for r in result.inherited)


@pytest.mark.parametrize("location,local_group", [
    ("Chelsea", "adult-services-staff-chelsea"),
    ("Woburn", "adult-services-staff-woburn"),
])
def test_adult_nurse_other_locations_require_review(location, local_group):
    result = recommend_groups(make_employee(job_title="Nurse", department="Adult Services", program="Adult Services", location=location))
    groups = by_local_part(result)
    assert set(groups) == {"adult-services-all-staff", local_group, "shorestaffall"}
    assert any("nursing" in note.lower() and "review" in note.lower() for note in result.review_notes)


def test_adult_woburn_therapist_inheritance():
    result = recommend_groups(make_employee(job_title="Occupational Therapist", department="Adult Services", program="Adult Services", location="Woburn"))
    groups = by_local_part(result)
    assert "adult-therapists-woburn" in groups
    assert groups["adult-therapists-woburn"].policy is GroupPolicy.AUTOMATIC
    assert groups["adult_therapists"].inherited


def test_adult_chelsea_manager_inheritance():
    result = recommend_groups(make_employee(job_title="Program Manager", department="Adult Services", program="Adult Services", location="Chelsea"))
    groups = by_local_part(result)
    assert "adult-services-managers-chelsea" in groups
    assert groups["adult_managers"].inherited


def test_adult_program_coordinator_not_manager():
    result = recommend_groups(make_employee(job_title="Program Coordinator", department="Adult Services", program="Adult Services", location="Peabody"))
    assert set(by_local_part(result)) == {"adult-services-all-staff", "adult-services-peabody", "adultprogramcoordinators", "shorestaffall"}


@pytest.mark.parametrize("program,stem,review_fragment", [
    ("Discovery", "discovery", None),
    ("Explorers", "explorers", "E Team"),
    ("Pathfinders", "pathfinders", "Joann F Class"),
])
@pytest.mark.parametrize("job_title,suffix,wrong_suffix", [
    ("Teacher", "teachers", "paras"),
    ("Paraprofessional", "paras", "teachers"),
])
def test_program_role_groups(program, stem, review_fragment, job_title, suffix, wrong_suffix):
    result = recommend_groups(make_employee(job_title=job_title, program=program))
    groups = by_local_part(result)
    assert f"{stem}{suffix}" in groups
    assert f"{stem}{wrong_suffix}" not in groups
    if job_title == "Teacher":
        assert {"teachers", "classroom_teachers"} <= set(groups)
        assert "paraprofessionals" not in groups
    else:
        assert "paraprofessionals" in groups
        assert "teachers" not in groups
        assert "classroom_teachers" not in groups
    if review_fragment:
        assert any(review_fragment in note for note in result.review_notes)
    else:
        assert not result.review_notes


@pytest.mark.parametrize("department,program,expected", [
    ("IT", "Technology", "it"),
    ("Facilities", "Operations", "facilities"),
    ("Admissions", "Enrollment", "enroll"),
])
def test_department_groups(department, program, expected):
    result = recommend_groups(make_employee(job_title="Support Specialist", department=department, program=program))
    assert set(by_local_part(result)) == {"shorestaffall", "cambridge", expected}


def test_restricted_groups_never_directly_recommended_across_scenarios():
    scenarios = [
        make_employee(job_title="IT Specialist", department="IT", program="Technology"),
        make_employee(job_title="Finance Director", department="Finance", program="Administration", location="Chelsea"),
        make_employee(job_title="Nurse"),
        make_employee(job_title="Program Manager", department="Adult Services", program="Adult Services", location="Peabody"),
        make_employee(program="Explorers"),
    ]
    for employee in scenarios:
        result = recommend_groups(employee)
        assert all(
            r.inherited or r.policy not in {GroupPolicy.IT_APPROVAL, GroupPolicy.MANUAL_REVIEW, GroupPolicy.EXCLUDED}
            for r in result.recommendations
        )
        assert all(r.email.endswith(f"@{DOMAIN}") for r in result.recommendations)
        assert "ittools" not in by_local_part(result)
        assert "tempshorestaffall" not in by_local_part(result)
