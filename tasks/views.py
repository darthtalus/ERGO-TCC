from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Avg
from user_aspects.forms import EffectForm

from django.contrib import auth
from .models import Task, TaskUser, CustomUser, TaskRate, TaskInvitation, TaskShareLink, TaskJoinRequest
from user_aspects.models import Effectiveness, UserAspectHistory, UserAspects
from datetime import date
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .forms import (
    AssignmentStatusForm,
    RoleForm,
    RoleFormSet,
    SelfAssessmentForm,
    StakeholderEvaluationForm,
    TaskForm,
    InvitationBatchItemForm,
    PublicJoinRequestForm,
    JoinRequestDecisionForm,
)
from .permissions import can_evaluate_assignment, can_manage_task, can_view_task, is_privileged as is_task_privileged
from .services import (
    TaskWorkflowError,
    change_assignment_status,
    clear_stakeholder_evaluation,
    complete_assignment,
    evaluate_assignment,
    task_has_workflow_history,
)
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.utils import translation
from django.conf import settings
from django.db.models import Q, Case, When, Value, BooleanField, Exists, OuterRef, Subquery
from django.views.decorators.http import require_POST, require_http_methods


def status_icon():
    return {
        "doing": "play",
        "paused": "pause",
        "canceled": "xmark",
        "done": "check",
    }


def apply_sorting(request, queryset, default_sort='id'):
    sort = request.GET.get('sort', default_sort)
    order = request.GET.get('order', 'asc')
    

    # Handle special sorting for Stakeholders and Executors
    if sort == 'stakeholder_name':
        task_ref = OuterRef('pk') if queryset.model == Task else OuterRef('task_id')
        sub = TaskUser.objects.filter(
            task_id=task_ref,
            type=Task.UserType.STAKEHOLDER
        ).order_by('user__first_name').values('user__first_name')[:1]
        queryset = queryset.annotate(stakeholder_name=Subquery(sub))
    
    elif sort == 'executor_name':
        task_ref = OuterRef('pk') if queryset.model == Task else OuterRef('task_id')
        sub = TaskUser.objects.filter(
            task_id=task_ref,
            type=Task.UserType.EXECUTOR
        ).order_by('user__first_name').values('user__first_name')[:1]
        queryset = queryset.annotate(executor_name=Subquery(sub))

    elif sort == 'is_evaluated':
        # This assumes the queryset has been annotated with 'evaluated_by_me'
        sort = 'evaluated_by_me'

    elif sort == 'status' and queryset.model == Task:
        # If we're sorting Tasks by status, we usually mean the Executor's status
        sub = TaskUser.objects.filter(
            task_id=OuterRef('pk'),
            type=Task.UserType.EXECUTOR
        ).values('status')[:1]
        queryset = queryset.annotate(status_sort=Subquery(sub))
        sort = 'status_sort'

    if order == 'desc':
        sort_field = f'-{sort}'
    else:
        sort_field = sort
        
    try:
        return queryset.order_by(sort_field)
    except:
        return queryset

