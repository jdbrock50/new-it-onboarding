
"""Tests for the local Google Workspace group approval workflow."""

from unittest.mock import patch

import pytest

from src import audit
from src.group_approval import (
    GroupApprovalError,
    GroupDecision,
    GroupReviewStatus,
    create_group_approval_review,
    record_group_decision,
    start_group_approval_review,
    restore_group_approval_review,
    complete_group_approval_review,
    reopen_group_approval_review,
)
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture
def audit_file(tmp_path, monkeypatch):
    """Keep approval audit events out of the real data directory."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )
    return audit.AUDIT_FILE


def make_recommendation(
    email: str,
    policy: GroupPolicy = GroupPolicy.AUTOMATIC,
    *,
    inherited: bool = False,
) -> GroupRecommendation:
    """Build a fictional group recommendation for testing."""
    return GroupRecommendation(
        email=email,
        name=email.split("@")[0],
        policy=policy,
        reason="Fictional test recommendation",
        inherited=inherited,
    )


def make_review(*recommendations: GroupRecommendation):
    """Build a fictional employee's group approval review."""
    return create_group_approval_review(
        onboarding_id="TEST-ONBOARDING-001",
        employee_email="alex.morgan@example.org",
        recommendations=GroupRecommendationResult(
            recommendations=tuple(recommendations),
        ),
    )


def test_review_starts_in_progress():
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    assert review.status == GroupReviewStatus.IN_PROGRESS
    assert review.onboarding_id == "TEST-ONBOARDING-001"
    assert review.employee_email == "alex.morgan@example.org"


def test_actionable_groups_start_not_reviewed():
    review = make_review(
        make_recommendation("teachers@example.org"),
        make_recommendation(
            "leadership@example.org",
            GroupPolicy.IT_APPROVAL,
        ),
        make_recommendation(
            "specialists@example.org",
            GroupPolicy.MANUAL_REVIEW,
        ),
    )

    assert len(review.groups) == 3
    assert all(
        group.decision == GroupDecision.NOT_REVIEWED
        for group in review.groups.values()
    )
    assert len(review.unresolved_groups) == 3
    assert not review.can_complete


def test_inherited_groups_are_not_actionable():
    review = make_review(
        make_recommendation("teachers@example.org"),
        make_recommendation(
            "staff@example.org",
            GroupPolicy.INHERITED,
            inherited=True,
        ),
    )

    assert "teachers@example.org" in review.groups
    assert "staff@example.org" not in review.groups


def test_excluded_groups_are_not_actionable():
    review = make_review(
        make_recommendation("teachers@example.org"),
        make_recommendation(
            "excluded@example.org",
            GroupPolicy.EXCLUDED,
        ),
    )

    assert len(review.groups) == 1
    assert "excluded@example.org" not in review.groups


def test_review_requires_final_decisions():
    review = make_review(
        make_recommendation("teachers@example.org"),
        make_recommendation("sail@example.org"),
    )

    review.groups["teachers@example.org"].decision = (
        GroupDecision.APPROVED
    )
    review.groups["sail@example.org"].decision = (
        GroupDecision.DEFERRED
    )

    assert not review.can_complete
    assert len(review.unresolved_groups) == 1

    review.groups["sail@example.org"].decision = (
        GroupDecision.REJECTED
    )

    assert review.can_complete
    assert review.unresolved_groups == ()


def test_empty_review_cannot_complete():
    review = make_review()

    assert review.groups == {}
    assert not review.can_complete


def test_duplicate_group_emails_are_rejected():
    with pytest.raises(
        GroupApprovalError,
        match="Duplicate group recommendation",
    ):
        make_review(
            make_recommendation("teachers@example.org"),
            make_recommendation("TEACHERS@example.org"),
        )


@pytest.mark.parametrize(
    ("onboarding_id", "employee_email"),
    [
        ("", "alex.morgan@example.org"),
        ("TEST-001", ""),
        ("   ", "alex.morgan@example.org"),
        ("TEST-001", "   "),
    ],
)
def test_required_identifiers_are_validated(
    onboarding_id,
    employee_email,
):
    with pytest.raises(GroupApprovalError):
        create_group_approval_review(
            onboarding_id=onboarding_id,
            employee_email=employee_email,
            recommendations=GroupRecommendationResult(
                recommendations=(),
            ),
        )


