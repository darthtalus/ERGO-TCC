import csv
import json
import secrets
from io import BytesIO
from pathlib import Path
from statistics import mean

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from tasks.models import Task, TaskRate, TaskUser
from tasks.permissions import (
    can_change_assignment_status as core_can_change_assignment_status,
    can_evaluate_assignment as core_can_evaluate_assignment,
)
from tasks.services import (
    ALLOWED_STATUS_TRANSITIONS,
    TaskWorkflowError,
    change_assignment_status,
)
from user_aspects.models import Effectiveness, UserAspects

from .forms import (
    RecurringTaskRuleForm,
    SensorReadingForm,
    TaskCommentForm,
    TaskStartChecklistForm,
    TaskTemplateForm,
)
from .models import (
    RecurringTaskRule,
    SensorApiToken,
    SensorReading,
    TaskChecklistItem,
    TaskComment,
    TaskReview,
    TaskStartChecklist,
    TaskTemplate,
)
from .services import (
    SCOPE_ORGANIZATION,
    build_ai_summary,
    build_recommendations,
    build_visualization_data,
    checklist_recommendations,
    compute_dashboard,
    compute_divergences,
    compute_heatmap,
    create_task_from_template,
    generate_due_recurring_tasks,
    get_effectiveness_queryset,
    get_sensor_queryset,
    get_visible_tasks,
    is_privileged,
    pseudonymized_user_label,
    resolve_analytics_scope,
    suggest_executors,
)


def can_access_task(user, task):
    return (
        is_privileged(user)
        or task.user_id == user.id
        or task.tasks.filter(user=user).exists()
    )


def can_update_assignment_status(user, assignment):
    return core_can_change_assignment_status(user, assignment)


def can_answer_checklist(user, assignment):
    return (
        assignment.type == Task.UserType.EXECUTOR
        and assignment.user_id == user.id
        and assignment.status in {Task.Status.DOING, Task.Status.PAUSED}
    )


def can_review_assignment(user, assignment):
    return core_can_evaluate_assignment(user, assignment)


def can_update_operational_checklist(user, task):
    return (
        is_privileged(user)
        or task.user_id == user.id
        or task.tasks.filter(user=user, type=Task.UserType.EXECUTOR).exists()
    )


def _review_evaluation_snapshot(assignment):
    """Return an immutable JSON-safe copy of evaluations for audit history."""
    self_rating = assignment.rate.filter(
        rate_type=TaskRate.RateType.SELF,
        user=assignment.user,
    ).order_by('-created_at', '-pk').first()
    stakeholder_ratings = list(
        assignment.rate.filter(rate_type=TaskRate.RateType.STAKEHOLDER)
        .select_related('user')
        .order_by('created_at', 'pk')
    )
    return {
        'task': {
            'id': assignment.task_id,
            'name': assignment.task.name,
            'description': assignment.task.description,
            'dias': assignment.task.dias,
            'horas': assignment.task.horas,
            'difficulty': assignment.task.difficulty,
            'owner_user_id': assignment.task.user_id,
        },
        'assignment': {
            'id': assignment.pk,
            'executor_user_id': assignment.user_id,
            'type': assignment.type,
            'status': assignment.status,
        },
        'executor_user_id': assignment.user_id,
        'self_assessment': (
            {
                'environment': self_rating.environment,
                'cognition': self_rating.cognition,
                'behavior': self_rating.behavior,
                'effectiveness': self_rating.effectiveness,
                'rated_by_user_id': self_rating.user_id,
                'created_at': self_rating.created_at.isoformat() if self_rating.created_at else None,
                'updated_at': self_rating.updated_at.isoformat() if self_rating.updated_at else None,
            }
            if self_rating else None
        ),
        'stakeholder_assessments': [
            {
                'effectiveness': rating.effectiveness,
                'rated_by_user_id': rating.user_id,
                'created_at': rating.created_at.isoformat() if rating.created_at else None,
                'updated_at': rating.updated_at.isoformat() if rating.updated_at else None,
            }
            for rating in stakeholder_ratings
        ],
    }


