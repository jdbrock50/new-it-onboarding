
"""Tests for audited creation of local group approval reviews."""

from unittest.mock import patch

import pytest

from src import audit
from src.group_approval import (
    GroupApprovalError,
    GroupReviewStatus,
    start_group_approval_review,
)
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture
def audit_file(tmp_path, monkeypatch):
    """Keep test audit events separate from production data."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )
    return audit.AUDIT_FILE


def make_recommendations():
    """Create fictional group recommendations."""
    return GroupRecommendationResult(
        recommendations=(
            GroupRecommendation(
                email="teachers@example.org",
                name="Teachers",
                policy=GroupPolicy.AUTOMATIC,
                reason="Teaching position",
                inherited=False,
            ),
            GroupRecommendation(
                email="leadership@example.org",
                name="Leadership",
                policy=GroupPolicy.IT_APPROVAL,
                reason="Leadership responsibilities",
                inherited=False,
            ),
            GroupRecommendation(
                email="staff@example.org",
                name="All Staff",
                policy=GroupPolicy.INHERITED,
                reason="Inherited membership",
                inherited=True,
            ),
        ),
    )


def start_review(
    onboarding_id="TEST-001",
    employee_email="alex.morgan@example.org",
):
    """Start an audited review using fictional test data."""
    return start_group_approval_review(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        recommendations=make_recommendations(),
        administrator_name="Jane Administrator",
    )


def test_start_review_records_creation_event(audit_file):
    """Starting a review must create one durable audit event."""
    review = start_group_approval_review(
        onboarding_id="TEST-001",
        employee_email="alex.morgan@example.org",
        recommendations=make_recommendations(),
        administrator_name="Jane Administrator",
    )

    assert review.status is GroupReviewStatus.IN_PROGRESS
    assert len(review.groups) == 2

    events = audit.load_audit_events()

    assert len(events) == 1
    assert events[0]["event_type"] == "group_review_created"
    assert events[0]["employee_email"] == "alex.morgan@example.org"

    details = events[0]["details"]

    assert details["onboarding_id"] == "TEST-001"
    assert details["administrator_name"] == "Jane Administrator"
    assert details["new_status"] == "in_progress"

    groups = details["groups"]

    assert len(groups) == 2
    assert groups[0]["group_email"] == "teachers@example.org"
    assert groups[0]["group_policy"] == "automatic"
    assert groups[0]["decision"] == "not_reviewed"
    assert groups[1]["group_email"] == "leadership@example.org"


def test_start_review_requires_administrator(audit_file):
    """An administrator must be identified before starting a review."""
    with pytest.raises(
        GroupApprovalError,
        match="Administrator name is required",
    ):
        start_group_approval_review(
            onboarding_id="TEST-001",
            employee_email="alex.morgan@example.org",
            recommendations=make_recommendations(),
            administrator_name=" ",
        )

    assert audit.load_audit_events() == []


def test_audit_failure_prevents_review_creation(audit_file):
    """A failed audit write must prevent successful review creation."""
    with (
        patch(
            "src.group_approval.record_audit_event",
            side_effect=audit.AuditWriteError("Disk unavailable"),
        ),
        pytest.raises(audit.AuditWriteError),
    ):
        start_group_approval_review(
            onboarding_id="TEST-001",
            employee_email="alex.morgan@example.org",
            recommendations=make_recommendations(),
            administrator_name="Jane Administrator",
        )

    assert audit.load_audit_events() == []


def test_duplicate_onboarding_id_is_rejected(audit_file):
    """An onboarding ID cannot have two created reviews."""
    start_review()

    with pytest.raises(
        GroupApprovalError,
        match="already exists",
    ):
        start_review()

    events = audit.load_audit_events()

    assert len(events) == 1
    assert events[0]["event_type"] == "group_review_created"


def test_duplicate_id_is_rejected_for_different_employee(audit_file):
    """Changing the employee email must not bypass duplicate protection."""
    start_review()

    with pytest.raises(
        GroupApprovalError,
        match="already exists",
    ):
        start_review(
            onboarding_id="TEST-001",
            employee_email="different.employee@example.org",
        )

    assert len(audit.load_audit_events()) == 1


def test_different_onboarding_ids_are_allowed(audit_file):
    """Separate onboarding IDs may each have their own review."""
    first = start_review(onboarding_id="TEST-001")
    second = start_review(onboarding_id="TEST-002")

    assert first.onboarding_id == "TEST-001"
    assert second.onboarding_id == "TEST-002"

    events = audit.load_audit_events()

    assert len(events) == 2
    assert all(
        event["event_type"] == "group_review_created"
        for event in events
    )


def test_audit_read_failure_prevents_review_creation(audit_file):
    """Unreadable audit history must never be treated as empty."""
    with (
        patch(
            "src.group_approval.load_audit_events",
            side_effect=OSError("Audit file unavailable"),
        ),
        pytest.raises(OSError, match="Audit file unavailable"),
    ):
        start_review()

    assert not audit_file.exists()


def test_malformed_audit_history_prevents_review_creation(audit_file):
    """Invalid audit JSON must prevent creating another review."""
    audit_file.write_text(
        "{invalid json}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        start_review()

    assert audit_file.read_text(encoding="utf-8") == (
        "{invalid json}\n"
    )


def test_unrelated_audit_events_do_not_block_creation(audit_file):
    """Other onboarding audit events must not count as reviews."""
    audit.record_audit_event(
        "verification_completed",
        employee_email="alex.morgan@example.org",
        details={"onboarding_id": "TEST-001"},
    )

    review = start_review()

    assert review.onboarding_id == "TEST-001"
    assert len(audit.load_audit_events()) == 2
