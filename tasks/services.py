"""Transactional task workflow operations.

Keeping state transitions here prevents different screens from applying
incompatible rules.  All public functions expect model instances that may be
locked by their caller with ``select_for_update``.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from .models import Task, TaskRate, TaskUser
from .permissions import (
    can_change_assignment_status,
    can_complete_assignment,
    can_evaluate_assignment,
)


class TaskWorkflowError(ValueError):
    """Raised when a requested transition violates the workflow."""


def is_assignment_final(assignment: TaskUser) -> bool:
    """Return whether the collaboration workflow has finalized the assignment.

    The core ``tasks`` app intentionally avoids importing the optional
    ``upgrades`` models.  When the reverse relation is available, an APPROVED
    review freezes stakeholder evaluations so the audit snapshot and the live
    record cannot diverge after final approval.
    """
    reviews = getattr(assignment, "upgrade_reviews", None)
    return bool(reviews is not None and reviews.filter(status="APPROVED").exists())


def assignment_has_workflow_history(assignment: TaskUser) -> bool:
    """Return whether removing an assignment would destroy workflow evidence."""
    if assignment.rate.exists():
        return True
    reviews = getattr(assignment, "upgrade_reviews", None)
    if reviews is not None and reviews.exists():
        return True
    checklists = getattr(assignment, "start_checklists", None)
    if checklists is not None and checklists.exists():
        return True
    return False


def task_has_workflow_history(task: Task) -> bool:
    """Return whether deleting a task would erase execution/audit history."""
    for assignment in task.tasks.all():
        if assignment_has_workflow_history(assignment):
            return True
    comments = getattr(task, "upgrade_comments", None)
    if comments is not None and comments.exists():
        return True
    checklist_items = getattr(task, "operational_checklist_items", None)
    if checklist_items is not None and checklist_items.filter(is_completed=True).exists():
        return True
    return False


NON_FINAL_STATUS_VALUES = {
    Task.Status.DOING,
    Task.Status.PAUSED,
    Task.Status.CANCELED,
}

# DONE is deliberately absent.  Completion must pass through the assessment
# service below.  DONE -> DOING is reserved for a formal return-for-adjustment
# review in the collaboration workflow.
ALLOWED_STATUS_TRANSITIONS = {
    Task.Status.DOING: {Task.Status.DOING, Task.Status.PAUSED, Task.Status.CANCELED},
    Task.Status.PAUSED: {Task.Status.PAUSED, Task.Status.DOING, Task.Status.CANCELED},
    Task.Status.CANCELED: {Task.Status.CANCELED, Task.Status.DOING},
    Task.Status.DONE: {Task.Status.DONE},
    Task.Status.NONE: {Task.Status.DOING},
}


@dataclass(frozen=True)
class TransitionResult:
    old_status: str
    new_status: str


def change_assignment_status(*, actor, assignment: TaskUser, new_status: str) -> TransitionResult:
    if not can_change_assignment_status(actor, assignment):
        raise TaskWorkflowError("permission_denied")
    if new_status not in NON_FINAL_STATUS_VALUES:
        raise TaskWorkflowError("invalid_status")
    allowed = ALLOWED_STATUS_TRANSITIONS.get(assignment.status, set())
    if new_status not in allowed:
        raise TaskWorkflowError("invalid_transition")

    old_status = assignment.status
    if old_status != new_status:
        assignment.status = new_status
        assignment.save(update_fields=["status"])
    return TransitionResult(old_status=old_status, new_status=new_status)


@transaction.atomic
def complete_assignment(*, actor, assignment: TaskUser, assessment: dict) -> TaskRate:
    if not can_complete_assignment(actor, assignment):
        raise TaskWorkflowError("permission_denied")
    if assignment.status not in {Task.Status.DOING, Task.Status.PAUSED}:
        raise TaskWorkflowError("invalid_transition")

    rating, _ = TaskRate.objects.update_or_create(
        taskuser=assignment,
        user=actor,
        rate_type=TaskRate.RateType.SELF,
        defaults={
            "environment": assessment["environment"],
            "cognition": assessment["cognition"],
            "behavior": assessment["behavior"],
            "effectiveness": assessment["effectiveness"],
        },
    )
    # Save the assessment before changing the status.  If either write fails,
    # the surrounding transaction rolls back both operations.
    assignment.status = Task.Status.DONE
    assignment.save(update_fields=["status"])
    return rating


@transaction.atomic
def evaluate_assignment(*, actor, assignment: TaskUser, effectiveness: int) -> TaskRate:
    if not can_evaluate_assignment(actor, assignment):
        raise TaskWorkflowError("permission_denied")
    if is_assignment_final(assignment):
        raise TaskWorkflowError("final_approved")
    if assignment.status != Task.Status.DONE:
        raise TaskWorkflowError("not_completed")
    if not TaskRate.objects.filter(
        taskuser=assignment,
        user=assignment.user,
        rate_type=TaskRate.RateType.SELF,
    ).exists():
        raise TaskWorkflowError("missing_self_assessment")
    return TaskRate.objects.update_or_create(
        taskuser=assignment,
        user=actor,
        rate_type=TaskRate.RateType.STAKEHOLDER,
        defaults={
            "environment": None,
            "cognition": None,
            "behavior": None,
            "effectiveness": effectiveness,
        },
    )[0]


@transaction.atomic
def clear_stakeholder_evaluation(*, actor, assignment: TaskUser) -> int:
    if not can_evaluate_assignment(actor, assignment):
        raise TaskWorkflowError("permission_denied")
    if is_assignment_final(assignment):
        raise TaskWorkflowError("final_approved")
    deleted, _ = TaskRate.objects.filter(
        taskuser=assignment,
        user=actor,
        rate_type=TaskRate.RateType.STAKEHOLDER,
    ).delete()
    return deleted
