
"""Tests for audit-backed group approval review completion."""

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
)
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Keep test audit events out of Shore's real data directory."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )


def make_review():
    """Create a fictional review containing two actionable groups."""
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

    return create_group_approval_review(
        onboarding_id="TEST-ONBOARDING-001",
        employee_email="alex.morgan@example.org",
        recommendations=recommendations,
    )


def resolve_review(review):
    """Approve one group and reject the other."""
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


def test_completed_review_records_audit_event():
    review = make_review()
    resolve_review(review)

    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        notes="Final review completed",
    )

    assert review.status is GroupReviewStatus.COMPLETED

    events = audit.load_audit_events()
    assert len(events) == 3

    completion = events[-1]
    assert completion["event_type"] == "group_review_completed"
    assert completion["employee_email"] == "alex.morgan@example.org"

    details = completion["details"]
    assert details["onboarding_id"] == "TEST-ONBOARDING-001"
    assert details["administrator_name"] == "Jane Administrator"
    assert details["notes"] == "Final review completed"
    assert details["previous_status"] == "in_progress"
    assert details["new_status"] == "completed"
    assert details["total_groups"] == 2
    assert details["approved_groups"] == ["teachers@example.org"]
    assert details["rejected_groups"] == ["sail@example.org"]


def test_not_reviewed_group_blocks_completion():
    review = make_review()

    with pytest.raises(
        GroupApprovalError,
        match="Every group must be approved or rejected",
    ):
        complete_group_approval_review(
            review,
            administrator_name="Jane Administrator",
        )

    assert review.status is GroupReviewStatus.IN_PROGRESS
    assert audit.load_audit_events() == []


def test_deferred_group_blocks_completion():
    review = make_review()

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )
    record_group_decision(
        review,
        group_email="sail@example.org",
        decision=GroupDecision.DEFERRED,
        administrator_name="Jane Administrator",
    )

    with pytest.raises(
        GroupApprovalError,
        match="Every group must be approved or rejected",
    ):
        complete_group_approval_review(
            review,
            administrator_name="Jane Administrator",
        )

    assert review.status is GroupReviewStatus.IN_PROGRESS
    assert len(audit.load_audit_events()) == 2


def test_completion_requires_administrator_name():
    review = make_review()
    resolve_review(review)

    with pytest.raises(
        GroupApprovalError,
        match="Administrator name is required",
    ):
        complete_group_approval_review(
            review,
            administrator_name=" ",
        )

    assert review.status is GroupReviewStatus.IN_PROGRESS
    assert len(audit.load_audit_events()) == 2


def test_completed_review_cannot_be_completed_again():
    review = make_review()
    resolve_review(review)

    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
    )

    with pytest.raises(
        GroupApprovalError,
        match="already completed",
    ):
        complete_group_approval_review(
            review,
            administrator_name="Jane Administrator",
        )

    assert review.status is GroupReviewStatus.COMPLETED
    assert len(audit.load_audit_events()) == 3


def test_audit_failure_preserves_review_status():
    review = make_review()
    resolve_review(review)

    with (
        patch(
            "src.group_approval.record_audit_event",
            side_effect=audit.AuditWriteError("Disk unavailable"),
        ),
        pytest.raises(audit.AuditWriteError),
    ):
        complete_group_approval_review(
            review,
            administrator_name="Jane Administrator",
        )

    assert review.status is GroupReviewStatus.IN_PROGRESS
    assert len(audit.load_audit_events()) == 2
