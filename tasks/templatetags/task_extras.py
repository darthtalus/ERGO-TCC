from django import template
from tasks.models import Task, TaskUser
from tasks.permissions import is_privileged

register = template.Library()

@register.filter
def executor_display(task, user):
    if not task:
        return "-"
    
    # Check if user is Admin or SuperAdmin
    if is_privileged(user):
        return task.executor
    
    # Check if user is the owner (creator) or a stakeholder
    is_owner = task.user == user
    is_stakeholder = task.tasks.filter(user=user, type=Task.UserType.STAKEHOLDER).exists()
    
    if is_owner or is_stakeholder:
        return task.executor

    # For other users
    executors = task.tasks.filter(type=Task.UserType.EXECUTOR)
    if executors.count() > 1:
        # If the current user is one of the executors, show only their name
        if executors.filter(user=user).exists():
            return user.first_name
        # If not an executor, they shouldn't see multiple executors
        return "-"
    
    return task.executor

@register.filter
def status_display(task):
    if not task:
        return []
    return task.tasks.filter(type=Task.UserType.EXECUTOR)

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for kwarg, value in kwargs.items():
        if value:
            query[kwarg] = value
        else:
            query.pop(kwarg, None)
    return query.urlencode()

@register.filter
def is_admin(user):
    return is_privileged(user)