def _scope_from_request(request):
    return resolve_analytics_scope(request.user, request.GET.get('scope'))


def _scope_query(scope):
    return f'?scope={scope}'


@login_required
def dashboard(request):
    scope = _scope_from_request(request)
    context = compute_dashboard(request.user, scope)
    heatmap_rows = compute_heatmap(request.user, scope)
    recommendations = build_recommendations(
        request.user,
        scope,
        dashboard_data=context,
    )
    context.update({
        'scope': scope,
        'scope_query': _scope_query(scope),
        'can_use_organization_scope': is_privileged(request.user),
        'recommendations': recommendations,
        'heatmap_rows': heatmap_rows,
        'divergences': compute_divergences(request.user, scope),
        'suggested_executors': (
            suggest_executors(request.user, limit=5)
            if scope == SCOPE_ORGANIZATION
            else []
        ),
        'show_executor_suggestions': is_privileged(request.user) and scope == SCOPE_ORGANIZATION,
        'ai_summary': build_ai_summary(
            request.user,
            scope,
            dashboard_data=context,
            recommendations=recommendations,
        ),
        'recent_sensors': get_sensor_queryset(request.user, scope).select_related('user').order_by('-captured_at')[:5],
        'chart_data': build_visualization_data(request.user, context, heatmap_rows, scope),
    })
    return render(request, 'upgrades/dashboard.html', context)


@login_required
def kanban(request):
    assignments = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
    if not is_privileged(request.user):
        assignments = assignments.filter(
            Q(user=request.user)
            | Q(task__user=request.user)
            | Q(task__tasks__user=request.user, task__tasks__type=Task.UserType.STAKEHOLDER)
        ).distinct()
    assignments = list(assignments.select_related('task', 'user').order_by('-task__created_at', 'pk'))

    columns = [
        {'key': Task.Status.DOING, 'label': _('Doing'), 'items': []},
        {'key': Task.Status.PAUSED, 'label': _('Paused'), 'items': []},
        {'key': Task.Status.DONE, 'label': _('Done'), 'items': []},
        {'key': Task.Status.CANCELED, 'label': _('Canceled'), 'items': []},
    ]
    by_key = {column['key']: column for column in columns}
    labels = dict(Task.Status.choices)
    for assignment in assignments:
        allowed = ALLOWED_STATUS_TRANSITIONS.get(assignment.status, set()) & {
            Task.Status.DOING, Task.Status.PAUSED, Task.Status.CANCELED,
        }
        assignment.status_choices = [(value, labels[value]) for value in allowed]
        assignment.can_edit_status = bool(
            can_update_assignment_status(request.user, assignment)
            and assignment.status != Task.Status.DONE
            and assignment.status_choices
        )
        by_key.get(assignment.status, by_key[Task.Status.DOING])['items'].append(assignment)
    return render(request, 'upgrades/kanban.html', {'columns': columns})


@login_required
@require_POST
@transaction.atomic
def kanban_update(request):
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=request.POST.get('taskuser_id'),
    )
    try:
        change_assignment_status(
            actor=request.user,
            assignment=assignment,
            new_status=request.POST.get('status'),
        )
    except TaskWorkflowError as exc:
        if str(exc) == 'permission_denied':
            raise PermissionDenied
        messages.error(request, _('This status transition is not allowed.'))
        return redirect('upgrades_kanban')
    messages.success(request, _('Task status updated from Kanban.'))
    return redirect('upgrades_kanban')


