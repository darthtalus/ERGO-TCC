import base64
import hashlib
import hmac
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean

from django.db import transaction
from django.db.models import Avg, Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import CustomUser
from tasks.models import Task, TaskRate, TaskUser
from user_aspects.models import Effectiveness, UserAspectHistory, UserAspects

from .models import (
    RecurringTaskOccurrence,
    RecurringTaskRule,
    SensorReading,
    TaskChecklistItem,
    TaskReview,
)


LOW_SCORE = 2.5
SCOPE_PERSONAL = 'personal'
SCOPE_ORGANIZATION = 'organization'


def is_privileged(user):
    return getattr(user, 'role', '') in ['ADMIN', 'SUPERADMIN'] or user.is_superuser


def resolve_analytics_scope(user, requested_scope=None):
    """Return a scope the current user is authorized to use."""
    if is_privileged(user) and requested_scope != SCOPE_PERSONAL:
        return SCOPE_ORGANIZATION
    return SCOPE_PERSONAL


def personal_task_filter(user):
    return Q(user=user) | Q(tasks__user=user)


def get_visible_tasks(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        return Task.objects.all()
    return Task.objects.filter(personal_task_filter(user)).distinct()


def get_visible_assignments(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        return TaskUser.objects.select_related('task', 'user').all()
    visible_task_ids = get_visible_tasks(user, scope=SCOPE_PERSONAL).values_list('id', flat=True)
    return (
        TaskUser.objects.select_related('task', 'user')
        .filter(Q(user=user) | Q(task_id__in=visible_task_ids))
        .distinct()
    )


def get_effectiveness_queryset(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        return Effectiveness.objects.all()
    return Effectiveness.objects.filter(user=user)


def get_rate_queryset(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        return TaskRate.objects.all()
    return TaskRate.objects.filter(Q(user=user) | Q(taskuser__user=user)).distinct()


def get_sensor_queryset(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        return SensorReading.objects.all()
    return SensorReading.objects.filter(user=user)


def average_dimension_by_effectiveness(effectiveness_items):
    ids = [item.id for item in effectiveness_items]
    if not ids:
        return {}
    history = (
        UserAspectHistory.objects
        .filter(effectiveness_id__in=ids)
        .values('effectiveness_id', 'dimension')
        .annotate(avg=Avg('parametrized'))
    )
    mapped = defaultdict(dict)
    for item in history:
        mapped[item['effectiveness_id']][item['dimension']] = item['avg'] or 0
    return mapped


def _daily_rows(effectiveness_qs, limit=14):
    days = list(
        effectiveness_qs.order_by('-day')
        .values_list('day', flat=True)
        .distinct()[:limit]
    )
    if not days:
        return []

    effectiveness_items = list(effectiveness_qs.filter(day__in=days).order_by('-day', 'user_id'))
    history_map = average_dimension_by_effectiveness(effectiveness_items)
    grouped = defaultdict(lambda: {
        'effectiveness': [],
        'environment': [],
        'cognition': [],
        'behavior': [],
    })
    dimension_keys = {
        UserAspects.Dimension.ENVIRONMENT: 'environment',
        UserAspects.Dimension.COGNITION: 'cognition',
        UserAspects.Dimension.BEHAVIOR: 'behavior',
    }
    for eff in effectiveness_items:
        grouped[eff.day]['effectiveness'].append(eff.effectiveness)
        values = history_map.get(eff.id, {})
        for dimension, key in dimension_keys.items():
            value = values.get(dimension)
            if value is not None:
                grouped[eff.day][key].append(value)

    rows = []
    for day in sorted(grouped.keys(), reverse=True):
        values = grouped[day]
        rows.append({
            'day': day,
            'effectiveness': round(mean(values['effectiveness']), 2) if values['effectiveness'] else 0,
            'environment': round(mean(values['environment']), 2) if values['environment'] else 0,
            'cognition': round(mean(values['cognition']), 2) if values['cognition'] else 0,
            'behavior': round(mean(values['behavior']), 2) if values['behavior'] else 0,
        })
    return rows


def _pending_review_count(assignments):
    latest_status = (
        TaskReview.objects
        .filter(taskuser_id=OuterRef('pk'))
        .order_by('-created_at', '-pk')
        .values('status')[:1]
    )
    return (
        assignments.filter(type=Task.UserType.EXECUTOR, status=Task.Status.DONE)
        .annotate(latest_review_status=Subquery(latest_status))
        .exclude(latest_review_status=TaskReview.Status.APPROVED)
        .count()
    )


def compute_dashboard(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    visible_assignments = get_visible_assignments(user, scope).filter(type=Task.UserType.EXECUTOR)
    visible_tasks = get_visible_tasks(user, scope)
    eff_qs = get_effectiveness_queryset(user, scope)
    rates_qs = get_rate_queryset(user, scope)

    eff_avg = eff_qs.aggregate(avg=Avg('effectiveness'))['avg'] or 0
    self_avg = rates_qs.filter(rate_type=TaskRate.RateType.SELF).aggregate(avg=Avg('effectiveness'))['avg'] or 0
    stakeholder_avg = rates_qs.filter(rate_type=TaskRate.RateType.STAKEHOLDER).aggregate(avg=Avg('effectiveness'))['avg'] or 0

    dim_rows = (
        UserAspectHistory.objects
        .filter(effectiveness__in=eff_qs)
        .values('dimension')
        .annotate(avg=Avg('parametrized'))
    )
    dim_map = {item['dimension']: item['avg'] or 0 for item in dim_rows}
    dimension_averages = {
        'environment': round(dim_map.get(UserAspects.Dimension.ENVIRONMENT, 0), 2),
        'cognition': round(dim_map.get(UserAspects.Dimension.COGNITION, 0), 2),
        'behavior': round(dim_map.get(UserAspects.Dimension.BEHAVIOR, 0), 2),
    }
    dimension_percentages = {
        key: min(100, max(0, int(value * 20)))
        for key, value in dimension_averages.items()
    }

    status_counts = visible_assignments.values('status').annotate(total=Count('id')).order_by('status')
    status_map = {item['status']: item['total'] for item in status_counts}

    cards = {
        'tasks': visible_tasks.count(),
        'assignments': visible_assignments.count(),
        'daily_effectiveness': round(eff_avg, 2),
        'self_effectiveness': round(self_avg, 2),
        'stakeholder_effectiveness': round(stakeholder_avg, 2),
        'pending_reviews': _pending_review_count(visible_assignments),
    }

    non_zero_dimensions = [(key, value) for key, value in dimension_averages.items() if value > 0]
    critical_dimension = min(non_zero_dimensions, key=lambda item: item[1]) if non_zero_dimensions else None

    return {
        'scope': scope,
        'cards': cards,
        'status_map': status_map,
        'dimension_averages': dimension_averages,
        'dimension_percentages': dimension_percentages,
        'critical_dimension': critical_dimension,
        'daily_rows': _daily_rows(eff_qs, limit=14),
    }


def compute_heatmap(user, scope=None):
    scope = resolve_analytics_scope(user, scope)
    cutoff = timezone.localdate() - timedelta(days=89)
    qs = get_effectiveness_queryset(user, scope).filter(day__gte=cutoff)
    by_weekday = defaultdict(list)
    for eff in qs.only('day', 'effectiveness'):
        by_weekday[eff.day.weekday()].append(eff.effectiveness)
    names = [_('Monday'), _('Tuesday'), _('Wednesday'), _('Thursday'), _('Friday'), _('Saturday'), _('Sunday')]
    return [
        {
            'weekday': name,
            'count': len(by_weekday.get(index, [])),
            'avg': round(mean(by_weekday[index]), 2) if by_weekday.get(index) else 0,
        }
        for index, name in enumerate(names)
    ]


def build_recommendations(user, scope=None, limit=10, dashboard_data=None):
    scope = resolve_analytics_scope(user, scope)
    dashboard_data = dashboard_data or compute_dashboard(user, scope)
    daily_rows = dashboard_data['daily_rows']
    recommendations = []

    if not daily_rows:
        recommendations.append({
            'level': 'info',
            'title': _('Start collecting daily records'),
            'body': _('No daily effectiveness records were found yet. Add daily records to unlock ergonomic recommendations.'),
        })
        return recommendations

    recent_effectiveness = [row['effectiveness'] for row in daily_rows[:5]]
    if recent_effectiveness and mean(recent_effectiveness) <= LOW_SCORE:
        recommendations.append({
            'level': 'danger',
            'title': _('Recent effectiveness is low'),
            'body': _('Recent records are below the desired range. Review workload, pauses, task clarity, and environmental conditions.'),
        })

    if len(daily_rows) >= 6:
        latest_avg = mean([row['effectiveness'] for row in daily_rows[:3]])
        previous_avg = mean([row['effectiveness'] for row in daily_rows[3:6]])
        if latest_avg + 0.75 < previous_avg:
            recommendations.append({
                'level': 'warning',
                'title': _('Effectiveness dropped recently'),
                'body': _('The last three daily averages are noticeably lower than the previous three. Check task difficulty, fatigue, and environment.'),
            })

    labels = {
        'environment': _('Environment'),
        'cognition': _('Cognition'),
        'behavior': _('Behavior'),
    }
    body_map = {
        'environment': _('Prioritize noise, lighting, temperature, air quality, and workspace adjustments.'),
        'cognition': _('Reduce interruptions, split complex tasks, improve instructions, and schedule focused work blocks.'),
        'behavior': _('Review posture, rhythm, breaks, and task routine. Use short recovery pauses.'),
    }
    for dimension, value in dashboard_data['dimension_averages'].items():
        if value and value <= LOW_SCORE:
            recommendations.append({
                'level': 'warning',
                'title': _('%(dimension)s dimension needs attention') % {'dimension': labels[dimension]},
                'body': body_map[dimension],
            })

    if scope == SCOPE_ORGANIZATION:
        difficult_tasks = TaskUser.objects.filter(
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
            task__difficulty__gte=4,
        )
    else:
        difficult_tasks = TaskUser.objects.filter(
            user=user,
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
            task__difficulty__gte=4,
        )
    for assignment in difficult_tasks.select_related('task')[:3]:
        recommendations.append({
            'level': 'info',
            'title': _('High difficulty task in progress'),
            'body': _('Task "%(task)s" has high difficulty. Consider a checklist, breaks, and stakeholder alignment before continuing.') % {'task': assignment.task.name},
        })

    for reading in get_sensor_queryset(user, scope).order_by('-captured_at')[:3]:
        if reading.noise_db is not None and float(reading.noise_db) >= 70:
            recommendations.append({
                'level': 'warning',
                'title': _('High noise reading'),
                'body': _('A recent sensor/manual reading indicated %(noise)s dB. Consider reducing noise exposure for focused work.') % {'noise': reading.noise_db},
            })
        if reading.temperature_c is not None and (float(reading.temperature_c) < 18 or float(reading.temperature_c) > 28):
            recommendations.append({
                'level': 'warning',
                'title': _('Temperature outside comfort range'),
                'body': _('A recent reading indicated %(temp)s °C. Review thermal comfort before complex tasks.') % {'temp': reading.temperature_c},
            })

    if not recommendations:
        recommendations.append({
            'level': 'success',
            'title': _('No critical ergonomic alert'),
            'body': _('Recent records do not show an obvious risk pattern. Keep collecting data to improve the analysis.'),
        })
    return recommendations[:limit]


def compute_divergences(user, scope=None, limit=15):
    scope = resolve_analytics_scope(user, scope)
    if scope == SCOPE_ORGANIZATION:
        assignments = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
    else:
        assignments = TaskUser.objects.filter(user=user, type=Task.UserType.EXECUTOR)

    rows = []
    for assignment in assignments.select_related('task', 'user').prefetch_related('rate'):
        rates = sorted(assignment.rate.all(), key=lambda item: (item.created_at, item.pk), reverse=True)
        self_rate = next((item for item in rates if item.rate_type == TaskRate.RateType.SELF), None)
        stakeholder_rate = next((item for item in rates if item.rate_type == TaskRate.RateType.STAKEHOLDER), None)
        if not self_rate or not stakeholder_rate:
            continue
        difference = abs((self_rate.effectiveness or 0) - (stakeholder_rate.effectiveness or 0))
        if difference >= 2:
            rows.append({
                'task': assignment.task,
                'executor': assignment.user,
                'self': self_rate.effectiveness,
                'stakeholder': stakeholder_rate.effectiveness,
                'difference': difference,
            })
    return sorted(rows, key=lambda item: item['difference'], reverse=True)[:limit]


def suggest_executors(requesting_user, task=None, limit=5):
    """Return a manager-only heuristic; never expose peer metrics to regular users."""
    if not is_privileged(requesting_user):
        return []

    users = list(CustomUser.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'))
    active_map = {
        item['user_id']: item['total']
        for item in TaskUser.objects.filter(
            type=Task.UserType.EXECUTOR,
            status__in=[Task.Status.DOING, Task.Status.PAUSED],
        ).values('user_id').annotate(total=Count('id'))
    }
    rate_map = defaultdict(dict)
    for item in TaskRate.objects.values('taskuser__user_id', 'rate_type').annotate(avg=Avg('effectiveness')):
        rate_map[item['taskuser__user_id']][item['rate_type']] = item['avg'] or 0

    rows = []
    for candidate in users:
        active_count = active_map.get(candidate.id, 0)
        self_avg = rate_map[candidate.id].get(TaskRate.RateType.SELF, 0)
        stakeholder_avg = rate_map[candidate.id].get(TaskRate.RateType.STAKEHOLDER, 0)
        historical_avg = stakeholder_avg or self_avg or 0
        score = historical_avg - (active_count * 0.25)
        if task and getattr(task, 'difficulty', 0) >= 4 and historical_avg < 3:
            score -= 0.75
        rows.append({
            'user': candidate,
            'active_count': active_count,
            'self_avg': round(self_avg, 2),
            'stakeholder_avg': round(stakeholder_avg, 2),
            'score': round(score, 2),
        })
    return sorted(rows, key=lambda item: item['score'], reverse=True)[:limit]


def build_ai_summary(user, scope=None, dashboard_data=None, recommendations=None):
    scope = resolve_analytics_scope(user, scope)
    dashboard_data = dashboard_data or compute_dashboard(user, scope)
    recommendations = recommendations or build_recommendations(user, scope, limit=3, dashboard_data=dashboard_data)
    critical = dashboard_data['critical_dimension']
    dimension_labels = {
        'environment': _('Environment'),
        'cognition': _('Cognition'),
        'behavior': _('Behavior'),
    }
    pieces = [
        _('Average daily effectiveness: %(value)s.') % {
            'value': dashboard_data['cards']['daily_effectiveness'],
        }
    ]
    if critical:
        pieces.append(_('Most critical ABC dimension: %(dimension)s with average %(value)s.') % {
            'dimension': dimension_labels.get(critical[0], critical[0]),
            'value': critical[1],
        })
    if dashboard_data['cards']['pending_reviews']:
        pieces.append(_('%(count)s completed assignment(s) are waiting for approval or return.') % {
            'count': dashboard_data['cards']['pending_reviews'],
        })
    if recommendations:
        pieces.append(_('Main recommendation: %(title)s') % {'title': recommendations[0]['title']})
    return ' '.join(pieces)


def build_visualization_data(user, dashboard_data=None, heatmap_rows=None, scope=None):
    scope = resolve_analytics_scope(user, scope)
    dashboard_data = dashboard_data or compute_dashboard(user, scope)
    heatmap_rows = heatmap_rows or compute_heatmap(user, scope)

    visible_tasks = get_visible_tasks(user, scope)
    visible_assignments = get_visible_assignments(user, scope)
    rates_qs = get_rate_queryset(user, scope).select_related('taskuser__task', 'taskuser__user')

    daily_rows = list(reversed(dashboard_data.get('daily_rows', [])))
    status_labels = {
        Task.Status.DOING: _('Doing'),
        Task.Status.PAUSED: _('Paused'),
        Task.Status.DONE: _('Done'),
        Task.Status.CANCELED: _('Canceled'),
        Task.Status.NONE: _('No status'),
    }
    status_map = dashboard_data.get('status_map', {})
    ordered_statuses = [Task.Status.DOING, Task.Status.PAUSED, Task.Status.DONE, Task.Status.CANCELED, Task.Status.NONE]
    status_keys = [key for key in ordered_statuses if key in status_map]

    difficulty_counts = {str(value): 0 for value in range(0, 6)}
    difficulty_counts['6+'] = 0
    for item in visible_tasks.values('difficulty').annotate(total=Count('id')):
        difficulty = int(item['difficulty'] or 0)
        bucket = str(difficulty) if difficulty <= 5 else '6+'
        difficulty_counts[bucket] += item['total']

    scatter = []
    max_difficulty = 5
    for rate in rates_qs.order_by('-created_at')[:250]:
        task = getattr(rate.taskuser, 'task', None)
        if not task:
            continue
        difficulty = int(task.difficulty or 0)
        max_difficulty = max(max_difficulty, difficulty)
        scatter.append({
            'x': difficulty,
            'y': int(rate.effectiveness or 0),
            'task': task.name,
            'type': rate.get_rate_type_display(),
        })

    role_counts = Counter(
        assignment.get_type_display()
        for assignment in visible_assignments.select_related('task', 'user')
    )

    return {
        'daily_effectiveness': {
            'labels': [row['day'].strftime('%d/%m') for row in daily_rows],
            'effectiveness': [row['effectiveness'] for row in daily_rows],
            'environment': [row['environment'] for row in daily_rows],
            'cognition': [row['cognition'] for row in daily_rows],
            'behavior': [row['behavior'] for row in daily_rows],
        },
        'abc_bar': {
            'labels': [_('Environment'), _('Cognition'), _('Behavior')],
            'values': [
                dashboard_data['dimension_averages']['environment'],
                dashboard_data['dimension_averages']['cognition'],
                dashboard_data['dimension_averages']['behavior'],
            ],
        },
        'status_doughnut': {
            'labels': [str(status_labels.get(key, key)) for key in status_keys],
            'values': [status_map.get(key, 0) for key in status_keys],
        },
        'weekday_bar': {
            'labels': [row['weekday'] for row in heatmap_rows],
            'values': [row['avg'] for row in heatmap_rows],
            'counts': [row['count'] for row in heatmap_rows],
        },
        'difficulty_histogram': {
            'labels': [_('Not informed'), '1', '2', '3', '4', '5', _('6 or more')],
            'values': [difficulty_counts[str(value)] for value in range(0, 6)] + [difficulty_counts['6+']],
        },
        'difficulty_effectiveness_scatter': {
            'points': scatter,
            'x_max': max_difficulty,
        },
        'role_distribution': {
            'labels': list(role_counts.keys()),
            'values': list(role_counts.values()),
        },
    }


def checklist_recommendations(cleaned_data):
    failed = [key for key, value in cleaned_data.items() if value is False]
    recommendations = []
    if 'environment_ok' in failed:
        recommendations.append(_('Review temperature, workspace, ventilation, and physical comfort.'))
    if 'lighting_ok' in failed:
        recommendations.append(_('Improve lighting or reduce glare before starting.'))
    if 'noise_ok' in failed:
        recommendations.append(_('Reduce noise, use headphones, or move focus tasks to a quieter period.'))
    if 'fatigue_low' in failed:
        recommendations.append(_('Use a short pause, hydrate, and split the task into smaller blocks.'))
    if 'clarity_ok' in failed:
        recommendations.append(_('Ask for task clarification before execution.'))
    if 'acceptance_criteria_ok' in failed:
        recommendations.append(_('Confirm the acceptance criteria with the stakeholder.'))
    return len(failed), '\n'.join(recommendations)


@transaction.atomic
def create_task_from_template(template, owner=None):
    owner = owner or template.owner
    task = Task.objects.create(
        name=template.name,
        description=template.description or template.name,
        dias=template.dias,
        horas=template.horas,
        difficulty=template.difficulty,
        user=owner,
    )
    checklist_lines = [line.strip() for line in template.checklist.splitlines() if line.strip()]
    TaskChecklistItem.objects.bulk_create([
        TaskChecklistItem(task=task, text=line[:500], position=index)
        for index, line in enumerate(checklist_lines, start=1)
    ])
    return task


def generate_due_recurring_tasks(owner=None, max_occurrences_per_rule=366):
    """Generate all due occurrences safely and idempotently."""
    today = timezone.localdate()
    created_tasks = []

    with transaction.atomic():
        rules = (
            RecurringTaskRule.objects.select_for_update()
            .filter(is_active=True, next_run__lte=today)
            .select_related('template', 'owner')
            .order_by('pk')
        )
        if owner is not None:
            rules = rules.filter(owner=owner)

        for rule in rules:
            if rule.anchor_day is None:
                rule.anchor_day = rule.next_run.day
            scheduled_for = rule.next_run
            generated_count = 0
            while scheduled_for <= today and generated_count < max_occurrences_per_rule:
                occurrence, _ = RecurringTaskOccurrence.objects.get_or_create(
                    rule=rule,
                    scheduled_for=scheduled_for,
                )
                if occurrence.task_id is None:
                    task = create_task_from_template(rule.template, owner=rule.owner)
                    occurrence.task = task
                    occurrence.save(update_fields=['task'])
                    created_tasks.append(task)
                scheduled_for = rule.next_date_after(scheduled_for)
                generated_count += 1

            rule.next_run = scheduled_for
            rule.save(update_fields=['next_run', 'anchor_day'])

    return created_tasks


def pseudonymized_user_label(user, salt, prefix='U'):
    """Create a non-sequential, export-specific pseudonym."""
    digest = hmac.new(salt, str(user.pk).encode('utf-8'), hashlib.sha256).digest()
    label = base64.b32encode(digest[:7]).decode('ascii').rstrip('=')
    return f'{prefix}-{label}'