def get_index_context(request):
    all_effectiveness = Effectiveness.objects.filter(user=request.user).order_by('-day')
    day_effectiveness = Effectiveness.objects.filter(
        user=request.user, day=date.today()
    ).first()
    effectiveness_form = EffectForm()

    
    # Optimized: Get all averages in a single query grouped by effectiveness and dimension
    histories = UserAspectHistory.objects.filter(effectiveness__in=all_effectiveness) \
        .values('effectiveness_id', 'dimension') \
        .annotate(avg_param=Avg('parametrized'))
    
    # Organize histories into a dictionary for quick access: {eff_id: {dimension: avg}}
    history_map = {}
    for h in histories:
        eff_id = h['effectiveness_id']
        if eff_id not in history_map:
            history_map[eff_id] = {}
        history_map[eff_id][h['dimension']] = h['avg_param']

    resultado = []
    for e in all_effectiveness:
        averages = history_map.get(e.id, {})
        
        def get_dim_avg(stats_dict, dim_name):
            val = stats_dict.get(dim_name, 0.0)
            return round(val, 2) if val is not None else 0.0

        resultado.append({
            'dia': e.day,
            'effectiveness' : e.effectiveness,
            'behavior_avg': get_dim_avg(averages, 'BEHAVIOR'),
            'cognition_avg': get_dim_avg(averages, 'COGNITION'),
            'environment_avg': get_dim_avg(averages, 'ENVIRONMENT'),
        })


    
   

    # Role-based filtering logic
    is_privileged = is_task_privileged(request.user)

    if is_privileged:
        myTasks = Task.objects.all()
        my_tasks_executor = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
        stakeholder_tasks = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
    else:
        myTasks = Task.objects.filter(user=request.user)
        my_tasks_executor = TaskUser.objects.filter(
            user=request.user, type=Task.UserType.EXECUTOR
        )
        reviewable_task_ids = (
            Task.objects.filter(
                Q(user=request.user)
                | Q(tasks__user=request.user, tasks__type=Task.UserType.STAKEHOLDER)
            )
            .distinct()
            .values_list('id', flat=True)
        )
        # Owners and assigned stakeholders can review executor assignments.
        stakeholder_tasks = TaskUser.objects.filter(
            type=Task.UserType.EXECUTOR,
            task_id__in=reviewable_task_ids,
        )

    current_reviewer_rate = TaskRate.objects.filter(
        taskuser_id=OuterRef('pk'),
        user_id=request.user.id,
        rate_type=TaskRate.RateType.STAKEHOLDER,
    )
    stakeholder_tasks = stakeholder_tasks.annotate(
        evaluated_by_me=Exists(current_reviewer_rate),
    )
    my_tasks_stakeholder_ev = stakeholder_tasks.filter(evaluated_by_me=True)
    my_tasks_stakeholder = stakeholder_tasks.filter(
        evaluated_by_me=False,
        status=Task.Status.DONE,
    ).exclude(user=request.user)

    my_tasks_to_other = TaskUser.objects.filter(task__in=myTasks).exclude(
        user=request.user
    )
    tasks = TaskUser.objects.filter(task__in=myTasks)
    
    if is_privileged:
        atasks = TaskUser.objects.filter(type=Task.UserType.STAKEHOLDER).exclude(pk__in=tasks)
    else:
        atasks = TaskUser.objects.filter(
            user=request.user, type=Task.UserType.STAKEHOLDER
        ).exclude(pk__in=tasks)

    # Status counts for Executor view
    status_counts = {
        'DOING': my_tasks_executor.filter(status='DOING').count(),
        'DONE': my_tasks_executor.filter(status='DONE').count(),
        'PAUSED': my_tasks_executor.filter(status='PAUSED').count(),
        'CANCELED': my_tasks_executor.filter(status='CANCELED').count(),
        'ALL': my_tasks_executor.count(),
    }

    # Standardized card counts (Executors count)
    card_executor_count = my_tasks_executor.count()
    card_stakeholder_count = stakeholder_tasks.count()
    # For 'Created by me', we count the Tasks where the user is the owner
    if is_privileged:
        card_created_count = Task.objects.count()
    else:
        card_created_count = Task.objects.filter(user=request.user).count()

    # Apply status filter if present
    current_status = request.GET.get('status')
    if current_status and current_status != 'ALL':
        my_tasks_executor = my_tasks_executor.filter(status=current_status)
        myTasks = myTasks.filter(Exists(TaskUser.objects.filter(
            task_id=OuterRef('pk'), status=current_status, type=Task.UserType.EXECUTOR,
        )))
    
    # Apply search filter
    search_query = request.GET.get('q')
    if search_query:
        my_tasks_executor = my_tasks_executor.filter(task__name__icontains=search_query)
        myTasks = myTasks.filter(name__icontains=search_query)
    

    # Apply sorting
    
    # Keep one row per task even when its executors have different statuses.
    myTasks = myTasks.annotate(
        is_doing=Exists(TaskUser.objects.filter(
            task_id=OuterRef('pk'), status=Task.Status.DOING, type=Task.UserType.EXECUTOR,
        ))
    )
    default_myTasks_sort = '-is_doing' if not request.GET.get('sort') else 'id'
    myTasks = apply_sorting(request, myTasks, default_myTasks_sort)
    
    my_tasks_executor = my_tasks_executor.annotate(
        is_doing=Case(
            When(status=Task.Status.DOING, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    )
    default_executor_sort = '-is_doing' if not request.GET.get('sort') else 'task__id'
    my_tasks_executor = apply_sorting(request, my_tasks_executor, default_executor_sort)
    
    atasks = apply_sorting(request, atasks, 'task__id')
    my_tasks_to_other = apply_sorting(request, my_tasks_to_other, 'task__id')
    tasks = apply_sorting(request, tasks, 'task__id')

    context = {
        "tasks": tasks,
        "mytasks": myTasks,
        "atasks": atasks,
        "my_tasks_executor": my_tasks_executor,
        "my_tasks_stakeholder": my_tasks_stakeholder,
        "my_tasks_stakeholder_ev": my_tasks_stakeholder_ev,
        "my_tasks_to_other": my_tasks_to_other,
        "stakeholder_tasks": stakeholder_tasks,
        "icons": status_icon,
        "all_effectiveness": all_effectiveness,
        "day_effectiveness": day_effectiveness,
        "effectiveness_form": effectiveness_form,
        "resultado" : resultado,
        "card_executor_count": card_executor_count,
        "card_created_count": card_created_count,
        "card_stakeholder_count": card_stakeholder_count,
        "current_status": request.GET.get('status', 'ALL'),
        "status_counts": status_counts,
        "current_sort": request.GET.get('sort', ''),
        "current_order": request.GET.get('order', 'asc'),
        "has_parameters": (
            UserAspects.objects.filter(user=request.user, dimension=UserAspects.Dimension.ENVIRONMENT).exists() and
            UserAspects.objects.filter(user=request.user, dimension=UserAspects.Dimension.COGNITION).exists() and
            UserAspects.objects.filter(user=request.user, dimension=UserAspects.Dimension.BEHAVIOR).exists()
        ),
    }
    return context



@login_required
def statistics(request):
    return render(request, 'pages/statistic.html', get_index_context(request))

@login_required
def index(request):
    request.session['end'] = False
    context = get_index_context(request)

    # Paginate my_tasks_executor
    paginator = Paginator(context["my_tasks_executor"], 5)
    page_number = request.GET.get('page')
    context["my_tasks_executor"] = paginator.get_page(page_number)

    return render(request, "tasks/index.html", context)


@login_required
def created_by_me(request):
    context = get_index_context(request)
    
    is_privileged = is_task_privileged(request.user)
    if is_privileged:
        status_counts_tasks = Task.objects.all()
    else:
        status_counts_tasks = Task.objects.filter(user=request.user)

    status_counts = {
        'DOING': status_counts_tasks.filter(tasks__status='DOING', tasks__type=Task.UserType.EXECUTOR).distinct().count(),
        'DONE': status_counts_tasks.filter(tasks__status='DONE', tasks__type=Task.UserType.EXECUTOR).distinct().count(),
        'PAUSED': status_counts_tasks.filter(tasks__status='PAUSED', tasks__type=Task.UserType.EXECUTOR).distinct().count(),
        'CANCELED': status_counts_tasks.filter(tasks__status='CANCELED', tasks__type=Task.UserType.EXECUTOR).distinct().count(),
        'ALL': status_counts_tasks.count(),
    }
    context["status_counts"] = status_counts

    # Paginate mytasks
    paginator = Paginator(context["mytasks"], 5)
    page_number = request.GET.get('page')
    context["mytasks"] = paginator.get_page(page_number)
    
    return render(request, "tasks/created_by_me.html", context)


@login_required
def stakeholder(request):
    is_privileged = is_task_privileged(request.user)
    
    if is_privileged:
        myTasks = Task.objects.all()
        my_tasks_executor = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
        stakeholder_tasks = Task.objects.all()
        # Initial queryset for all relevant TaskUsers
        stakeholder_tasks_qs = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
    else:
        myTasks = Task.objects.filter(user=request.user)
        my_tasks_executor = TaskUser.objects.filter(
            user=request.user, type=Task.UserType.EXECUTOR
        )
        stakeholder_tasks = Task.objects.filter(
            Q(user=request.user)
            | Q(tasks__user=request.user, tasks__type=Task.UserType.STAKEHOLDER)
        ).distinct()
        stakeholder_list = stakeholder_tasks.values_list('id', flat=True)
        stakeholder_tasks_qs = TaskUser.objects.filter(
            type=Task.UserType.EXECUTOR,
            task_id__in=stakeholder_list,
        )

    # The UI flag is always scoped to the current reviewer.  Previously the
    # privileged view treated any rating (including the executor SELF rating)
    # as if the administrator had evaluated the assignment.
    evaluated_subquery = TaskRate.objects.filter(
        taskuser_id=OuterRef('pk'),
        user_id=request.user.id,
        rate_type=TaskRate.RateType.STAKEHOLDER,
    )

    stakeholder_tasks_qs = stakeholder_tasks_qs.annotate(
        evaluated_by_me=Exists(evaluated_subquery),
        is_final_approved=Exists(TaskUser.objects.filter(
            pk=OuterRef('pk'), upgrade_reviews__status='APPROVED',
        )),
        is_own_assignment=Case(
            When(user_id=request.user.id, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
    ).select_related('task', 'user').prefetch_related('task__tasks', 'task__tasks__user')

    # A completed assignment is pending only when this user may review it.
    stakeholder_tasks_qs = stakeholder_tasks_qs.annotate(
        is_pending_evaluation=Case(
            When(
                Q(status=Task.Status.DONE)
                & Q(evaluated_by_me=False)
                & Q(is_final_approved=False)
                & Q(is_own_assignment=False),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )

    # Apply sorting - default to pending evaluations first, then by task ID
    default_sort = '-is_pending_evaluation' if not request.GET.get('sort') else 'task__id'
    stakeholder_tasks_qs = apply_sorting(request, stakeholder_tasks_qs, default_sort)

    # Apply status filter
    current_status = request.GET.get('status')
    if current_status and current_status != 'ALL':
        stakeholder_tasks_qs = stakeholder_tasks_qs.filter(status=current_status)

    # Apply search filter
    search_query = request.GET.get('q')
    if search_query:
        stakeholder_tasks_qs = stakeholder_tasks_qs.filter(task__name__icontains=search_query)

    # Paginate
    paginator = Paginator(stakeholder_tasks_qs, 5)
    page_number = request.GET.get('page')
    stakeholder_tasks_qs = paginator.get_page(page_number)

    # Standardized card counts for cards partial
    card_executor_count = TaskUser.objects.filter(user=request.user, type=Task.UserType.EXECUTOR).count() if not is_privileged else TaskUser.objects.filter(type=Task.UserType.EXECUTOR).count()
    if is_privileged:
        card_created_count = Task.objects.count()
        card_stakeholder_count = TaskUser.objects.filter(type=Task.UserType.EXECUTOR).count()
    else:
        card_created_count = Task.objects.filter(user=request.user).count()
        # Count all executors of tasks where I am stakeholder
        card_stakeholder_count = TaskUser.objects.filter(type=Task.UserType.EXECUTOR, task_id__in=stakeholder_list).count()

    # Status counts for filter (calculate BEFORE status filter is applied to the main list)
    # We use a copy of the queryset before filtering
    status_counts_qs = TaskUser.objects.filter(type=Task.UserType.EXECUTOR)
    if not is_privileged:
        status_counts_qs = status_counts_qs.filter(task_id__in=stakeholder_list)

    status_counts = {
        'DOING': status_counts_qs.filter(status='DOING').count(),
        'DONE': status_counts_qs.filter(status='DONE').count(),
        'PAUSED': status_counts_qs.filter(status='PAUSED').count(),
        'CANCELED': status_counts_qs.filter(status='CANCELED').count(),
        'ALL': status_counts_qs.count(),
    }

    context = {
        "mytasks": myTasks,
        "my_tasks_executor": my_tasks_executor,
        "stakeholder_tasks_all": stakeholder_tasks_qs,
        "stakeholder_tasks": card_stakeholder_count,
        "card_executor_count": card_executor_count,
        "card_created_count": card_created_count,
        "card_stakeholder_count": card_stakeholder_count,
        "current_status": request.GET.get('status', 'ALL'),
        "status_counts": status_counts,
        "current_sort": request.GET.get('sort', ''),
        "current_order": request.GET.get('order', 'asc'),
        "search_query": search_query or '',
    }
    return render(request, "tasks/stakeholder.html", context)



@login_required
def tutorials(request):
    return render(request, "tasks/tutorials.html")


@login_required
def documentation(request):
    return render(request, "tasks/documentation.html")


@login_required
@transaction.atomic
def new(request):
    form = TaskForm(request.POST or None)
    users = CustomUser.objects.all()
    roles = Task.UserType
    formset = RoleFormSet(request.POST or None)

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        entries = []
        seen = set()
        for role_form in formset:
            user = role_form.cleaned_data.get('user')
            role_type = role_form.cleaned_data.get('type')
            if not user or not role_type:
                continue
            key = (user.pk, role_type)
            if key in seen:
                messages.error(request, _("The same user and role cannot be added twice."))
                return render(request, 'tasks/edit.html', {'roles': roles, 'users': users, 'form': form, 'formset': formset})
            seen.add(key)
            entries.append((user, role_type))

        task = form.save(commit=False)
        task.user = request.user
        task.save()
        for user, role_type in entries:
            assignment = TaskUser.objects.create(
                task=task,
                user=user,
                type=role_type,
                status=Task.Status.NONE if role_type == Task.UserType.STAKEHOLDER else Task.Status.DOING,
            )
            if assignment.type == Task.UserType.EXECUTOR:
                send_task_assignment_notification(request, assignment)
        process_invitations(request, task)
        messages.success(request, _("Task created successfully."))
        return redirect('tasks_edit', task_id=task.pk)

    return render(request, 'tasks/edit.html', {'roles': roles, 'users': users, 'form': form, 'formset': formset})

@login_required
@transaction.atomic
def edit(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    users = CustomUser.objects.all()
    roles = Task.UserType
    existing_assignments = TaskUser.objects.filter(task=task).order_by('-type', 'user__first_name')

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        formset = RoleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            entries = []
            seen = set()
            duplicate = False
            for role_form in formset:
                user = role_form.cleaned_data.get('user')
                role_type = role_form.cleaned_data.get('type')
                if not user or not role_type:
                    continue
                key = (user.pk, role_type)
                if key in seen:
                    duplicate = True
                    break
                seen.add(key)
                entries.append((user, role_type))

            if duplicate:
                messages.error(request, _("The same user and role cannot be added twice."))
            else:
                form.save()
                kept_ids = []
                for user, role_type in entries:
                    assignment, created = TaskUser.objects.get_or_create(
                        task=task,
                        user=user,
                        type=role_type,
                        defaults={
                            'status': Task.Status.NONE if role_type == Task.UserType.STAKEHOLDER else Task.Status.DOING,
                        },
                    )
                    kept_ids.append(assignment.pk)
                    if created and assignment.type == Task.UserType.EXECUTOR:
                        send_task_assignment_notification(request, assignment)

                removed = TaskUser.objects.filter(task=task).exclude(pk__in=kept_ids)
                for assignment in removed:
                    has_history = assignment.rate.exists()
                    if hasattr(assignment, 'upgrade_reviews'):
                        has_history = has_history or assignment.upgrade_reviews.exists() or assignment.start_checklists.exists()
                    if has_history:
                        kept_ids.append(assignment.pk)
                        messages.warning(
                            request,
                            _("%(user)s was kept because this assignment already has workflow history.")
                            % {'user': assignment.user},
                        )
                    else:
                        assignment.delete()

                process_invitations(request, task)
                messages.success(request, _("Task updated successfully."))
                return redirect('tasks_edit', task_id=task.pk)
    else:
        form = TaskForm(instance=task)
        initial = [
            {'user': assignment.user_id, 'type': assignment.type}
            for assignment in existing_assignments
        ]
        formset = RoleFormSet(initial=initial)

    context = {'roles': roles, 'users': users, 'form': form, 'formset': formset}
    return render(request, 'tasks/edit.html', context)

@login_required
@require_POST
@transaction.atomic
def task_delete(request, task_id):
    """Delete only a history-free task after an explicit, serialized POST."""
    task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    # Serialize deletion with execution/review writes that lock assignment rows.
    list(task.tasks.select_for_update().values_list('pk', flat=True))
    if task_has_workflow_history(task):
        messages.error(request, _('This task cannot be deleted because it already has workflow history.'))
        return redirect('tasks_edit', task_id=task.pk)
    task_name = task.name
    task.delete()
    messages.success(request, _('Task "%(name)s" deleted successfully.') % {'name': task_name})
    return redirect('tasks_index')

@login_required
@require_POST
def add_user_role(request):
    form = TaskForm(request.POST or None)
    user = request.POST.get('user', '')
    role = request.POST.get('role', '')
    users = CustomUser.objects.all()
    roles = Task.UserType
    return render(request, 'tasks/new.html', {'roles': roles, 'users': users, 'role': role, 'user': user, 'form': form})

@login_required
def roles(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied
    task_users = task.tasks.select_related('user').all().order_by('-type', 'user__first_name')
    return render(request, 'tasks/roles.html', {'task': task, 'task_users': task_users})

@login_required
@transaction.atomic
def role_new(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            role_type = form.cleaned_data['type']
            try:
                assignment, created = TaskUser.objects.get_or_create(
                    task=task,
                    user=user,
                    type=role_type,
                    defaults={
                        'status': Task.Status.NONE if role_type == Task.UserType.STAKEHOLDER else Task.Status.DOING,
                    },
                )
            except IntegrityError:
                created = False
                assignment = None
            if not created:
                messages.error(request, _("Role exists"))
            else:
                if assignment.type == Task.UserType.EXECUTOR:
                    send_task_assignment_notification(request, assignment)
                messages.success(request, _("Role added"))
            return redirect('tasks_roles', task_id=task.pk)
    else:
        form = RoleForm()

    return render(request, 'tasks/roles_new.html', {'form': form, 'task': task})

@login_required
@require_POST
@transaction.atomic
def role_delete(request, id):
    assignment = get_object_or_404(TaskUser.objects.select_related('task', 'user'), pk=id)
    task = assignment.task
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    has_history = assignment.rate.exists()
    if hasattr(assignment, 'upgrade_reviews'):
        has_history = has_history or assignment.upgrade_reviews.exists() or assignment.start_checklists.exists()
    if has_history:
        messages.error(request, _("This role cannot be removed because it already has workflow history."))
    else:
        assignment.delete()
        messages.success(request, _("Role deleted"))
    return redirect('tasks_roles', task_id=task.pk)

@login_required
@require_POST
@transaction.atomic
def change(request):
    form = AssignmentStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Invalid status request."))
        return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=form.cleaned_data['taskuser_id'],
    )
    try:
        result = change_assignment_status(
            actor=request.user,
            assignment=assignment,
            new_status=form.cleaned_data['status'],
        )
    except TaskWorkflowError as exc:
        if str(exc) == 'permission_denied':
            raise PermissionDenied
        message = _("This status transition is not allowed.") if str(exc) == 'invalid_transition' else _("Invalid status.")
        messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

    if result.new_status == Task.Status.CANCELED and result.old_status != Task.Status.CANCELED:
        send_task_canceled_notification(request, assignment)
    elif result.old_status == Task.Status.CANCELED and result.new_status == Task.Status.DOING:
        send_task_reactivated_notification(request, assignment)

    messages.success(request, _("Status updated"))
    return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

@login_required
@require_POST
@transaction.atomic
def done(request):
    assignment_id = request.POST.get('taskuser_id')
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=assignment_id,
    )
    assessment_form = SelfAssessmentForm({
        'environment': request.POST.get('environmentRadio'),
        'cognition': request.POST.get('cognitionRadio'),
        'behavior': request.POST.get('behaviorRadio'),
        'effectiveness': request.POST.get('effectiveness'),
    })
    if not assessment_form.is_valid():
        messages.error(request, _("All ratings must be whole numbers from 1 to 5."))
        return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

    try:
        complete_assignment(
            actor=request.user,
            assignment=assignment,
            assessment=assessment_form.cleaned_data,
        )
    except TaskWorkflowError as exc:
        if str(exc) == 'permission_denied':
            raise PermissionDenied
        messages.error(request, _("This assignment cannot be completed from its current status."))
        return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

    send_task_completed_notification(request, assignment)
    messages.success(request, _("Task completed and self-assessment saved."))
    return redirect(request.META.get('HTTP_REFERER', 'tasks_index'))

@login_required
@require_POST
@transaction.atomic
def stakeholder_evaluate(request):
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=request.POST.get('taskuser_id'),
    )
    form = StakeholderEvaluationForm({'effectiveness': request.POST.get('effectiveness')})
    if not form.is_valid():
        messages.error(request, _("Effectiveness must be a whole number from 1 to 5."))
        return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))

    try:
        evaluate_assignment(
            actor=request.user,
            assignment=assignment,
            effectiveness=form.cleaned_data['effectiveness'],
        )
    except TaskWorkflowError as exc:
        code = str(exc)
        if code == 'permission_denied':
            raise PermissionDenied
        messages.error(request, {
            'not_completed': _("Only completed executor assignments can be evaluated."),
            'missing_self_assessment': _("A valid executor self-assessment is required before evaluation."),
            'final_approved': _("This assignment is approved and its evaluations are final."),
        }.get(code, _("The evaluation could not be saved.")))
        return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))

    send_task_evaluated_notification(request, assignment, request.user)
    messages.success(request, _("Stakeholder evaluation saved."))
    return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))