@login_required
def task_collaboration(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not can_access_task(request.user, task):
        raise PermissionDenied

    assignments = list(
        task.tasks.select_related('user')
        .prefetch_related(
            'rate',
            Prefetch(
                'upgrade_reviews',
                queryset=TaskReview.objects.select_related('reviewed_by').order_by('-created_at', '-pk'),
                to_attr='prefetched_reviews',
            ),
            Prefetch(
                'start_checklists',
                queryset=TaskStartChecklist.objects.select_related('answered_by').order_by('-created_at', '-pk'),
                to_attr='prefetched_checklists',
            ),
        )
        .order_by('type', 'user__first_name', 'user__username')
    )
    for assignment in assignments:
        assignment.latest_review = assignment.prefetched_reviews[0] if assignment.prefetched_reviews else None
        assignment.latest_checklist = assignment.prefetched_checklists[0] if assignment.prefetched_checklists else None
        assignment.can_answer_checklist = can_answer_checklist(request.user, assignment)
        assignment.can_review = can_review_assignment(request.user, assignment)
        if assignment.can_answer_checklist:
            assignment.checklist_form = TaskStartChecklistForm(prefix=f'checklist-{assignment.pk}')

    context = {
        'task': task,
        'assignments': assignments,
        'comments': task.upgrade_comments.select_related('user').all(),
        'comment_form': TaskCommentForm(),
        'operational_checklist_items': task.operational_checklist_items.select_related('completed_by').all(),
        'can_update_operational_checklist': can_update_operational_checklist(request.user, task),
    }
    return render(request, 'upgrades/task_collaboration.html', context)


@login_required
@require_POST
@transaction.atomic
def add_comment(request, task_id):
    # Lock the task so comments cannot race with guarded task deletion.
    task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)
    if not can_access_task(request.user, task):
        raise PermissionDenied
    form = TaskCommentForm(request.POST, request.FILES)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.user = request.user
        comment.save()
        messages.success(request, _('Comment added.'))
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect('upgrades_task_collaboration', task_id=task.id)


@login_required
def download_attachment(request, comment_id):
    comment = get_object_or_404(TaskComment.objects.select_related('task'), pk=comment_id)
    if not can_access_task(request.user, comment.task):
        raise PermissionDenied
    if not comment.attachment:
        raise Http404

    filename = Path(comment.attachment.name).name
    try:
        file_handle = comment.attachment.open('rb')
    except FileNotFoundError:
        # Compatibility fallback for attachments saved by older versions in MEDIA_ROOT.
        legacy_path = (Path(settings.MEDIA_ROOT) / comment.attachment.name).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if media_root not in legacy_path.parents or not legacy_path.exists():
            raise Http404
        file_handle = legacy_path.open('rb')

    response = FileResponse(file_handle, as_attachment=True, filename=filename)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_POST
@transaction.atomic
def review_assignment(request, taskuser_id):
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=taskuser_id,
    )
    if not can_review_assignment(request.user, assignment):
        raise PermissionDenied
    if assignment.status != Task.Status.DONE:
        messages.error(request, _('Only completed executor assignments can be reviewed.'))
        return redirect('upgrades_task_collaboration', task_id=assignment.task_id)
    if not assignment.rate.filter(
        rate_type=TaskRate.RateType.SELF,
        user=assignment.user,
    ).exists():
        messages.error(request, _('A valid executor self-assessment is required before review.'))
        return redirect('upgrades_task_collaboration', task_id=assignment.task_id)
    latest_review = assignment.upgrade_reviews.order_by('-created_at', '-pk').first()
    if latest_review and latest_review.status == TaskReview.Status.APPROVED:
        messages.info(request, _('This assignment has already been approved and is final.'))
        return redirect('upgrades_task_collaboration', task_id=assignment.task_id)

    status = request.POST.get('status')
    comment = request.POST.get('comment', '')[:2000]
    if status not in TaskReview.Status.values:
        messages.error(request, _('Invalid review status.'))
        return redirect('upgrades_task_collaboration', task_id=assignment.task_id)

    if status == TaskReview.Status.APPROVED:
        stakeholder_ids = assignment.task.tasks.filter(type=Task.UserType.STAKEHOLDER).values_list('user_id', flat=True)
        if stakeholder_ids.exists() and not assignment.rate.filter(
            rate_type=TaskRate.RateType.STAKEHOLDER,
            user_id__in=stakeholder_ids,
        ).exists():
            messages.error(request, _('A stakeholder evaluation is required before approval.'))
            return redirect('upgrades_task_collaboration', task_id=assignment.task_id)

    cycle_number = assignment.upgrade_reviews.filter(
        status=TaskReview.Status.RETURNED,
    ).count() + 1
    TaskReview.objects.create(
        taskuser=assignment,
        reviewed_by=request.user,
        status=status,
        comment=comment,
        cycle_number=cycle_number,
        evaluation_snapshot=_review_evaluation_snapshot(assignment),
    )
    if status == TaskReview.Status.APPROVED:
        messages.success(request, _('Assignment approved.'))
    elif status == TaskReview.Status.RETURNED:
        # A new execution cycle requires a fresh stakeholder evaluation.
        assignment.rate.filter(rate_type=TaskRate.RateType.STAKEHOLDER).delete()
        assignment.status = Task.Status.DOING
        assignment.save(update_fields=['status'])
        messages.warning(request, _('Assignment returned for adjustments and moved back to Doing.'))
    else:
        messages.info(request, _('Review marked as pending.'))
    return redirect('upgrades_task_collaboration', task_id=assignment.task_id)


