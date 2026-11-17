"""Authorization rules for the task workflow.

The original project spread authorization checks across views.  This module
centralizes the rules so the HTML views, Kanban and automated tests use the
same policy.
"""
from __future__ import annotations

from tasks.models import Task, TaskUser


PRIVILEGED_ROLES = {"ADMIN", "SUPERADMIN"}


def is_privileged(user) -> bool:
    """Return whether the account may exercise application-wide admin powers.

    Django superusers are always privileged, even when their custom ``role``
    field was not manually promoted after ``createsuperuser``.
    """
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) in PRIVILEGED_ROLES
        )
    )


def can_manage_task(user, task: Task) -> bool:
    """Only the creator or an administrator may edit/delete/manage roles."""
    return is_privileged(user) or task.user_id == getattr(user, "id", None)


def can_view_task(user, task: Task) -> bool:
    """Creators, administrators and assigned participants may see a task."""
    if can_manage_task(user, task):
        return True
    return task.tasks.filter(user=user).exists()


def can_change_assignment_status(user, assignment: TaskUser) -> bool:
    """Status changes are limited to executor assignments.

    The assigned executor may manage their own progress.  The task creator and
    administrators may pause, reactivate or cancel an executor assignment, but
    completion is intentionally handled by ``complete_assignment`` because it
    requires the executor's self-assessment.
    """
    if assignment.type != Task.UserType.EXECUTOR:
        return False
    return (
        is_privileged(user)
        or assignment.task.user_id == getattr(user, "id", None)
        or assignment.user_id == getattr(user, "id", None)
    )


def can_complete_assignment(user, assignment: TaskUser) -> bool:
    """A self-assessment can only be submitted by the assigned executor."""
    return (
        assignment.type == Task.UserType.EXECUTOR
        and assignment.user_id == getattr(user, "id", None)
    )


def can_evaluate_assignment(user, assignment: TaskUser) -> bool:
    """Stakeholders, the task creator and administrators may evaluate."""
    if assignment.type != Task.UserType.EXECUTOR:
        return False
    # Separation of duties: nobody may act as stakeholder/reviewer of their
    # own executor assignment, even when they also own the task or are admin.
    if assignment.user_id == getattr(user, "id", None):
        return False
    if is_privileged(user) or assignment.task.user_id == getattr(user, "id", None):
        return True
    return assignment.task.tasks.filter(
        user=user,
        type=Task.UserType.STAKEHOLDER,
    ).exists()
