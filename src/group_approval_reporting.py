
"""Read-only reporting for audited Google Workspace group approval reviews.

Reports are reconstructed from local onboarding audit events.
This module never modifies audit history or Google Workspace memberships.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.audit import load_audit_events
from src.group_approval import (
    GroupApprovalError,
    GroupDecision,
    GroupReviewStatus,
    restore_group_approval_review,
)


@dataclass(frozen=True)
class GroupReviewSummary:
    """Current state of one audited group approval review."""

    onboarding_id: str
    employee_email: str
    status: GroupReviewStatus
    total_groups: int
    approved: int
    rejected: int
    deferred: int
    not_reviewed: int
    reopen_count: int

    @property
    def unresolved(self) -> int:
        """Number of groups still requiring a final decision."""
        return self.deferred + self.not_reviewed

    @property
    def was_reopened(self) -> bool:
        """Whether this review has ever been reopened."""
        return self.reopen_count > 0


@dataclass(frozen=True)
class GroupApprovalReport:
    """Aggregate reporting across all audited group reviews."""

    reviews: tuple[GroupReviewSummary, ...]

    @property
    def total_reviews(self) -> int:
        return len(self.reviews)

    @property
    def completed_reviews(self) -> int:
        return sum(
            review.status is GroupReviewStatus.COMPLETED
            for review in self.reviews
        )

    @property
    def in_progress_reviews(self) -> int:
        return sum(
            review.status is GroupReviewStatus.IN_PROGRESS
            for review in self.reviews
        )

    @property
    def pending_reviews(self) -> int:
        """Reviews with at least one unresolved group."""
        return sum(review.unresolved > 0 for review in self.reviews)

    @property
    def reopened_reviews(self) -> int:
        """Reviews that have been reopened at least once."""
        return sum(review.was_reopened for review in self.reviews)

    @property
    def total_reopenings(self) -> int:
        return sum(review.reopen_count for review in self.reviews)

    @property
    def total_groups(self) -> int:
        return sum(review.total_groups for review in self.reviews)

    @property
    def approved(self) -> int:
        return sum(review.approved for review in self.reviews)

    @property
    def rejected(self) -> int:
        return sum(review.rejected for review in self.reviews)

    @property
    def deferred(self) -> int:
        return sum(review.deferred for review in self.reviews)

    @property
    def not_reviewed(self) -> int:
        return sum(review.not_reviewed for review in self.reviews)

    @property
    def unresolved(self) -> int:
        return self.deferred + self.not_reviewed


def generate_group_approval_report() -> GroupApprovalReport:
    """Generate a validated report from local audit history.

    Review IDs are discovered from creation events. Each review is
    reconstructed through the existing lifecycle validation service.

    Raises GroupApprovalError when group review history is malformed.
    No data is written.
    """
    events = load_audit_events()
    review_ids: set[str] = set()
    reopen_counts: dict[str, int] = {}

    group_event_types = {
        "group_review_created",
        "group_decision_recorded",
        "group_decision_changed",
        "group_review_completed",
        "group_review_reopened",
    }

    for event in events:
        if not isinstance(event, dict):
            raise GroupApprovalError("Invalid audit event structure.")

        event_type = event.get("event_type")

        if event_type not in group_event_types:
            continue

        details = event.get("details")

        if not isinstance(details, dict):
            raise GroupApprovalError(
                "Invalid group review audit event details."
            )

        onboarding_id = details.get("onboarding_id")

        if not isinstance(onboarding_id, str) or not onboarding_id.strip():
            raise GroupApprovalError(
                "Invalid onboarding ID in group review audit event."
            )

        if event_type == "group_review_created":
            review_ids.add(onboarding_id)

        elif event_type == "group_review_reopened":
            reopen_counts[onboarding_id] = (
                reopen_counts.get(onboarding_id, 0) + 1
            )

    summaries: list[GroupReviewSummary] = []

    for onboarding_id in sorted(review_ids):
        review = restore_group_approval_review(
            onboarding_id=onboarding_id
        )

        decisions = [
            group.decision for group in review.groups.values()
        ]

        summaries.append(
            GroupReviewSummary(
                onboarding_id=review.onboarding_id,
                employee_email=review.employee_email,
                status=review.status,
                total_groups=len(decisions),
                approved=decisions.count(GroupDecision.APPROVED),
                rejected=decisions.count(GroupDecision.REJECTED),
                deferred=decisions.count(GroupDecision.DEFERRED),
                not_reviewed=decisions.count(
                    GroupDecision.NOT_REVIEWED
                ),
                reopen_count=reopen_counts.get(onboarding_id, 0),
            )
        )

    orphaned_reopenings = set(reopen_counts) - review_ids

    if orphaned_reopenings:
        raise GroupApprovalError(
            "Reopening events exist without a review creation event."
        )

    return GroupApprovalReport(reviews=tuple(summaries))


CSV_REPORT_COLUMNS = (
    "onboarding_id",
    "employee_email",
    "status",
    "total_groups",
    "approved",
    "rejected",
    "deferred",
    "not_reviewed",
    "unresolved",
    "reopen_count",
    "was_reopened",
)


def _safe_csv_cell(value: object) -> object:
    """Prevent spreadsheet software from interpreting text as formulas."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def export_group_approval_report_csv(
    report: GroupApprovalReport, destination: str | Path
) -> Path:
    """Export a report to a new CSV file without changing audit records.

    Uses exclusive creation to avoid overwriting an existing file.
    Parent directories must already exist.
    """
    path = Path(destination)
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_REPORT_COLUMNS)
        for review in report.reviews:
            writer.writerow(
                [
                    _safe_csv_cell(review.onboarding_id),
                    _safe_csv_cell(review.employee_email),
                    _safe_csv_cell(review.status.value),
                    review.total_groups,
                    review.approved,
                    review.rejected,
                    review.deferred,
                    review.not_reviewed,
                    review.unresolved,
                    review.reopen_count,
                    review.was_reopened,
                ]
            )
    return path