def test_approval_records_audit_event(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
        notes="Verified teaching assignment",
    )

    assert review.groups["teachers@example.org"].decision == (
        GroupDecision.APPROVED
    )

    events = audit.load_audit_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "group_decision_recorded"
    assert events[0]["employee_email"] == "alex.morgan@example.org"

    details = events[0]["details"]
    assert details["onboarding_id"] == "TEST-ONBOARDING-001"
    assert details["group_email"] == "teachers@example.org"
    assert details["previous_decision"] == "not_reviewed"
    assert details["new_decision"] == "approved"
    assert details["administrator_name"] == "Jane Administrator"
    assert details["notes"] == "Verified teaching assignment"


def test_rejection_records_audit_event(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Jane Administrator",
    )

    assert review.groups["teachers@example.org"].decision == (
        GroupDecision.REJECTED
    )
    assert audit.load_audit_events()[0]["details"]["new_decision"] == (
        "rejected"
    )


def test_changing_decision_requires_reason(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )

    with pytest.raises(
        GroupApprovalError,
        match="reason is required",
    ):
        record_group_decision(
            review,
            group_email="teachers@example.org",
            decision=GroupDecision.REJECTED,
            administrator_name="Jane Administrator",
        )

    assert review.groups["teachers@example.org"].decision == (
        GroupDecision.APPROVED
    )
    assert len(audit.load_audit_events()) == 1


def test_decision_change_preserves_audit_history(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="John Administrator",
        change_reason="Assignment corrected by supervisor",
    )

    events = audit.load_audit_events()
    assert len(events) == 2
    assert events[0]["event_type"] == "group_decision_recorded"
    assert events[1]["event_type"] == "group_decision_changed"
    assert events[1]["details"]["previous_decision"] == "approved"
    assert events[1]["details"]["new_decision"] == "rejected"
    assert events[1]["details"]["change_reason"] == (
        "Assignment corrected by supervisor"
    )