@login_required
@require_POST
@transaction.atomic
def add_checklist(request, taskuser_id):
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=taskuser_id,
    )
    if not can_answer_checklist(request.user, assignment):
        raise PermissionDenied
    form = TaskStartChecklistForm(request.POST, prefix=f'checklist-{assignment.pk}')
    if form.is_valid():
        risk_score, recommendations = checklist_recommendations(form.cleaned_data)
        checklist = form.save(commit=False)
        checklist.taskuser = assignment
        checklist.answered_by = request.user
        checklist.risk_score = risk_score
        checklist.recommendations = recommendations
        checklist.save()
        if risk_score >= 3:
            messages.warning(request, _('Checklist saved with high ergonomic risk. Review the recommendations before continuing.'))
        else:
            messages.success(request, _('Checklist saved.'))
    else:
        messages.error(request, _('Could not save checklist.'))
    return redirect('upgrades_task_collaboration', task_id=assignment.task_id)


@login_required
@require_POST
def toggle_operational_checklist(request, item_id):
    item = get_object_or_404(TaskChecklistItem.objects.select_related('task'), pk=item_id)
    if not can_update_operational_checklist(request.user, item.task):
        raise PermissionDenied
    completed = request.POST.get('completed') in {'1', 'true', 'on', 'yes'}
    item.is_completed = completed
    item.completed_by = request.user if completed else None
    item.completed_at = timezone.now() if completed else None
    item.save(update_fields=['is_completed', 'completed_by', 'completed_at'])
    messages.success(request, _('Task checklist updated.'))
    return redirect('upgrades_task_collaboration', task_id=item.task_id)


@login_required
def templates_view(request):
    form = TaskTemplateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        template = form.save(commit=False)
        template.owner = request.user
        template.save()
        messages.success(request, _('Task template created.'))
        return redirect('upgrades_templates')
    templates = TaskTemplate.objects.filter(owner=request.user).order_by('name')
    return render(request, 'upgrades/templates.html', {'form': form, 'templates': templates})


@login_required
@require_POST
def create_from_template(request, template_id):
    template = get_object_or_404(TaskTemplate, pk=template_id, owner=request.user)
    task = create_task_from_template(template, owner=request.user)
    messages.success(request, _('Task created from template, including its checklist. Add executors and stakeholders next.'))
    return redirect('tasks_roles', task_id=task.id)


@login_required
def recurring_view(request):
    form = RecurringTaskRuleForm(request.POST or None, owner=request.user)
    if request.method == 'POST' and form.is_valid():
        rule = form.save(commit=False)
        rule.owner = request.user
        rule.save()
        messages.success(request, _('Recurring rule saved.'))
        return redirect('upgrades_recurring')
    rules = RecurringTaskRule.objects.filter(owner=request.user).select_related('template').order_by('next_run')
    return render(request, 'upgrades/recurring.html', {
        'form': form,
        'rules': rules,
        'has_templates': TaskTemplate.objects.filter(owner=request.user).exists(),
    })


