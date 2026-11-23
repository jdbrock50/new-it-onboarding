
"""Tests for restoring group approval reviews from audit history."""

import pytest

from src import audit
from src.group_approval import (
    GroupApprovalError,
    GroupDecision,
    GroupReviewStatus,
    complete_group_approval_review,
    record_group_decision,
    reopen_group_approval_review,
    restore_group_approval_review,
    start_group_approval_review,
)
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Keep test events separate from real onboarding data."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )


def make_recommendations():
    """Create fictional group recommendations."""
    return GroupRecommendationResult(
        recommendations=(
            GroupRecommendation(
                email="teachers@example.org",
                name="Teachers",
                policy=GroupPolicy.AUTOMATIC,
                reason="Teaching position",
            ),
            GroupRecommendation(
                email="leadership@example.org",
                name="Leadership",
                policy=GroupPolicy.IT_APPROVAL,
                reason="Leadership responsibilities",
            ),
        ),
    )


def start_review(
    onboarding_id="TEST-001",
    employee_email="alex.morgan@example.org",
):
    """Create an audited review with fictional employee information."""
    return start_group_approval_review(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        recommendations=make_recommendations(),
        administrator_name="Jane Administrator",
    )


def resolve_review(review):
    """Approve teaching access and reject leadership access."""
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


def complete_review(review):
    """Complete an audited review with final decisions."""
    resolve_review(review)
    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
    )


def test_restore_newly_created_review():
    """A review can be reconstructed from its creation event."""
    original = start_group_approval_review(
        onboarding_id="TEST-001",
        employee_email="alex.morgan@example.org",
        recommendations=make_recommendations(),
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored is not original
    assert restored.onboarding_id == original.onboarding_id
    assert restored.employee_email == original.employee_email
    assert restored.status is GroupReviewStatus.IN_PROGRESS

    assert set(restored.groups) == set(original.groups)

    for email, original_group in original.groups.items():
        restored_group = restored.groups[email]

        assert restored_group.group_name == original_group.group_name
        assert restored_group.policy is original_group.policy
        assert restored_group.reason == original_group.reason
        assert restored_group.decision is GroupDecision.NOT_REVIEWED


def test_restore_approved_and_rejected_decisions():
    """Previously recorded final decisions must survive restoration."""
    review = start_review()

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

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.APPROVED
    )
    assert restored.groups["leadership@example.org"].decision is (
        GroupDecision.REJECTED
    )
    assert restored.can_complete


def test_restore_deferred_decision():
    """Deferred decisions must remain unresolved after restoration."""
    review = start_review()

    record_group_decision(
        review,
        group_email="teachers@example.org",
        decision=GroupDecision.DEFERRED,
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.DEFERRED
    )
    assert not restored.can_complete
    assert len(restored.unresolved_groups) == 2


def test_restore_latest_decision_change():
    """The most recent valid decision must determine restored state."""
    review = start_review()

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
        change_reason="Employee assignment corrected",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.REJECTED
    )


def test_restore_ignores_other_onboarding_decisions():
    """Events for other onboarding IDs must not affect the review."""
    first = start_review(
        onboarding_id="TEST-001",
        employee_email="alex.morgan@example.org",
    )
    second = start_review(
        onboarding_id="TEST-002",
        employee_email="sam.taylor@example.org",
    )

    record_group_decision(
        first,
        group_email="teachers@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
    )

    record_group_decision(
        second,
        group_email="teachers@example.org",
        decision=GroupDecision.REJECTED,
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.APPROVED
    )
    assert restored.employee_email == "alex.morgan@example.org"


def test_restore_rejects_invalid_decision_sequence():
    """An audit event with an incorrect previous decision is invalid."""
    start_review()

    audit.record_audit_event(
        "group_decision_changed",
        employee_email="alex.morgan@example.org",
        details={
            "onboarding_id": "TEST-001",
            "group_email": "teachers@example.org",
            "previous_decision": "approved",
            "new_decision": "rejected",
            "administrator_name": "Jane Administrator",
            "change_reason": "Incorrect sequence",
        },
    )

    with pytest.raises(GroupApprovalError):
        restore_group_approval_review(
            onboarding_id="TEST-001",
        )


def test_restore_completed_review():
    """Completion status and final decisions survive restoration."""
    review = start_review()
    complete_review(review)

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.status is GroupReviewStatus.COMPLETED
    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.APPROVED
    )
    assert restored.groups["leadership@example.org"].decision is (
        GroupDecision.REJECTED
    )


def test_restore_reopened_review():
    """Reopening restores in-progress status without losing decisions."""
    review = start_review()
    complete_review(review)

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Employee assignment changed",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.status is GroupReviewStatus.IN_PROGRESS
    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.APPROVED
    )
    assert restored.groups["leadership@example.org"].decision is (
        GroupDecision.REJECTED
    )


def test_restore_reopened_and_completed_again():
    """Replay must preserve the latest lifecycle and decision state."""
    review = start_review()
    complete_review(review)

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Leadership responsibilities changed",
    )

    record_group_decision(
        review,
        group_email="leadership@example.org",
        decision=GroupDecision.APPROVED,
        administrator_name="Jane Administrator",
        change_reason="Employee joined leadership team",
    )

    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
    )

    restored = restore_group_approval_review(
        onboarding_id="TEST-001",
    )

    assert restored.status is GroupReviewStatus.COMPLETED
    assert restored.groups["teachers@example.org"].decision is (
        GroupDecision.APPROVED
    )
    assert restored.groups["leadership@example.org"].decision is (
        GroupDecision.APPROVED
    )


def test_restore_rejects_completion_with_unresolved_groups():
    """An invalid completion event must not be accepted."""
    start_review()

    audit.record_audit_event(
        "group_review_completed",
        employee_email="alex.morgan@example.org",
        details={
            "onboarding_id": "TEST-001",
            "administrator_name": "Jane Administrator",
            "previous_status": "in_progress",
            "new_status": "completed",
            "total_groups": 2,
            "approved_groups": [],
            "rejected_groups": [],
        },
    )

    with pytest.raises(GroupApprovalError):
        restore_group_approval_review(
            onboarding_id="TEST-001",
        )


def test_restore_rejects_reopening_without_completion():
    """A review cannot be restored as reopened without completion."""
    start_review()

    audit.record_audit_event(
        "group_review_reopened",
        employee_email="alex.morgan@example.org",
        details={
            "onboarding_id": "TEST-001",
            "administrator_name": "Jane Administrator",
            "reopen_reason": "Invalid reopening",
            "previous_status": "completed",
            "new_status": "in_progress",
            "total_groups": 2,
        },
    )

    with pytest.raises(GroupApprovalError):
        restore_group_approval_review(
            onboarding_id="TEST-001",
        )


def test_restore_rejects_decision_after_completion():
    """A decision event after completion requires reopening first."""
    review = start_review()
    complete_review(review)

    audit.record_audit_event(
        "group_decision_changed",
        employee_email="alex.morgan@example.org",
        details={
            "onboarding_id": "TEST-001",
            "group_email": "leadership@example.org",
            "previous_decision": "rejected",
            "new_decision": "approved",
            "administrator_name": "Jane Administrator",
            "change_reason": "Unauthorized post-completion change",
        },
    )

    with pytest.raises(GroupApprovalError):
        restore_group_approval_review(
            onboarding_id="TEST-001",
        )