def test_missing_administrator_is_rejected(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    with pytest.raises(
        GroupApprovalError,
        match="Administrator name is required",
    ):
        record_group_decision(
            review,
            group_email="teachers@example.org",
            decision=GroupDecision.APPROVED,
            administrator_name=" ",
        )

    assert audit.load_audit_events() == []


def test_unknown_group_is_rejected(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    with pytest.raises(
        GroupApprovalError,
        match="not eligible for approval",
    ):
        record_group_decision(
            review,
            group_email="unknown@example.org",
            decision=GroupDecision.APPROVED,
            administrator_name="Jane Administrator",
        )

    assert audit.load_audit_events() == []


def test_completed_review_rejects_decision_changes(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )
    review.status = GroupReviewStatus.COMPLETED

    with pytest.raises(
        GroupApprovalError,
        match="must be reopened",
    ):
        record_group_decision(
            review,
            group_email="teachers@example.org",
            decision=GroupDecision.APPROVED,
            administrator_name="Jane Administrator",
        )

    assert audit.load_audit_events() == []


def test_audit_failure_preserves_previous_decision(audit_file):
    review = make_review(
        make_recommendation("teachers@example.org"),
    )

    with (
        patch(
            "src.group_approval.record_audit_event",
            side_effect=audit.AuditWriteError("Disk unavailable"),
        ),
        pytest.raises(audit.AuditWriteError),
    ):
        record_group_decision(
            review,
            group_email="teachers@example.org",
            decision=GroupDecision.APPROVED,
            administrator_name="Jane Administrator",
        )

    assert review.groups["teachers@example.org"].decision == (
        GroupDecision.NOT_REVIEWED
    )
    assert audit.load_audit_events() == []


# Step 472: Persistence checks use the real JSONL audit file isolated by audit_file.
# No Google Workspace API is contacted.


def make_audited_review(*recommendations: GroupRecommendation):
    return start_group_approval_review(
        onboarding_id="TEST-ONBOARDING-001",
        employee_email="alex.morgan@example.org",
        recommendations=GroupRecommendationResult(
            recommendations=tuple(recommendations),
        ),
        administrator_name="Jane Administrator",
    )


@pytest.mark.parametrize(
    "decision",
    [GroupDecision.APPROVED, GroupDecision.REJECTED, GroupDecision.DEFERRED],
)
def test_decision_survives_restore_from_audit(audit_file, decision):
    review = make_audited_review(make_recommendation("teachers@example.org"))
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=decision,
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)

    assert restored is not review
    assert restored.groups["teachers@example.org"] is not review.groups["teachers@example.org"]
    assert restored.groups["teachers@example.org"].decision is decision
    assert restored.status is GroupReviewStatus.IN_PROGRESS
    assert len(audit.load_audit_events()) == 2


def test_multiple_group_decisions_survive_restore(audit_file):
    review = make_audited_review(
        make_recommendation("teachers@example.org"),
        make_recommendation("leadership@example.org", GroupPolicy.IT_APPROVAL),
        make_recommendation("specialists@example.org", GroupPolicy.MANUAL_REVIEW),
    )
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )
    record_group_decision(
        review,
        group_email="leadership@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)

    assert restored.groups["teachers@example.org"].decision is GroupDecision.APPROVED
    assert restored.groups["leadership@example.org"].decision is GroupDecision.REJECTED
    assert restored.groups["specialists@example.org"].decision is GroupDecision.NOT_REVIEWED
    assert len(restored.unresolved_groups) == 1
    assert not restored.can_complete


def test_changed_decision_survives_restore_with_history(audit_file):
    review = make_audited_review(make_recommendation("teachers@example.org"))
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="John Administrator",
        change_reason="Supervisor corrected assignment",
    )

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)
    events = audit.load_audit_events()

    assert restored.groups["teachers@example.org"].decision is GroupDecision.REJECTED
    assert [event["event_type"] for event in events] == [
        "group_review_created", "group_decision_recorded", "group_decision_changed"
    ]
    assert events[-1]["details"]["change_reason"] == "Supervisor corrected assignment"


def test_completed_review_status_survives_restore(audit_file):
    review = make_audited_review(make_recommendation("teachers@example.org"))
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )
    complete_group_approval_review(review, administrator_name="Jane Administrator")

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)

    assert restored.status is GroupReviewStatus.COMPLETED
    assert restored.groups["teachers@example.org"].decision is GroupDecision.APPROVED
    with pytest.raises(GroupApprovalError, match="must be reopened"):
        record_group_decision(
            restored,
            group_email="teachers@example.org",
            decision=GroupDecision.REJECTED,
            administrator_name="Jane Administrator",
            change_reason="New assignment",
        )
    assert len(audit.load_audit_events()) == 3


def test_reopened_review_and_subsequent_change_survive_restore(audit_file):
    review = make_audited_review(make_recommendation("teachers@example.org"))
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )
    complete_group_approval_review(review, administrator_name="Jane Administrator")
    reopen_group_approval_review(
        review,
        administrator_name="John Administrator",
        reopen_reason="Updated assignment",
    )
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="John Administrator",
        change_reason="Updated assignment",
    )

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)

    assert restored.status is GroupReviewStatus.IN_PROGRESS
    assert restored.groups["teachers@example.org"].decision is GroupDecision.REJECTED
    assert restored.can_complete
    assert [event["event_type"] for event in audit.load_audit_events()] == [
        "group_review_created",
        "group_decision_recorded",
        "group_review_completed",
        "group_review_reopened",
        "group_decision_changed",
    ]


def test_console_string_decision_is_normalized_and_restored(audit_file):
    review = make_audited_review(make_recommendation("teachers@example.org"))
    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision="approved",
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(onboarding_id=review.onboarding_id)

    assert restored.groups["teachers@example.org"].decision is GroupDecision.APPROVED
    assert audit.load_audit_events()[-1]["details"]["new_decision"] == "approved"