@login_required
@require_POST
def run_due_recurring(request):
    created = generate_due_recurring_tasks(owner=request.user)
    messages.success(request, _('%(count)s recurring task(s) generated.') % {'count': len(created)})
    return redirect('upgrades_recurring')


@login_required
def sensors_view(request):
    form = SensorReadingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        sensor = form.save(commit=False)
        sensor.user = request.user
        sensor.save()
        messages.success(request, _('Sensor/manual reading saved.'))
        return redirect('upgrades_sensors')

    api_token = SensorApiToken.objects.filter(user=request.user).first()
    new_api_key = request.session.pop('new_sensor_api_key', None)
    readings = SensorReading.objects.filter(user=request.user).order_by('-captured_at')[:50]
    return render(request, 'upgrades/sensors.html', {
        'form': form,
        'readings': readings,
        'api_token': api_token,
        'new_api_key': new_api_key,
    })


@login_required
@require_POST
def generate_sensor_token(request):
    _, raw_key = SensorApiToken.issue_for_user(request.user)
    request.session['new_sensor_api_key'] = raw_key
    messages.success(request, _('A new sensor API key was generated. Copy it now; it will only be shown once.'))
    return redirect('upgrades_sensors')


@login_required
@require_POST
def revoke_sensor_token(request):
    SensorApiToken.objects.filter(user=request.user).update(is_active=False)
    messages.success(request, _('The sensor API key was revoked.'))
    return redirect('upgrades_sensors')