@login_required
@require_POST
@transaction.atomic
def stakeholder_clear_evaluate(request, taskuser_id):
    assignment = get_object_or_404(
        TaskUser.objects.select_for_update().select_related('task', 'user'),
        pk=taskuser_id,
    )
    try:
        deleted = clear_stakeholder_evaluation(actor=request.user, assignment=assignment)
    except TaskWorkflowError as exc:
        if str(exc) == 'permission_denied':
            raise PermissionDenied
        if str(exc) == 'final_approved':
            messages.error(request, _("This assignment is approved and its evaluations are final."))
            return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))
        messages.error(request, _("The evaluation could not be cleared."))
        return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))
    if deleted:
        messages.success(request, _("Evaluation cleared"))
    else:
        messages.info(request, _("No evaluation from your user was found."))
    return redirect(request.META.get('HTTP_REFERER', 'stakeholder_tasks'))

def process_invitations(request, task):
    """Validate and create task invitations submitted with the task form.

    Invalid rows are ignored with a user-facing warning.  Existing active
    invitations for the same e-mail/role are reused to avoid duplicate mail
    and duplicate participation records.
    """
    raw_total = request.POST.get('total_invitations', '0')
    try:
        total_invitations = max(0, min(int(raw_total), 100))
    except (TypeError, ValueError):
        total_invitations = 0
        messages.warning(request, _("Invalid invitation count was ignored."))

    for i in range(total_invitations):
        form = InvitationBatchItemForm({
            'email': request.POST.get(f'invite_email_{i}', '').strip().lower(),
            'type': request.POST.get(f'invite_role_{i}', ''),
        })
        if not form.is_valid():
            messages.warning(request, _("An invalid invitation row was ignored."))
            continue

        email = form.cleaned_data['email']
        role_type = form.cleaned_data['type']
        if TaskUser.objects.filter(task=task, user__email__iexact=email, type=role_type).exists():
            messages.info(request, _("%(email)s already participates in this role.") % {'email': email})
            continue

        invitation = TaskInvitation.objects.filter(
            email__iexact=email,
            task=task,
            type=role_type,
            accepted=False,
        ).order_by('-created_at').first()
        if invitation and invitation.is_expired:
            invitation.delete()
            invitation = None
        if invitation is None:
            invitation = TaskInvitation.objects.create(
                email=email,
                task=task,
                type=role_type,
                invited_by=request.user,
            )

        subject = _('Invitation to participate in task: %(task_name)s') % {'task_name': task.name}
        invite_url = request.build_absolute_uri(reverse('tasks_accept_invitation', args=[invitation.id]))
        context = {
            'invitation': invitation,
            'first_name': invitation.invited_by.first_name,
            'last_name': invitation.invited_by.last_name,
            'task_name': task.name,
            'invite_url': invite_url,
            'role_name': invitation.get_type_display(),
        }
        html_message = render_to_string('tasks/emails/invitation_email.html', context)
        plain_message = strip_tags(html_message)
        try:
            send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [email], html_message=html_message)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Error sending invitation email: %s", exc)

