
"""Tests for read-only group approval reporting."""

import pytest

from src import audit
from src.group_approval import (
    GroupApprovalError,
    GroupDecision,
    GroupReviewStatus,
    complete_group_approval_review,
    record_group_decision,
    reopen_group_approval_review,
    start_group_approval_review,
)
from src.group_approval_reporting import generate_group_approval_report
from src.group_catalog import GroupPolicy
from src.group_recommendations import (
    GroupRecommendation,
    GroupRecommendationResult,
)


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Prevent tests from accessing production audit records."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )


def make_recommendations():
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
    return start_group_approval_review(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        recommendations=make_recommendations(),
        administrator_name="Jane Administrator",
    )


def resolve_review(review):
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


def finish_review(review):
    resolve_review(review)
    complete_group_approval_review(
        review,
        administrator_name="Jane Administrator",
    )


def test_empty_report():
    report = generate_group_approval_report()

    assert report.total_reviews == 0
    assert report.completed_reviews == 0
    assert report.in_progress_reviews == 0
    assert report.pending_reviews == 0
    assert report.reopened_reviews == 0
    assert report.total_groups == 0
    assert report.unresolved == 0


def test_new_review_is_pending():
    start_review()

    report = generate_group_approval_report()

    assert report.total_reviews == 1
    assert report.in_progress_reviews == 1
    assert report.pending_reviews == 1
    assert report.total_groups == 2
    assert report.not_reviewed == 2
    assert report.unresolved == 2

    summary = report.reviews[0]

    assert summary.onboarding_id == "TEST-001"
    assert summary.employee_email == "alex.morgan@example.org"
    assert summary.status is GroupReviewStatus.IN_PROGRESS
    assert summary.reopen_count == 0
    assert not summary.was_reopened


def test_approved_rejected_and_deferred_counts():
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
        decision=GroupDecision.DEFERRED,
        administrator_name="Jane Administrator",
    )

    report = generate_group_approval_report()

    assert report.approved == 1
    assert report.rejected == 0
    assert report.deferred == 1
    assert report.not_reviewed == 0
    assert report.unresolved == 1
    assert report.pending_reviews == 1


def test_completed_review():
    review = start_review()
    finish_review(review)

    report = generate_group_approval_report()

    assert report.completed_reviews == 1
    assert report.in_progress_reviews == 0
    assert report.pending_reviews == 0
    assert report.approved == 1
    assert report.rejected == 1
    assert report.unresolved == 0
    assert report.reviews[0].status is GroupReviewStatus.COMPLETED


def test_reopened_review():
    review = start_review()
    finish_review(review)

    reopen_group_approval_review(
        review,
        administrator_name="Jane Administrator",
        reopen_reason="Employee responsibilities changed",
    )

    report = generate_group_approval_report()

    assert report.completed_reviews == 0
    assert report.in_progress_reviews == 1
    assert report.reopened_reviews == 1
    assert report.total_reopenings == 1
    assert report.reviews[0].was_reopened
    assert report.reviews[0].reopen_count == 1
    assert report.pending_reviews == 0


def test_multiple_reopenings():
    review = start_review()
    finish_review(review)

    for number in range(2):
        reopen_group_approval_review(
            review,
            administrator_name="Jane Administrator",
            reopen_reason=f"Review cycle {number + 1}",
        )
        complete_group_approval_review(
            review,
            administrator_name="Jane Administrator",
        )

    report = generate_group_approval_report()

    assert report.completed_reviews == 1
    assert report.reopened_reviews == 1
    assert report.total_reopenings == 2
    assert report.reviews[0].reopen_count == 2


def test_multiple_reviews():
    first = start_review(
        onboarding_id="TEST-002",
        employee_email="sam.taylor@example.org",
    )
    start_review(
        onboarding_id="TEST-001",
        employee_email="alex.morgan@example.org",
    )

    finish_review(first)

    report = generate_group_approval_report()

    assert report.total_reviews == 2
    assert report.completed_reviews == 1
    assert report.in_progress_reviews == 1
    assert report.pending_reviews == 1
    assert report.total_groups == 4

    assert [review.onboarding_id for review in report.reviews] == [
        "TEST-001",
        "TEST-002",
    ]


def test_latest_decision_is_reported():
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
        administrator_name="Jane Administrator",
        change_reason="Access requirement corrected",
    )

    report = generate_group_approval_report()

    assert report.approved == 0
    assert report.rejected == 1
    assert report.not_reviewed == 1


def test_invalid_decision_history_is_rejected():
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
            "change_reason": "Invalid transition",
        },
    )

    with pytest.raises(GroupApprovalError):
        generate_group_approval_report()


def test_orphaned_reopening_is_rejected():
    audit.record_audit_event(
        "group_review_reopened",
        employee_email="alex.morgan@example.org",
        details={
            "onboarding_id": "MISSING-001",
            "previous_status": "completed",
            "new_status": "in_progress",
            "total_groups": 2,
            "reopen_reason": "Invalid orphaned event",
        },
    )

    with pytest.raises(GroupApprovalError):
        generate_group_approval_report()


def test_unrelated_audit_events_are_ignored():
    audit.record_audit_event(
        "employee_onboarding_created",
        employee_email="alex.morgan@example.org",
        details={"onboarding_id": "OTHER-001"},
    )

    report = generate_group_approval_report()

    assert report.total_reviews == 0


def test_report_does_not_modify_audit_history():
    review = start_review()
    finish_review(review)

    before = audit.AUDIT_FILE.read_bytes()

    report = generate_group_approval_report()

    after = audit.AUDIT_FILE.read_bytes()

    assert report.total_reviews == 1
    assert before == after