@login_required
def report_pdf(request):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    scope = _scope_from_request(request)
    dashboard_data = compute_dashboard(request.user, scope)
    heatmap_rows = compute_heatmap(request.user, scope)
    chart_data = build_visualization_data(request.user, dashboard_data, heatmap_rows, scope)
    recommendations = build_recommendations(request.user, scope, limit=5, dashboard_data=dashboard_data)
    divergences = compute_divergences(request.user, scope, limit=5)

    card_labels = {
        'tasks': _('Visible tasks'),
        'assignments': _('Executor assignments'),
        'daily_effectiveness': _('Average daily effectiveness'),
        'self_effectiveness': _('Average self-assessment'),
        'stakeholder_effectiveness': _('Average stakeholder assessment'),
        'pending_reviews': _('Pending reviews'),
    }

    buffer = BytesIO()
    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.95, str(_('ERGO - Ergonomic Analysis Report')), fontsize=18, weight='bold')
        fig.text(0.08, 0.91, f"{_('Generated at')}: {timezone.localtime().strftime('%d/%m/%Y %H:%M')}", fontsize=10)
        scope_label = _('Organization') if scope == SCOPE_ORGANIZATION else _('Personal')
        fig.text(0.08, 0.87, f"{_('Scope')}: {scope_label}", fontsize=11)
        fig.text(0.08, 0.84, f"{_('User')}: {request.user.get_full_name() or request.user.username}", fontsize=11)

        y = 0.79
        fig.text(0.08, y, str(_('Executive summary')), fontsize=14, weight='bold')
        y -= 0.035
        for key, value in dashboard_data['cards'].items():
            fig.text(0.10, y, f'- {card_labels.get(key, key)}: {value}', fontsize=10)
            y -= 0.025

        y -= 0.02
        fig.text(0.08, y, str(_('Recommendations')), fontsize=14, weight='bold')
        y -= 0.035
        for recommendation in recommendations:
            fig.text(0.10, y, f"- {recommendation['title']}: {recommendation['body'][:115]}", fontsize=9, wrap=True)
            y -= 0.055

        y -= 0.01
        fig.text(0.08, y, str(_('Relevant divergences')), fontsize=14, weight='bold')
        y -= 0.035
        if divergences:
            for item in divergences:
                text = _('%(task)s: self %(self)s vs stakeholder %(stakeholder)s (difference %(difference)s)') % {
                    'task': item['task'].name,
                    'self': item['self'],
                    'stakeholder': item['stakeholder'],
                    'difference': item['difference'],
                }
                fig.text(0.10, y, f'- {text}', fontsize=9)
                y -= 0.03
        else:
            fig.text(0.10, y, str(_('No divergence greater than or equal to 2 was found.')), fontsize=9)

        fig.text(0.08, 0.05, str(_('Exploratory report generated from ERGO rules and visual analytics; it is not a clinical diagnosis.')), fontsize=8)
        plt.axis('off')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        daily = chart_data['daily_effectiveness']
        if daily['labels']:
            fig = plt.figure(figsize=(8.27, 5))
            plt.plot(daily['labels'], daily['effectiveness'], marker='o', label=str(_('Effectiveness')))
            plt.plot(daily['labels'], daily['environment'], marker='o', label=str(_('Environment')))
            plt.plot(daily['labels'], daily['cognition'], marker='o', label=str(_('Cognition')))
            plt.plot(daily['labels'], daily['behavior'], marker='o', label=str(_('Behavior')))
            plt.title(str(_('Trend: effectiveness and ABC dimensions')))
            plt.ylim(0, 5.5)
            plt.xlabel(str(_('Date')))
            plt.ylabel(str(_('Score')))
            plt.xticks(rotation=45)
            plt.grid(True, linestyle='--', alpha=0.4)
            plt.legend()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

        abc = chart_data['abc_bar']
        fig = plt.figure(figsize=(8.27, 5))
        plt.bar(abc['labels'], abc['values'])
        plt.title(str(_('Bar chart: ABC averages')))
        plt.ylim(0, 5.5)
        plt.ylabel(str(_('Average Score')))
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        status = chart_data['status_doughnut']
        if any(status['values']):
            fig = plt.figure(figsize=(8.27, 5))
            plt.pie(status['values'], labels=status['labels'], autopct='%1.0f%%')
            plt.title(str(_('Pie chart: task status distribution')))
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

        weekday = chart_data['weekday_bar']
        fig = plt.figure(figsize=(8.27, 5))
        plt.bar(weekday['labels'], weekday['values'])
        plt.title(str(_('Bar chart: effectiveness by weekday')))
        plt.ylim(0, 5.5)
        plt.ylabel(str(_('Average Score')))
        plt.xticks(rotation=25)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        scatter_data = chart_data['difficulty_effectiveness_scatter']
        scatter = scatter_data['points']
        if scatter:
            fig = plt.figure(figsize=(8.27, 5))
            plt.scatter([point['x'] for point in scatter], [point['y'] for point in scatter])
            plt.title(str(_('Scatter plot: difficulty vs effectiveness')))
            plt.xlabel(str(_('Difficulty')))
            plt.ylabel(str(_('Effectiveness')))
            plt.xlim(-0.5, scatter_data.get('x_max', 5) + 0.5)
            plt.ylim(0.5, 5.5)
            plt.grid(True, linestyle='--', alpha=0.4)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ergo_analise_{timezone.localdate()}.pdf"'
    return response


@login_required
def pseudonymized_csv(request):
    scope = _scope_from_request(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ergo_pseudonimizado_{timezone.localdate()}.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['pseudonymous_user', 'date', 'daily_effectiveness', 'avg_environment', 'avg_cognition', 'avg_behavior'])

    export_salt = secrets.token_bytes(32)
    qs = get_effectiveness_queryset(request.user, scope)
    for effectiveness in qs.select_related('user').prefetch_related('history').order_by('user_id', 'day'):
        dimension_values = {
            UserAspects.Dimension.ENVIRONMENT: [],
            UserAspects.Dimension.COGNITION: [],
            UserAspects.Dimension.BEHAVIOR: [],
        }
        for history in effectiveness.history.all():
            if history.dimension in dimension_values:
                dimension_values[history.dimension].append(history.parametrized)
        writer.writerow([
            pseudonymized_user_label(effectiveness.user, export_salt),
            effectiveness.day,
            effectiveness.effectiveness,
            round(mean(dimension_values[UserAspects.Dimension.ENVIRONMENT]), 2) if dimension_values[UserAspects.Dimension.ENVIRONMENT] else 0,
            round(mean(dimension_values[UserAspects.Dimension.COGNITION]), 2) if dimension_values[UserAspects.Dimension.COGNITION] else 0,
            round(mean(dimension_values[UserAspects.Dimension.BEHAVIOR]), 2) if dimension_values[UserAspects.Dimension.BEHAVIOR] else 0,
        ])
    return response