def send_task_reactivated_notification(request, taskuser):
    """
    Sends an email notification to all stakeholders of a task when an executor reactivates it (CANCELED -> DOING).
    """
    task = taskuser.task
    stakeholders = task.tasks.filter(type=Task.UserType.STAKEHOLDER)
    
    if not stakeholders.exists():
        return

    # Use the current language
    with translation.override(request.LANGUAGE_CODE):
        subject = _('Task reactivated: %(task_name)s') % {'task_name': task.name}
        history_url = request.build_absolute_uri(reverse('task_history', args=[task.id]))
        
        for sh in stakeholders:
            context = {
                'recipient_name': sh.user.get_full_name() or sh.user.first_name,
                'executor_name': taskuser.user.get_full_name() or taskuser.user.first_name,
                'task_name': task.name,
                'history_url': history_url,
            }
            
            html_message = render_to_string('tasks/emails/task_reactivated_email.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject, 
                    plain_message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [sh.user.email], 
                    html_message=html_message
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending task reactivation email to {sh.user.email}: {e}")

def send_task_canceled_notification(request, taskuser):
    """
    Sends an email notification to all stakeholders of a task when an executor marks it as CANCELED.
    """
    task = taskuser.task
    stakeholders = task.tasks.filter(type=Task.UserType.STAKEHOLDER)
    
    if not stakeholders.exists():
        return

    # Use the current language
    with translation.override(request.LANGUAGE_CODE):
        subject = _('Task canceled: %(task_name)s') % {'task_name': task.name}
        history_url = request.build_absolute_uri(reverse('task_history', args=[task.id]))
        
        for sh in stakeholders:
            context = {
                'recipient_name': sh.user.get_full_name() or sh.user.first_name,
                'executor_name': taskuser.user.get_full_name() or taskuser.user.first_name,
                'task_name': task.name,
                'history_url': history_url,
            }
            
            html_message = render_to_string('tasks/emails/task_canceled_email.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject, 
                    plain_message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [sh.user.email], 
                    html_message=html_message
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending task cancellation email to {sh.user.email}: {e}")

def send_task_completed_notification(request, taskuser):
    """
    Sends an email notification to all stakeholders of a task when an executor marks it as DONE.
    """
    task = taskuser.task
    stakeholders = task.tasks.filter(type=Task.UserType.STAKEHOLDER)
    
    if not stakeholders.exists():
        return

    # Use the executor's current language for the notification email
    with translation.override(request.LANGUAGE_CODE):
        subject = _('Task completed and ready for evaluation: %(task_name)s') % {'task_name': task.name}
        evaluation_url = request.build_absolute_uri(reverse('task_history', args=[task.id]) + f'?evaluate={taskuser.id}')
        
        for sh in stakeholders:
            context = {
                'recipient_name': sh.user.get_full_name() or sh.user.first_name,
                'executor_name': taskuser.user.get_full_name() or taskuser.user.first_name,
                'task_name': task.name,
                'evaluation_url': evaluation_url,
            }
            
            html_message = render_to_string('tasks/emails/task_completed_email.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject, 
                    plain_message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [sh.user.email], 
                    html_message=html_message
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending task completion email to {sh.user.email}: {e}")

def send_task_assignment_notification(request, taskuser):
    """
    Sends an email notification to an executor when they are assigned to a task.
    """
    task = taskuser.task
    executor = taskuser.user

    if not executor.email:
        return

    # Use the current active language (of the person assigning the task)
    with translation.override(request.LANGUAGE_CODE):
        subject = _('New task assigned: %(task_name)s') % {'task_name': task.name}
        task_url = request.build_absolute_uri(reverse('task_history', args=[task.id]))
        
        context = {
            'recipient_name': executor.get_full_name() or executor.first_name,
            'owner_name': task.user.get_full_name() or task.user.first_name,
            'task_name': task.name,
            'task_url': task_url,
        }
        
        html_message = render_to_string('tasks/emails/new_task_assignment_email.html', context)
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject, 
                plain_message, 
                settings.DEFAULT_FROM_EMAIL, 
                [executor.email], 
                html_message=html_message
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending task assignment email to {executor.email}: {e}")

def send_task_evaluated_notification(request, taskuser, stakeholder_user):
    """
    Sends an email notification to the executor when a stakeholder finishes their evaluation.
    """
    task = taskuser.task
    executor = taskuser.user

    if not executor.email:
        return

    # Use the stakeholder's current language (or we could use executor's preference if stored)
    # But as per previous request, we follow the language of the person performing the action
    with translation.override(request.LANGUAGE_CODE):
        subject = _('Task evaluated: %(task_name)s') % {'task_name': task.name}
        history_url = request.build_absolute_uri(reverse('task_history', args=[task.id]))
        
        context = {
            'recipient_name': executor.get_full_name() or executor.first_name,
            'stakeholder_name': stakeholder_user.get_full_name() or stakeholder_user.first_name,
            'task_name': task.name,
            'history_url': history_url,
        }
        
        html_message = render_to_string('tasks/emails/task_evaluated_email.html', context)
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject, 
                plain_message, 
                settings.DEFAULT_FROM_EMAIL, 
                [executor.email], 
                html_message=html_message
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending task evaluation email to {executor.email}: {e}")

def send_task_reminder_notification(request, taskuser, stakeholder_user):
    """
    Sends an email notification to the executor reminding them to finish the task.
    """
    task = taskuser.task
    executor = taskuser.user

    if not executor.email:
        return

    with translation.override(request.LANGUAGE_CODE):
        subject = _('Reminder: Task not yet completed: %(task_name)s') % {'task_name': task.name}
        task_url = request.build_absolute_uri(reverse('task_history', args=[task.id]))
        
        context = {
            'recipient_name': executor.get_full_name() or executor.first_name,
            'stakeholder_name': stakeholder_user.get_full_name() or stakeholder_user.first_name,
            'task_name': task.name,
            'task_url': task_url,
        }
        
        html_message = render_to_string('tasks/emails/task_reminder_email.html', context)
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject, 
                plain_message, 
                settings.DEFAULT_FROM_EMAIL, 
                [executor.email], 
                html_message=html_message
            )
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending task reminder email to {executor.email}: {e}")
            return False

@require_http_methods(['GET', 'POST'])
@transaction.atomic
def accept_invitation(request, token):
    invitation = get_object_or_404(
        TaskInvitation.objects.select_for_update().select_related('task'),
        id=token,
    )

    if invitation.accepted:
        messages.info(request, _("This invitation has already been accepted."))
        return redirect('tasks_index')
    if invitation.is_expired:
        messages.error(request, _("This invitation link has expired (48 hours limit). Please ask for a new invitation."))
        return redirect('login')

    if not request.user.is_authenticated:
        if CustomUser.objects.filter(email__iexact=invitation.email).exists():
            messages.info(request, _("Please login with your account to join the task."))
            return redirect(f"{reverse('login')}?next={request.path}")
        return redirect(f"{reverse('register')}?email={invitation.email}&invitation={invitation.id}")

    if (request.user.email or '').casefold() != invitation.email.casefold():
        messages.error(request, _("This invitation belongs to a different e-mail address."))
        return redirect('tasks_index')

    if request.method == 'GET':
        return render(request, 'tasks/accept_invitation.html', {'invitation': invitation})

    assignment, created = TaskUser.objects.get_or_create(
        task=invitation.task,
        user=request.user,
        type=invitation.type,
        defaults={
            'status': Task.Status.NONE if invitation.type == Task.UserType.STAKEHOLDER else Task.Status.DOING,
        },
    )
    invitation.accepted = True
    invitation.save(update_fields=['accepted'])
    if created and assignment.type == Task.UserType.EXECUTOR:
        send_task_assignment_notification(request, assignment)
    messages.success(request, _("You have been added to the task '%(task_name)s' as %(role)s.") % {
        'task_name': invitation.task.name,
        'role': invitation.get_type_display(),
    })
    return redirect('tasks_index')

@login_required
def task_history(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    
    if not can_view_task(request.user, task):
        raise PermissionDenied

    assignments = task.tasks.all().select_related('user').prefetch_related(
        'rate', 'rate__user', 'upgrade_reviews', 'upgrade_reviews__reviewed_by',
    )
    is_privileged = is_task_privileged(request.user)
    is_owner = task.user_id == request.user.id
    is_stakeholder = task.tasks.filter(user=request.user, type=Task.UserType.STAKEHOLDER).exists()

    if not is_privileged and not is_owner:
        assignments = (
            assignments.filter(type=Task.UserType.EXECUTOR)
            if is_stakeholder
            else assignments.filter(user=request.user)
        )
    
    # The action state belongs to the current reviewer, including admins.
    from django.db.models import Exists, OuterRef
    evaluated_subquery = TaskRate.objects.filter(
        taskuser_id=OuterRef('pk'),
        user_id=request.user.id,
        rate_type=TaskRate.RateType.STAKEHOLDER,
    )

    assignments = list(assignments.annotate(
        evaluated_by_me=Exists(evaluated_subquery),
        is_final_approved=Exists(TaskUser.objects.filter(
            pk=OuterRef('pk'), upgrade_reviews__status='APPROVED',
        )),
    ))
    # Review snapshots remain immutable; build separate display records.
    snapshot_reviewer_ids = set()
    for assignment in assignments:
        for review in assignment.upgrade_reviews.all():
            snapshot = review.evaluation_snapshot or {}
            for rating in snapshot.get('stakeholder_assessments', []):
                if isinstance(rating.get('rated_by_user_id'), int):
                    snapshot_reviewer_ids.add(rating['rated_by_user_id'])
    snapshot_users = CustomUser.objects.in_bulk(snapshot_reviewer_ids)

    def display_snapshot_rating(rating):
        if not rating:
            return None
        result = dict(rating)
        rated_by_id = rating.get('rated_by_user_id')
        reviewer = snapshot_users.get(rated_by_id)
        result['reviewer_name'] = (
            reviewer.get_full_name() or reviewer.username if reviewer else f'#{rated_by_id}'
        )
        raw_date = rating.get('updated_at') or rating.get('created_at')
        try:
            result['rated_at'] = parse_datetime(raw_date) if raw_date else None
        except (ValueError, TypeError):
            result['rated_at'] = None
        return result

    for assignment in assignments:
        assignment.review_history = []
        for review in assignment.upgrade_reviews.all():
            snapshot = review.evaluation_snapshot or {}
            assignment.review_history.append({
                'review': review,
                'self_assessment': display_snapshot_rating(snapshot.get('self_assessment')),
                'stakeholder_assessments': [
                    display_snapshot_rating(rating)
                    for rating in snapshot.get('stakeholder_assessments', [])
                ],
            })
    
    # Navigation logic: Find next/prev tasks pending evaluation
    next_task_id = None
    prev_task_id = None
    
    # Owners, assigned stakeholders and administrators may navigate pending
    # reviews. Own executor assignments are never offered for self-review.
    if is_privileged:
        stakeholder_all_ids = Task.objects.values_list('id', flat=True)
    else:
        stakeholder_all_ids = (
            Task.objects.filter(
                Q(user=request.user)
                | Q(tasks__user=request.user, tasks__type=Task.UserType.STAKEHOLDER)
            )
            .distinct()
            .values_list('id', flat=True)
        )

    if is_privileged or stakeholder_all_ids.exists():
        current_evaluation = TaskRate.objects.filter(
            taskuser_id=OuterRef('pk'),
            user_id=request.user.id,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        )
        pending_assignments_subquery = (
            TaskUser.objects.filter(
                task_id=OuterRef('pk'),
                type=Task.UserType.EXECUTOR,
                status=Task.Status.DONE,
            )
            .exclude(user_id=request.user.id)
            .annotate(
                evaluated_by_me=Exists(current_evaluation),
                is_final_approved=Exists(TaskUser.objects.filter(
                    pk=OuterRef('pk'), upgrade_reviews__status='APPROVED',
                )),
            )
            .filter(evaluated_by_me=False, is_final_approved=False)
        )

        pending_ids = list(
            Task.objects.filter(id__in=stakeholder_all_ids)
            .filter(Exists(pending_assignments_subquery))
            .distinct()
            .order_by('id')
            .values_list('id', flat=True)
        )
        
        if pending_ids:
            # Find next task ID in pending_ids that is > task.id
            next_tasks = [tid for tid in pending_ids if tid > task.id]
            if next_tasks:
                next_task_id = next_tasks[0]
            
            # Find last task ID in pending_ids that is < task.id
            prev_tasks = [tid for tid in pending_ids if tid < task.id]
            if prev_tasks:
                prev_task_id = prev_tasks[-1]

    context = {
        'task': task,
        'assignments': assignments,
        'is_stakeholder': is_stakeholder,
        'next_task_id': next_task_id,
        'prev_task_id': prev_task_id,
    }
    return render(request, "tasks/task_history.html", context)


@login_required
@require_POST
def send_task_reminder(request, taskuser_id):
    """View to handle sending a reminder to an executor."""
    taskuser = get_object_or_404(TaskUser.objects.select_related('task', 'user'), pk=taskuser_id)
    task = taskuser.task
    
    # Check if the current user is a stakeholder or owner
    is_privileged = is_task_privileged(request.user)
    is_owner = task.user == request.user
    is_stakeholder = task.tasks.filter(user=request.user, type=Task.UserType.STAKEHOLDER).exists()
    
    if not (is_privileged or is_owner or is_stakeholder):
        raise PermissionDenied
    if taskuser.type != Task.UserType.EXECUTOR:
        raise PermissionDenied

    if taskuser.status == Task.Status.DONE:
        messages.warning(request, _("This task is already completed."))
    else:
        success = send_task_reminder_notification(request, taskuser, request.user)
        if success:
            name = taskuser.user.get_full_name() or taskuser.user.first_name
            email = taskuser.user.email
            executor_info = f"{name} ({email})" if name and email else (name or email)
            
            messages.success(request, _("Reminder sent to %(executor)s.") % {
                'executor': executor_info
            })
        else:
            messages.error(request, _("Failed to send reminder."))
            
    return redirect('task_history', task_id=task.id)


# ────────────────────────────────────────────────────────────────────────────
# Task Share Link – generate / toggle
# ────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def task_share_link(request, task_id):
    """Create or deactivate a shareable link for a task.
    Only the task owner (or privileged users) can manage the link.
    """
    task = get_object_or_404(Task, pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    action = request.POST.get('action')
    if action not in {'activate', 'deactivate', 'regenerate'}:
        messages.error(request, _('Invalid share-link action.'))
        return redirect(request.META.get('HTTP_REFERER', reverse('tasks_index')))

    share_link, _ = TaskShareLink.objects.select_for_update().get_or_create(
        task=task,
        defaults={'created_by': request.user},
    )
    if action == 'activate':
        share_link.is_active = True
        share_link.save(update_fields=['is_active'])
        messages.success(request, _('Link de compartilhamento ativado.'))
    elif action == 'deactivate':
        share_link.is_active = False
        share_link.save(update_fields=['is_active'])
        messages.success(request, _('Link de compartilhamento desativado.'))
    else:
        share_link.delete()
        TaskShareLink.objects.create(task=task, created_by=request.user)
        messages.success(request, _('Novo link gerado com sucesso.'))

    return redirect(request.META.get('HTTP_REFERER', reverse('tasks_index')))


# ────────────────────────────────────────────────────────────────────────────
# Public task view – no authentication required
# ────────────────────────────────────────────────────────────────────────────

def task_public_view(request, token):
    """Public page that any external user can access via the share link."""
    try:
        share_link = TaskShareLink.objects.get(id=token, is_active=True)
    except (TaskShareLink.DoesNotExist, ValueError):
        return render(request, '404.html', status=404)
        
    task = share_link.task

    # Check if this email already submitted a request
    already_requested = False
    request_status = None
    prefill_email = ''

    if request.method == 'POST':
        join_form = PublicJoinRequestForm(request.POST)
        if not join_form.is_valid():
            messages.error(request, _('Please provide a valid e-mail and review the form fields.'))
        else:
            email = join_form.cleaned_data['email'].strip().lower()
            name = join_form.cleaned_data['name'].strip()
            message = join_form.cleaned_data['message'].strip()
            obj, created = TaskJoinRequest.objects.get_or_create(
                share_link=share_link,
                email=email,
                defaults={'name': name, 'message': message},
            )
            if created:
                messages.success(
                    request,
                    _('Solicitação enviada! O responsável pela tarefa analisará seu pedido.')
                )
                # Notify the task owner
                _notify_owner_join_request(request, obj, task)
            else:
                # Do not disclose approval/rejection state on a public page.
                # Possession of an e-mail address is not proof of identity.
                messages.info(request, _('Você já solicitou participação nesta tarefa.'))
            already_requested = True
            prefill_email = email

    # Public links expose participant counts, not identities, unless the
    # deployment explicitly opts in after obtaining participant consent.
    stakeholder_qs = task.tasks.filter(type=Task.UserType.STAKEHOLDER).select_related('user')
    executor_qs = task.tasks.filter(type=Task.UserType.EXECUTOR).select_related('user')
    show_participant_names = getattr(settings, 'PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES', False)

    context = {
        'task': task,
        'share_link': share_link,
        'show_participant_names': show_participant_names,
        'stakeholders': stakeholder_qs if show_participant_names else [],
        'executors': executor_qs if show_participant_names else [],
        'stakeholder_count': stakeholder_qs.count(),
        'executor_count': executor_qs.count(),
        'already_requested': already_requested,
        'request_status': request_status,
        'prefill_email': prefill_email,
    }
    return render(request, 'tasks/task_public.html', context)


def _notify_owner_join_request(request, join_request, task):
    """Send an email to the task owner when a new join request arrives."""
    owner = task.user
    if not owner.email:
        return
    try:
        # Check if the user already exists in the system
        existing_user = CustomUser.objects.filter(email__iexact=join_request.email).first()

        review_url = request.build_absolute_uri(
            reverse('task_join_requests', args=[task.id])
        )
        subject = _('Nova solicitação de participação: %(task_name)s') % {'task_name': task.name}

        # Use system name if user exists, otherwise use provided name
        requester_name = join_request.name
        if existing_user:
            requester_name = existing_user.get_full_name() or existing_user.username

        context = {
            'owner_name': owner.get_full_name() or owner.first_name,
            'requester_name': requester_name or join_request.email,
            'requester_email': join_request.email,
            'task_name': task.name,
            'message': join_request.message,
            'review_url': review_url,
            'user_exists': existing_user is not None
        }
        html_message = render_to_string('tasks/emails/join_request_email.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [owner.email],
            html_message=html_message
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Error sending join request email: {e}')


# ────────────────────────────────────────────────────────────────────────────
# Manage join requests – owner approves / rejects
# ────────────────────────────────────────────────────────────────────────────

@login_required
@transaction.atomic
def task_join_requests(request, task_id):
    """List and decide join requests. Decisions are idempotent and locked."""
    task = get_object_or_404(Task, pk=task_id)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    share_link = getattr(task, 'share_link', None)
    join_requests = share_link.join_requests.order_by('-created_at') if share_link else []

    if request.method == 'POST':
        form = JoinRequestDecisionForm(request.POST)
        if not form.is_valid():
            messages.error(request, _('Invalid join-request decision.'))
            return redirect('task_join_requests', task_id=task.id)

        join_req = get_object_or_404(
            TaskJoinRequest.objects.select_for_update(),
            pk=form.cleaned_data['request_id'],
            share_link__task=task,
        )
        if join_req.status != TaskJoinRequest.Status.PENDING:
            messages.info(request, _('This request has already been reviewed.'))
            return redirect('task_join_requests', task_id=task.id)

        action = form.cleaned_data['action']
        if action == 'approve':
            role = form.cleaned_data['role']
            invitation = TaskInvitation.objects.filter(
                email__iexact=join_req.email,
                task=task,
                type=role,
                accepted=False,
            ).order_by('-created_at').first()
            if invitation and invitation.is_expired:
                invitation.delete()
                invitation = None
            if invitation is None:
                invitation = TaskInvitation.objects.create(
                    email=join_req.email,
                    task=task,
                    type=role,
                    invited_by=request.user,
                )

            user = CustomUser.objects.filter(email__iexact=join_req.email).first()
            user_exists = user is not None
            if user_exists:
                assignment, created = TaskUser.objects.get_or_create(
                    task=task,
                    user=user,
                    type=role,
                    defaults={
                        'status': Task.Status.NONE if role == Task.UserType.STAKEHOLDER else Task.Status.DOING,
                    },
                )
                invitation.accepted = True
                invitation.save(update_fields=['accepted'])
                if created and assignment.type == Task.UserType.EXECUTOR:
                    send_task_assignment_notification(request, assignment)

            join_req.status = TaskJoinRequest.Status.APPROVED
            join_req.reviewed_by = request.user
            join_req.reviewed_at = timezone.now()
            join_req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            messages.success(request, _('Solicitação de %(email)s aprovada como %(role)s.') % {
                'email': join_req.email,
                'role': invitation.get_type_display(),
            })
            _notify_requester_decision(
                request,
                join_req,
                approved=True,
                invitation=invitation,
                user_exists=user_exists,
            )
        else:
            join_req.status = TaskJoinRequest.Status.REJECTED
            join_req.reviewed_by = request.user
            join_req.reviewed_at = timezone.now()
            join_req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            messages.info(request, _('Solicitação de %(email)s recusada.') % {'email': join_req.email})
            _notify_requester_decision(request, join_req, approved=False)
        return redirect('task_join_requests', task_id=task.id)

    return render(request, 'tasks/task_join_requests.html', {
        'task': task,
        'share_link': share_link,
        'join_requests': join_requests,
    })

def _notify_requester_decision(request, join_req, approved, invitation=None, user_exists=False):
    """Notify the external requester about the decision."""
    try:
        task = join_req.share_link.task
        if approved:
            subject = _('Solicitação aprovada: %(task_name)s') % {'task_name': task.name}
        else:
            subject = _('Solicitação recusada: %(task_name)s') % {'task_name': task.name}

        invite_url = ""
        if invitation:
            invite_url = request.build_absolute_uri(
                reverse('tasks_accept_invitation', args=[invitation.id])
            )

        context = {
            'requester_name': join_req.name or join_req.email,
            'task_name': task.name,
            'approved': approved,
            'invite_url': invite_url,
            'role_name': invitation.get_type_display() if invitation else "",
            'user_exists': user_exists
        }
        html_message = render_to_string('tasks/emails/join_decision_email.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [join_req.email],
            html_message=html_message
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Error sending join decision email: {e}')

