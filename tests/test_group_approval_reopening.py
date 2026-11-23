
"""Tests for reopening completed group approval reviews."""

from unittest.mock import patch

import pytest

from src import audit
from src.group_approval import (
    GroupApprovalError,
    GroupDecision,
    GroupReviewStatus,
    complete_group_approval_review,
    create_group_approval_review,
    record_group_decision,
    reopen_group_approval_review,
)
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Keep test audit events separate from real onboarding data."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )


def make_completed_review():
    """Create a completed review using fictional employee information."""
    recommendations = GroupRecommendationResult(
        recommendations=(
            GroupRecommendation(
                email="teachers@example.org",
                name="Teachers",
                policy=GroupPolicy.AUTOMATIC,
                reason="Teacher position",
            ),
            GroupRecommendation(
                email="sail@example.org",
                name="SAIL",
                policy=GroupPolicy.IT_APPROVAL,
                reason="SAIL program assignment",
            ),
        ),
    )

    review = create_group_approval_review(
        onboarding_id="TEST-ONBOARDING-001",
        employee_email="alex.morgan@example.org",
        recommendations=recommendations,
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )

    record_group_decision(
        review,
        group_email="sail@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Jane Administrator",
    )

    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
    )

    return review


def test_completed_review_can_be_reopened():
    review = make_completed_review()

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="New employee assignment information",
    )

    assert review.status is GroupReviewStatus.IN_PROGRESS

    events = audit.load_audit_events()
    assert len(events) == 4
    assert events[-1]["event_type"] == "group_review_reopened"


def test_reopening_requires_completed_status():
    review = make_completed_review()

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Assignment changed",
    )

    with pytest.raises(
        GroupApprovalError,
        match="Only completed group approval reviews can be reopened",
    ):
        reopen_group_approval_review(
            review,
            administrator_name="Jane Administrator",
            reopen_reason="Second reopening attempt",
        )

    assert len(audit.load_audit_events()) == 4


def test_reopening_requires_administrator_name():
    review = make_completed_review()

    with pytest.raises(
        GroupApprovalError,
        match="Administrator name is required",
    ):
        reopen_group_approval_review(
            review,
            administrator_name=" ",
            reopen_reason="Assignment changed",
        )

    assert review.status is GroupReviewStatus.COMPLETED
    assert len(audit.load_audit_events()) == 3


def test_reopening_requires_reason():
    review = make_completed_review()

    with pytest.raises(
        GroupApprovalError,
        match="A reason is required",
    ):
        reopen_group_approval_review(
            review,
            administrator_name="Jane Administrator",
            reopen_reason=" ",
        )

    assert review.status is GroupReviewStatus.COMPLETED
    assert len(audit.load_audit_events()) == 3


def test_reopening_preserves_existing_decisions():
    review = make_completed_review()

    original_decisions = {
        email: group.decision
        for email, group in review.groups.items()
    }

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Review employee assignment",
    )

    assert {
        email: group.decision
        for email, group in review.groups.items()
    } == original_decisions


def test_reopening_records_complete_audit_details():
    review = make_completed_review()

    reopen_group_approval_review(
        review,
        administrator_name=" Jane Administrator ",
        reopen_reason=" Updated assignment ",
        notes=" Follow-up requested ",
    )

    event = audit.load_audit_events()[-1]
    details = event["details"]

    assert event["event_type"] == "group_review_reopened"
    assert event["employee_email"] == "alex.morgan@example.org"
    assert details["onboarding_id"] == "TEST-ONBOARDING-001"
    assert details["administrator_name"] == "Jane Administrator"
    assert details["reopen_reason"] == "Updated assignment"
    assert details["notes"] == "Follow-up requested"
    assert details["previous_status"] == "completed"
    assert details["new_status"] == "in_progress"
    assert details["total_groups"] == 2


def test_audit_failure_preserves_completed_status():
    review = make_completed_review()

    with (
        patch(
            "src.group_approval.record_audit_event",
            side_effect=audit.AuditWriteError("Disk unavailable"),
        ),
        pytest.raises(audit.AuditWriteError),
    ):
        reopen_group_approval_review(
            review,
            administrator_name="Jane Administrator",
            reopen_reason="Assignment changed",
        )

    assert review.status is GroupReviewStatus.COMPLETED
    assert len(audit.load_audit_events()) == 3


def test_reopened_review_can_change_decisions_and_complete_again():
    review = make_completed_review()

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Employee program assignment changed",
    )

    record_group_decision(
        review,
        group_email="sail@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
        change_reason="Employee is now assigned to SAIL",
    )

    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        notes="Updated review approved",
    )

    assert review.status is GroupReviewStatus.COMPLETED
    assert review.groups["sail@example.org"].decision is GroupDecision.APPROVED

    events = audit.load_audit_events()
    assert len(events) == 6
    assert [event["event_type"] for event in events[-3:]] == [
        "group_review_reopened",
        "group_decision_changed",
        "group_review_completed",
    ]