@login_required
def api_tasks(request):
    scope = _scope_from_request(request)
    assignment_qs = TaskUser.objects.select_related('user').order_by('type', 'user__first_name', 'user__username')
    tasks = (
        get_visible_tasks(request.user, scope)
        .prefetch_related(Prefetch('tasks', queryset=assignment_qs))
        .order_by('-created_at')[:100]
    )
    data = []
    for task in tasks:
        assignments = list(task.tasks.all())
        data.append({
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'difficulty': task.difficulty,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'executors': [str(item.user) for item in assignments if item.type == Task.UserType.EXECUTOR],
            'stakeholders': [str(item.user) for item in assignments if item.type == Task.UserType.STAKEHOLDER],
        })
    return JsonResponse({'scope': scope, 'results': data})


@login_required
def api_effectiveness(request):
    scope = _scope_from_request(request)
    dashboard_data = compute_dashboard(request.user, scope)
    data = [
        {
            'day': item['day'].isoformat(),
            'effectiveness': item['effectiveness'],
            'environment': item['environment'],
            'cognition': item['cognition'],
            'behavior': item['behavior'],
        }
        for item in dashboard_data['daily_rows']
    ]
    return JsonResponse({'scope': scope, 'results': data})


@login_required
def api_recommendations(request):
    scope = _scope_from_request(request)
    return JsonResponse({'scope': scope, 'results': build_recommendations(request.user, scope)})


@login_required
def api_charts(request):
    scope = _scope_from_request(request)
    dashboard_data = compute_dashboard(request.user, scope)
    heatmap_rows = compute_heatmap(request.user, scope)
    return JsonResponse({
        'scope': scope,
        'results': build_visualization_data(request.user, dashboard_data, heatmap_rows, scope),
    })


def _raw_api_key(request):
    key = request.headers.get('X-ERGO-API-Key', '').strip()
    if key:
        return key
    authorization = request.headers.get('Authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return ''


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def api_sensors(request):
    raw_key = _raw_api_key(request)
    token_user = SensorApiToken.authenticate(raw_key) if raw_key else None

    if request.method == 'POST':
        # CSRF is intentionally exempt only because writes require a dedicated API key.
        if token_user is None:
            return JsonResponse({'error': str(_('A valid sensor API key is required for POST requests.'))}, status=401)
        api_user = token_user
    else:
        api_user = token_user or (request.user if request.user.is_authenticated else None)
        if api_user is None:
            return JsonResponse({'error': str(_('Authentication required.'))}, status=401)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': str(_('Invalid JSON.'))}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({'error': str(_('The JSON body must be an object.'))}, status=400)
        payload = payload.copy()
        payload.setdefault('source', 'api')
        form = SensorReadingForm(payload)
        if not form.is_valid():
            return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
        reading = form.save(commit=False)
        reading.user = api_user
        reading.save()
        return JsonResponse({'id': reading.id, 'created': True}, status=201)

    readings = SensorReading.objects.filter(user=api_user).order_by('-captured_at')[:100]
    data = [
        {
            'captured_at': item.captured_at.isoformat(),
            'source': item.source,
            'temperature_c': str(item.temperature_c) if item.temperature_c is not None else None,
            'humidity_percent': str(item.humidity_percent) if item.humidity_percent is not None else None,
            'noise_db': str(item.noise_db) if item.noise_db is not None else None,
            'luminosity_lux': str(item.luminosity_lux) if item.luminosity_lux is not None else None,
            'air_quality_index': str(item.air_quality_index) if item.air_quality_index is not None else None,
            'note': item.note,
        }
        for item in readings
    ]
    return JsonResponse({'results': data})
