
"""Local Google Workspace group recommendation approval workflow.

All decisions are local and audit-backed. This module does not access
Google Workspace or modify group memberships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from src.audit import load_audit_events, record_audit_event
from src.group_catalog import GroupPolicy
from src.group_recommendations import GroupRecommendationResult


class GroupDecision(StrEnum):
    NOT_REVIEWED = "not_reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class GroupReviewStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class GroupApprovalError(ValueError):
    """Raised when a group review operation violates approval rules."""


@dataclass
class GroupApproval:
    group_email: str
    group_name: str
    policy: GroupPolicy
    reason: str
    decision: GroupDecision = GroupDecision.NOT_REVIEWED


@dataclass
class GroupApprovalReview:
    onboarding_id: str
    employee_email: str
    groups: dict[str, GroupApproval] = field(default_factory=dict)
    status: GroupReviewStatus = GroupReviewStatus.IN_PROGRESS

    @property
    def unresolved_groups(self) -> tuple[GroupApproval, ...]:
        return tuple(
            group
            for group in self.groups.values()
            if group.decision not in {
                GroupDecision.APPROVED,
                GroupDecision.REJECTED,
            }
        )

    @property
    def can_complete(self) -> bool:
        return bool(self.groups) and not self.unresolved_groups


def create_group_approval_review(
    *,
    onboarding_id: str,
    employee_email: str,
    recommendations: GroupRecommendationResult,
) -> GroupApprovalReview:
    """Create an in-memory review of actionable recommendations."""
    if not onboarding_id.strip():
        raise GroupApprovalError("Onboarding ID is required.")

    if not employee_email.strip():
        raise GroupApprovalError("Employee email is required.")

    groups: dict[str, GroupApproval] = {}

    for recommendation in recommendations.recommendations:
        if recommendation.inherited or recommendation.policy in {
            GroupPolicy.INHERITED,
            GroupPolicy.EXCLUDED,
        }:
            continue

        if recommendation.policy not in {
            GroupPolicy.AUTOMATIC,
            GroupPolicy.IT_APPROVAL,
            GroupPolicy.MANUAL_REVIEW,
        }:
            raise GroupApprovalError(
                f"Unsupported group policy: {recommendation.policy}"
            )

        email = recommendation.email.strip().casefold()

        if not email:
            raise GroupApprovalError("Group email cannot be empty.")

        if email in groups:
            raise GroupApprovalError(
                f"Duplicate group recommendation: {email}"
            )

        groups[email] = GroupApproval(
            group_email=email,
            group_name=recommendation.name,
            policy=recommendation.policy,
            reason=recommendation.reason,
        )

    return GroupApprovalReview(
        onboarding_id=onboarding_id.strip(),
        employee_email=employee_email.strip().casefold(),
        groups=groups,
    )


def start_group_approval_review(
    *,
    onboarding_id: str,
    employee_email: str,
    recommendations: GroupRecommendationResult,
    administrator_name: str,
) -> GroupApprovalReview:
    """Start a new audited review, rejecting existing onboarding IDs."""
    if not administrator_name.strip():
        raise GroupApprovalError("Administrator name is required.")

    review = create_group_approval_review(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        recommendations=recommendations,
    )

    for event in load_audit_events():
        if not isinstance(event, dict):
            raise GroupApprovalError("Invalid audit event structure.")

        if event.get("event_type") != "group_review_created":
            continue

        details = event.get("details")

        if not isinstance(details, dict):
            raise GroupApprovalError(
                "Invalid group review creation audit event."
            )

        if details.get("onboarding_id") == review.onboarding_id:
            raise GroupApprovalError(
                "A group approval review already exists "
                f"for onboarding ID: {review.onboarding_id}"
            )

    groups = [
        {
            "group_email": group.group_email,
            "group_name": group.group_name,
            "group_policy": group.policy.value,
            "reason": group.reason,
            "decision": group.decision.value,
        }
        for group in review.groups.values()
    ]

    record_audit_event(
        "group_review_created",
        employee_email=review.employee_email,
        details={
            "onboarding_id": review.onboarding_id,
            "administrator_name": administrator_name.strip(),
            "new_status": review.status.value,
            "total_groups": len(groups),
            "groups": groups,
        },
    )

    return review


def _restore_creation_event(
    event: dict,
    onboarding_id: str,
) -> GroupApprovalReview:
    """Reconstruct the initial review from its creation event."""
    details = event["details"]
    employee_email = event.get("employee_email")

    if not isinstance(employee_email, str) or not employee_email.strip():
        raise GroupApprovalError(
            "Invalid employee email in group review audit event."
        )

    if details.get("new_status") != GroupReviewStatus.IN_PROGRESS.value:
        raise GroupApprovalError("Invalid initial group review status.")

    saved_groups = details.get("groups")

    if not isinstance(saved_groups, list):
        raise GroupApprovalError(
            "Invalid group list in group review audit event."
        )

    if details.get("total_groups") != len(saved_groups):
        raise GroupApprovalError(
            "Group count does not match the creation audit event."
        )

    groups: dict[str, GroupApproval] = {}

    for saved_group in saved_groups:
        if not isinstance(saved_group, dict):
            raise GroupApprovalError(
                "Invalid group entry in creation audit event."
            )

        group_email = saved_group.get("group_email")
        group_name = saved_group.get("group_name")
        group_policy = saved_group.get("group_policy")
        reason = saved_group.get("reason")
        decision = saved_group.get("decision")

        if not isinstance(group_email, str) or not group_email.strip():
            raise GroupApprovalError(
                "Invalid group email in creation audit event."
            )

        if not isinstance(group_name, str):
            raise GroupApprovalError(
                "Invalid group name in creation audit event."
            )

        if not isinstance(reason, str):
            raise GroupApprovalError(
                "Invalid group reason in creation audit event."
            )

        try:
            policy = GroupPolicy(group_policy)
            restored_decision = GroupDecision(decision)
        except (ValueError, TypeError) as exc:
            raise GroupApprovalError(
                "Invalid group policy or decision in creation audit event."
            ) from exc

        if policy not in {
            GroupPolicy.AUTOMATIC,
            GroupPolicy.IT_APPROVAL,
            GroupPolicy.MANUAL_REVIEW,
        }:
            raise GroupApprovalError(
                "Non-actionable group in creation audit event."
            )

        if restored_decision is not GroupDecision.NOT_REVIEWED:
            raise GroupApprovalError(
                "Creation audit event contains a non-initial decision."
            )

        normalized_email = group_email.strip().casefold()

        if normalized_email != group_email:
            raise GroupApprovalError(
                "Group email is not normalized in creation audit event."
            )

        if normalized_email in groups:
            raise GroupApprovalError(
                f"Duplicate group in creation audit event: "
                f"{normalized_email}"
            )

        groups[normalized_email] = GroupApproval(
            group_email=normalized_email,
            group_name=group_name,
            policy=policy,
            reason=reason,
            decision=restored_decision,
        )

    return GroupApprovalReview(
        onboarding_id=onboarding_id,
        employee_email=employee_email,
        groups=groups,
        status=GroupReviewStatus.IN_PROGRESS,
    )


def _replay_decision_event(
    review: GroupApprovalReview,
    event: dict,
) -> None:
    """Apply one audited decision after validating its transition."""
    if review.status is GroupReviewStatus.COMPLETED:
        raise GroupApprovalError(
            "Decision event occurred after completion without reopening."
        )

    details = event["details"]
    event_type = event["event_type"]
    group_email = details.get("group_email")

    if not isinstance(group_email, str):
        raise GroupApprovalError(
            "Invalid group email in decision audit event."
        )

    group = review.groups.get(group_email)

    if group is None:
        raise GroupApprovalError(
            f"Unknown group in decision audit event: {group_email}"
        )

    try:
        previous_decision = GroupDecision(
            details.get("previous_decision")
        )
        new_decision = GroupDecision(
            details.get("new_decision")
        )
    except (ValueError, TypeError) as exc:
        raise GroupApprovalError(
            "Invalid decision in audit event."
        ) from exc

    if previous_decision is not group.decision:
        raise GroupApprovalError(
            "Decision history does not match previous state."
        )

    if new_decision is GroupDecision.NOT_REVIEWED:
        raise GroupApprovalError(
            "Cannot replay NOT_REVIEWED as a new decision."
        )

    if new_decision is previous_decision:
        raise GroupApprovalError(
            "Decision audit event does not change the decision."
        )

    if event_type == "group_decision_recorded":
        if previous_decision is not GroupDecision.NOT_REVIEWED:
            raise GroupApprovalError(
                "Initial decision event has an invalid previous state."
            )

    elif event_type == "group_decision_changed":
        if previous_decision is GroupDecision.NOT_REVIEWED:
            raise GroupApprovalError(
                "Changed decision event has no previous decision."
            )

        change_reason = details.get("change_reason")

        if not isinstance(change_reason, str) or not change_reason.strip():
            raise GroupApprovalError(
                "Decision change audit event requires a reason."
            )

    group.decision = new_decision


def _replay_completion_event(
    review: GroupApprovalReview,
    event: dict,
) -> None:
    """Validate completion against the decisions at that point in time."""
    details = event["details"]

    if review.status is not GroupReviewStatus.IN_PROGRESS:
        raise GroupApprovalError(
            "Review completion event has an invalid current status."
        )

    if (
        details.get("previous_status")
        != GroupReviewStatus.IN_PROGRESS.value
        or details.get("new_status")
        != GroupReviewStatus.COMPLETED.value
    ):
        raise GroupApprovalError(
            "Invalid completion status transition."
        )

    if details.get("total_groups") != len(review.groups):
        raise GroupApprovalError(
            "Invalid group count in completion audit event."
        )

    if not review.can_complete:
        raise GroupApprovalError(
            "Completion event contains unresolved groups."
        )

    approved = sorted(
        group.group_email
        for group in review.groups.values()
        if group.decision is GroupDecision.APPROVED
    )
    rejected = sorted(
        group.group_email
        for group in review.groups.values()
        if group.decision is GroupDecision.REJECTED
    )

    if (
        details.get("approved_groups") != approved
        or details.get("rejected_groups") != rejected
    ):
        raise GroupApprovalError(
            "Completion audit event does not match group decisions."
        )

    review.status = GroupReviewStatus.COMPLETED


def _replay_reopening_event(
    review: GroupApprovalReview,
    event: dict,
) -> None:
    """Reopen a completed review without changing existing decisions."""
    details = event["details"]

    if review.status is not GroupReviewStatus.COMPLETED:
        raise GroupApprovalError(
            "Reopening event requires a completed review."
        )

    if (
        details.get("previous_status")
        != GroupReviewStatus.COMPLETED.value
        or details.get("new_status")
        != GroupReviewStatus.IN_PROGRESS.value
    ):
        raise GroupApprovalError(
            "Invalid reopening status transition."
        )

    if details.get("total_groups") != len(review.groups):
        raise GroupApprovalError(
            "Invalid group count in reopening audit event."
        )

    reopen_reason = details.get("reopen_reason")

    if not isinstance(reopen_reason, str) or not reopen_reason.strip():
        raise GroupApprovalError(
            "Reopening audit event requires a reason."
        )

    review.status = GroupReviewStatus.IN_PROGRESS


def restore_group_approval_review(
    *,
    onboarding_id: str,
) -> GroupApprovalReview:
    """Restore a review by replaying its audit events in stored order.

    Replays decisions, completion, reopening, and subsequent changes.
    Invalid lifecycle transitions are rejected.
    """
    if not onboarding_id.strip():
        raise GroupApprovalError("Onboarding ID is required.")

    requested_id = onboarding_id.strip()
    relevant_events = []
    creation_events = []

    event_types = {
        "group_review_created",
        "group_decision_recorded",
        "group_decision_changed",
        "group_review_completed",
        "group_review_reopened",
    }

    for event in load_audit_events():
        if not isinstance(event, dict):
            raise GroupApprovalError("Invalid audit event structure.")

        event_type = event.get("event_type")

        if event_type not in event_types:
            continue

        details = event.get("details")

        if not isinstance(details, dict):
            if event_type == "group_review_created":
                raise GroupApprovalError(
                    "Invalid group review creation audit event."
                )
            raise GroupApprovalError(
                "Invalid group review audit event details."
            )

        if details.get("onboarding_id") != requested_id:
            continue

        relevant_events.append(event)

        if event_type == "group_review_created":
            creation_events.append(event)

    if not creation_events:
        raise GroupApprovalError(
            "No group approval review exists for onboarding ID: "
            f"{requested_id}"
        )

    if len(creation_events) != 1:
        raise GroupApprovalError(
            "Duplicate group review creation events for: "
            f"{requested_id}"
        )

    if relevant_events[0] is not creation_events[0]:
        raise GroupApprovalError(
            "Group review events occurred before creation."
        )

    review = _restore_creation_event(
        creation_events[0],
        requested_id,
    )

    for event in relevant_events[1:]:
        if event.get("employee_email") != review.employee_email:
            raise GroupApprovalError(
                "Employee email mismatch in group review audit event."
            )

        event_type = event["event_type"]

        if event_type in {
            "group_decision_recorded",
            "group_decision_changed",
        }:
            _replay_decision_event(review, event)

        elif event_type == "group_review_completed":
            _replay_completion_event(review, event)

        elif event_type == "group_review_reopened":
            _replay_reopening_event(review, event)

    return review


def record_group_decision(
    review: GroupApprovalReview,
    *,
    group_email: str,
    decision: GroupDecision,
    administrator_name: str,
    notes: str = "",
    change_reason: str = "",
) -> None:
    """Record a decision before changing its in-memory state."""
    if review.status is GroupReviewStatus.COMPLETED:
        raise GroupApprovalError(
            "Completed reviews must be reopened before changes."
        )

    email = group_email.strip().casefold()
    group = review.groups.get(email)

    if group is None:
        raise GroupApprovalError(
            f"Group is not eligible for approval: {email}"
        )

    if not administrator_name.strip():
        raise GroupApprovalError("Administrator name is required.")

    try:
        new_decision = GroupDecision(decision)
    except ValueError as exc:
        raise GroupApprovalError("Invalid group decision.") from exc

    if new_decision is GroupDecision.NOT_REVIEWED:
        raise GroupApprovalError(
            "NOT_REVIEWED cannot be selected as a decision."
        )

    previous_decision = group.decision

    if previous_decision is new_decision:
        raise GroupApprovalError(
            "The group already has this decision."
        )

    is_change = previous_decision is not GroupDecision.NOT_REVIEWED

    if is_change and not change_reason.strip():
        raise GroupApprovalError(
            "A reason is required when changing a previous decision."
        )

    event_type = (
        "group_decision_changed"
        if is_change
        else "group_decision_recorded"
    )

    record_audit_event(
        event_type,
        employee_email=review.employee_email,
        details={
            "onboarding_id": review.onboarding_id,
            "group_email": group.group_email,
            "group_name": group.group_name,
            "group_policy": group.policy.value,
            "previous_decision": previous_decision.value,
            "new_decision": new_decision.value,
            "administrator_name": administrator_name.strip(),
            "notes": notes.strip(),
            "change_reason": change_reason.strip(),
        },
    )

    group.decision = new_decision


def complete_group_approval_review(
    review: GroupApprovalReview,
    *,
    administrator_name: str,
    notes: str = "",
) -> None:
    """Complete a review only after all groups have final decisions."""
    if review.status is GroupReviewStatus.COMPLETED:
        raise GroupApprovalError(
            "This group approval review is already completed."
        )

    if not administrator_name.strip():
        raise GroupApprovalError("Administrator name is required.")

    if not review.can_complete:
        raise GroupApprovalError(
            "Every group must be approved or rejected before completion."
        )

    approved_groups = sorted(
        group.group_email
        for group in review.groups.values()
        if group.decision is GroupDecision.APPROVED
    )
    rejected_groups = sorted(
        group.group_email
        for group in review.groups.values()
        if group.decision is GroupDecision.REJECTED
    )

    record_audit_event(
        "group_review_completed",
        employee_email=review.employee_email,
        details={
            "onboarding_id": review.onboarding_id,
            "administrator_name": administrator_name.strip(),
            "notes": notes.strip(),
            "previous_status": review.status.value,
            "new_status": GroupReviewStatus.COMPLETED.value,
            "total_groups": len(review.groups),
            "approved_groups": approved_groups,
            "rejected_groups": rejected_groups,
        },
    )

    review.status = GroupReviewStatus.COMPLETED


def reopen_group_approval_review(
    review: GroupApprovalReview,
    *,
    administrator_name: str,
    reopen_reason: str,
    notes: str = "",
) -> None:
    """Reopen a completed review while preserving existing decisions."""
    if review.status is not GroupReviewStatus.COMPLETED:
        raise GroupApprovalError(
            "Only completed group approval reviews can be reopened."
        )

    if not administrator_name.strip():
        raise GroupApprovalError("Administrator name is required.")

    if not reopen_reason.strip():
        raise GroupApprovalError(
            "A reason is required to reopen a completed review."
        )

    record_audit_event(
        "group_review_reopened",
        employee_email=review.employee_email,
        details={
            "onboarding_id": review.onboarding_id,
            "administrator_name": administrator_name.strip(),
            "reopen_reason": reopen_reason.strip(),
            "notes": notes.strip(),
            "previous_status": GroupReviewStatus.COMPLETED.value,
            "new_status": GroupReviewStatus.IN_PROGRESS.value,
            "total_groups": len(review.groups),
        },
    )

    review.status = GroupReviewStatus.IN_PROGRESS
