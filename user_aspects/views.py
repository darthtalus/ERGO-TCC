from django.forms.models import BaseModelForm
from django.shortcuts import render, redirect, get_object_or_404
from user_aspects.forms import AspectForm, UnitForm
from .models import UserAspects, Effectiveness, UserAspectHistory, DimensionUnit, PredefinedAspect
from units.models import Unit
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404, HttpResponse
from django.views.generic.edit import CreateView
from django.views import View
from .forms import EffectForm, PredefinedAspectForm
from django.db import IntegrityError
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required

from django.contrib.auth.decorators import login_required
from datetime import date, datetime, timedelta

@login_required
def redo_effectiveness_confirm(request):
    return render(request, "params/redo_confirm.html")

@login_required
@transaction.atomic
def delete_today_effectiveness(request):
    if request.method == "POST":
        Effectiveness.objects.filter(user=request.user, day=date.today()).delete()
        messages.success(request, _("Today's evaluation has been cleared. You can now record it again."))
        return redirect("tasks_index")
    return redirect("tasks_index")



def index(request):
    queryset = UserAspects.objects.filter(user=request.user)
    cognition = queryset.filter(dimension=UserAspects.Dimension.COGNITION)
    environment = queryset.filter(dimension=UserAspects.Dimension.ENVIRONMENT)
    behavior = queryset.filter(dimension=UserAspects.Dimension.BEHAVIOR)
    end_day = request.session["end"]
    effectiveness_form = EffectForm()
    context = {
        "cognition": cognition,
        "behavior": behavior,
        "environment": environment,
        "end_day": end_day,
        "effectiveness_form": effectiveness_form,
        "has_parameters": cognition.exists() and behavior.exists() and environment.exists(),
    }
    return render(request, "params/index.html", context)

def end_change_params(request):
    request.session['end'] = True
    return redirect('params')

def delete_aspect(request, pk):
    aspect = get_object_or_404(UserAspects, pk=pk, user=request.user)
    aspect.delete()
    return redirect('params')

def edit_aspect(request, pk):
    aspect = get_object_or_404(UserAspects, pk=pk, user=request.user)
    if request.method == "POST":
        form = AspectForm(request.POST, instance=aspect)
        if form.is_valid():
            form.save()
            return redirect('params')
    else:
        form = AspectForm(instance=aspect)
    
    allowed_units = DimensionUnit.objects.filter(dimension=aspect.dimension).values_list('unit__key', flat=True)
    
    context = {
        "form": form,
        "aspect": aspect,
        "allowed_units": allowed_units,
    }
    return render(request, "params/edit.html", context)
    




def new_cognition(request):
    current_lang = request.LANGUAGE_CODE[:2]
    lista = PredefinedAspect.objects.filter(dimension=UserAspects.Dimension.COGNITION, language__startswith=current_lang).values_list('name', flat=True)
    # Fetch allowed units for this dimension
    allowed_units = DimensionUnit.objects.filter(dimension=UserAspects.Dimension.COGNITION).values_list('unit__key', flat=True)
    
    if request.method == "POST":
        form = AspectForm(request.POST)
        form.instance.user = request.user
        if form.is_valid():
            if not form.cleaned_data.get('unidade'):
                form.instance.unidade = "ESCALA1A5"
            form.save()
        return redirect(reverse('params') + "?" + request.GET.urlencode())
    else:
        form = AspectForm(
            initial={"valor": 1, "dimension": UserAspects.Dimension(UserAspects.Dimension.COGNITION)}
        )

    context = {
        "form": form,
        "lista": lista,
        "allowed_units": allowed_units,
    }
    return render(request, "params/new_cognition.html", context)


def new_behavior(request, aspect=None):
    current_lang = request.LANGUAGE_CODE[:2]
    lista = PredefinedAspect.objects.filter(dimension=UserAspects.Dimension.BEHAVIOR, language__startswith=current_lang).values_list('name', flat=True)
    allowed_units = DimensionUnit.objects.filter(dimension=UserAspects.Dimension.BEHAVIOR).values_list('unit__key', flat=True)
    
    if request.method == "POST":
        form = AspectForm(request.POST)
        form.instance.user = request.user
        if form.is_valid():
            form.save()
            return redirect("params")
    else:
        form = AspectForm(initial={"dimension": UserAspects.Dimension(UserAspects.Dimension.BEHAVIOR)})

    context = {
        "form": form,
        "lista": lista,
        "allowed_units": allowed_units,
    }
    return render(request, "params/new_behavior.html", context)


def new_environment(request, aspect=None):
    current_lang = request.LANGUAGE_CODE[:2]
    lista = PredefinedAspect.objects.filter(dimension=UserAspects.Dimension.ENVIRONMENT, language__startswith=current_lang).values_list('name', flat=True)
    allowed_units = DimensionUnit.objects.filter(dimension=UserAspects.Dimension.ENVIRONMENT).values_list('unit__key', flat=True)
    
    if request.method == "POST":
        form = AspectForm(request.POST)
        form.instance.user = request.user
        if form.is_valid():
            form.save()
            return redirect("params")
    else:
        form = AspectForm(initial={"dimension": UserAspects.Dimension(UserAspects.Dimension.ENVIRONMENT)})

    context = {
        "form": form,
        "lista": lista,
        "allowed_units": allowed_units,
    }
    return render(request, "params/new_environment.html", context)


def is_admin(user):
    return user.is_authenticated and (user.role in ['SUPERADMIN', 'ADMIN'] or user.is_superuser)

@user_passes_test(is_admin)
def manage_dimension_units(request):
    if request.method == "POST":
        # Clear existing and re-save
        DimensionUnit.objects.all().delete()
        for key, value in request.POST.items():
            if key.startswith("unit_"):
                # format: unit_DIMENSION_UNITID
                parts = key.split("_")
                if len(parts) >= 3:
                    dim = parts[1]
                    unit_id = parts[2]
                    try:
                        unit_obj = Unit.objects.get(id=unit_id)
                        DimensionUnit.objects.create(dimension=dim, unit=unit_obj)
                    except Unit.DoesNotExist:
                        continue
        messages.success(request, _("Unit configurations updated successfully."))
        return redirect('manage_dimension_units')

    dimensions = [
        {'key': 'COGNITION', 'label': _('Cognition')},
        {'key': 'BEHAVIOR', 'label': _('Behavior')},
        {'key': 'ENVIRONMENT', 'label': _('Environment')},
    ]
    
    units = Unit.objects.all()
    
    # Matrix of dimension vs units
    matrix = []
    for dim in dimensions:
        row = {'dim': dim, 'units': []}
        for unit in units:
            is_active = DimensionUnit.objects.filter(dimension=dim['key'], unit=unit).exists()
            row['units'].append({'unit': unit, 'active': is_active})
        matrix.append(row)

    context = {
        "dimensions": dimensions,
        "units": units,
        "matrix": matrix,
    }
    return render(request, "params/manage_units.html", context)

class EffectivenessView(View):
    @transaction.atomic
    def post(self, request):
        # 0. Check if user has at least one parameter in EACH dimension
        uas = UserAspects.objects.filter(user=request.user)
        missing_dims = []
        if not uas.filter(dimension=UserAspects.Dimension.ENVIRONMENT).exists(): missing_dims.append(_("Environment"))
        if not uas.filter(dimension=UserAspects.Dimension.COGNITION).exists(): missing_dims.append(_("Cognition"))
        if not uas.filter(dimension=UserAspects.Dimension.BEHAVIOR).exists(): missing_dims.append(_("Behavior"))

        if missing_dims:
            messages.warning(request, _("You need to define at least one parameter in EACH dimension (Environment, Cognition, and Behavior) before finishing the day. Missing: ") + ", ".join(missing_dims))
            return redirect("params")

        # 1. Check if already exists before attempting to save
        if Effectiveness.objects.filter(user=request.user, day=date.today()).exists():
            return redirect("redo_effectiveness_confirm")

        form = EffectForm(request.POST)
        uas = UserAspects.objects.filter(user=request.user)

        if form.is_valid():
            try:
                form.instance.user = request.user
                obj = form.save()
                new_uahs = []
                for ua in uas:
                    uah = UserAspectHistory(
                        dimension=ua.dimension,
                        nome=ua.nome,
                        valor=ua.valor,
                        parametrized=ua.parametrized,
                        watched=ua.watched,
                        unidade=ua.unidade,
                        effectiveness_id=obj.id,
                    )
                    new_uahs.append(uah)
                UserAspectHistory.objects.bulk_create(new_uahs)
            except IntegrityError:
                return redirect("redo_effectiveness_confirm")

            messages.success(request, _("Day finished successfully! Check your statistics."))
            return redirect("statistics")

        return redirect("tasks_index")


@user_passes_test(is_admin)
def list_create_units(request):
    if request.method == "POST":
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.key = unit.name.upper().replace(" ", "_")[:50]
            
            if Unit.objects.filter(key=unit.key).exists():
                messages.error(request, _("A unit with a similar name or key already exists."))
            else:
                try:
                    unit.save()
                    messages.success(request, _("Unit registered successfully."))
                    return redirect('list_create_units')
                except IntegrityError:
                    messages.error(request, _("Error: This unit is already registered."))
    else:
        form = UnitForm()
    
    units = Unit.objects.all().order_by('name')
    context = {
        "form": form,
        "units": units,
    }
    return render(request, "params/manage_unit_list.html", context)


@user_passes_test(is_admin)
def delete_unit(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    unit.delete()
    messages.success(request, _("Unit deleted successfully."))
    return redirect('list_create_units')


@user_passes_test(is_admin)
def manage_predefined_aspects(request):
    if request.method == "POST":
        form = PredefinedAspectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Suggested aspect added successfully."))
            return redirect('manage_predefined_aspects')
    else:
        form = PredefinedAspectForm()

    aspects = PredefinedAspect.objects.all().order_by('dimension', 'name')
    context = {
        "form": form,
        "aspects": aspects,
    }
    return render(request, "params/manage_predefined_aspects.html", context)


@user_passes_test(is_admin)
def delete_predefined_aspect(request, pk):
    aspect = get_object_or_404(PredefinedAspect, pk=pk)
    aspect.delete()
    messages.success(request, _("Suggested aspect deleted successfully."))
    return redirect('manage_predefined_aspects')

import csv
from django.http import HttpResponse


@user_passes_test(is_admin)
def export_reports_index(request):
    return render(request, "params/export_reports.html")

@user_passes_test(is_admin)
def export_effectiveness_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ergo_effectiveness_report_{date.today()}.csv"'
    
    # Write UTF-8 BOM for Excel compatibility
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    
    writer.writerow([
        _('User ID'),
        _('User Email'), 
        _('User Name'), 
        _('Company'),
        _('Country'),
        _('Birthdate'),
        _('Date Joined'),
        _('Last Login'),
        _('Is Active'),
        _('Date'), 
        _('Effectiveness Score'),
        _('Dimension'), 
        _('Aspect Name'), 
        _('Value'), 
        _('Parametrized Score'), 
        _('Unit')
    ])
    
    histories = UserAspectHistory.objects.select_related('effectiveness', 'effectiveness__user').all().order_by('-effectiveness__day', 'effectiveness__user__email')
    
    for h in histories:
        u = h.effectiveness.user
        writer.writerow([
            u.id,
            u.email,
            f"{u.first_name} {u.last_name}",
            u.company or '',
            u.country or '',
            u.birthdate or '',
            u.date_joined.date(),
            u.last_login.date() if u.last_login else '',
            _('Yes') if u.is_active else _('No'),
            h.effectiveness.day,
            h.effectiveness.effectiveness,
            h.get_dimension_display(),
            h.nome,
            h.valor,
            h.parametrized,
            h.unidade
        ])
    
    return response


from accounts.models import CustomUser
from tasks.models import Task, TaskUser, TaskRate
from django.db.models import Avg, Count, Q

@user_passes_test(is_admin)
def export_task_evaluations_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ergo_task_evaluations_{date.today()}.csv"'
    
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    
    writer.writerow([
        _('Task ID'), 
        _('Task Name'), 
        _('User ID'),
        _('Executor/Stakeholder Email'), 
        _('Company'),
        _('Country'),
        _('Birthdate'),
        _('Date Joined'),
        _('Last Login'),
        _('Is Active'),
        _('Evaluation Type'), 
        _('Date'), 
        _('Environment'), 
        _('Cognition'), 
        _('Behavior'), 
        _('Effectiveness')
    ])
    
    rates = TaskRate.objects.select_related('taskuser__task', 'user').all().order_by('-created_at')
    
    for r in rates:
        u = r.user
        writer.writerow([
            r.taskuser.task.id,
            r.taskuser.task.name,
            u.id if u else '',
            u.email if u else '',
            u.company if u else '',
            u.country if u else '',
            u.birthdate if u else '',
            u.date_joined.date() if u else '',
            u.last_login.date() if u and u.last_login else '',
            _('Yes') if u and u.is_active else (_('No') if u else ''),
            r.get_rate_type_display(),
            r.created_at.date(),
            r.environment if r.environment is not None else '',
            r.cognition if r.cognition is not None else '',
            r.behavior if r.behavior is not None else '',
            r.effectiveness
        ])
    
    return response


@user_passes_test(is_admin)
def export_complete_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ergo_complete_{date.today()}.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)

    writer.writerow([
        # User demographics
        _('User ID'),
        _('Username'),
        _('Full Name'),
        _('Email'),
        _('Role'),
        _('Company'),
        _('Country'),
        _('Birthdate'),
        _('Date Joined'),
        _('Last Login'),
        _('Is Active'),
        # Daily record
        _('Date'),
        _('Daily Effectiveness'),
        # ABC dimension averages from aspects
        _('Avg Environment'),
        _('Avg Cognition'),
        _('Avg Behavior'),
        # Self evaluations that day
        _('Self Evaluations Count'),
        _('Self Avg Environment'),
        _('Self Avg Cognition'),
        _('Self Avg Behavior'),
        _('Self Avg Effectiveness'),
        # Stakeholder evaluations that day
        _('Stakeholder Evaluations Count'),
        _('Stakeholder Avg Environment'),
        _('Stakeholder Avg Cognition'),
        _('Stakeholder Avg Behavior'),
        _('Stakeholder Avg Effectiveness'),
        # User global stats
        _('Total Daily Records'),
        _('User Avg Daily Effectiveness'),
        _('Total Tasks Created'),
        _('Total Assignments as Executor'),
        _('Total Assignments as Stakeholder'),
        _('Total Self Evaluations'),
        _('Total Stakeholder Evaluations Received'),
    ])

    today = date.today()
    users = CustomUser.objects.all().order_by('id')

    for user_obj in users:
        user_global = {
            'total_daily': Effectiveness.objects.filter(user=user_obj).count(),
            'avg_daily': Effectiveness.objects.filter(user=user_obj).aggregate(avg=Avg('effectiveness'))['avg'],
            'tasks_created': Task.objects.filter(user=user_obj).count(),
            'executor_assignments': TaskUser.objects.filter(user=user_obj, type=Task.UserType.EXECUTOR).count(),
            'stakeholder_assignments': TaskUser.objects.filter(user=user_obj, type=Task.UserType.STAKEHOLDER).count(),
            'self_evals': TaskRate.objects.filter(taskuser__user=user_obj, rate_type=TaskRate.RateType.SELF).count(),
            'stakeholder_evals_received': TaskRate.objects.filter(
                taskuser__user=user_obj, rate_type=TaskRate.RateType.STAKEHOLDER
            ).count(),
        }

        daily_records = Effectiveness.objects.filter(user=user_obj).select_related('user').order_by('day')

        for eff in daily_records:
            env = UserAspectHistory.objects.filter(
                effectiveness=eff, dimension=UserAspects.Dimension.ENVIRONMENT
            ).aggregate(avg=Avg('parametrized'))['avg'] or 0
            cog = UserAspectHistory.objects.filter(
                effectiveness=eff, dimension=UserAspects.Dimension.COGNITION
            ).aggregate(avg=Avg('parametrized'))['avg'] or 0
            beh = UserAspectHistory.objects.filter(
                effectiveness=eff, dimension=UserAspects.Dimension.BEHAVIOR
            ).aggregate(avg=Avg('parametrized'))['avg'] or 0

            self_agg = TaskRate.objects.filter(
                taskuser__user=user_obj, rate_type=TaskRate.RateType.SELF, created_at__date=eff.day
            ).aggregate(
                cnt=Count('id'), e=Avg('effectiveness'),
                env=Avg('environment'), cog=Avg('cognition'), beh=Avg('behavior')
            )
            stake_agg = TaskRate.objects.filter(
                taskuser__user=user_obj, rate_type=TaskRate.RateType.STAKEHOLDER, created_at__date=eff.day
            ).aggregate(
                cnt=Count('id'), e=Avg('effectiveness'),
                env=Avg('environment'), cog=Avg('cognition'), beh=Avg('behavior')
            )

            writer.writerow([
                user_obj.id,
                user_obj.username,
                f"{user_obj.first_name} {user_obj.last_name}".strip(),
                user_obj.email,
                user_obj.get_role_display(),
                user_obj.company or '',
                user_obj.country or '',
                user_obj.birthdate or '',
                user_obj.date_joined.date(),
                user_obj.last_login.strftime('%Y-%m-%d %H:%M') if user_obj.last_login else '',
                _('Yes') if user_obj.is_active else _('No'),
                eff.day,
                eff.effectiveness,
                round(env, 2),
                round(cog, 2),
                round(beh, 2),
                self_agg['cnt'] or 0,
                round(self_agg['env'], 2) if self_agg['cnt'] and self_agg['env'] is not None else '',
                round(self_agg['cog'], 2) if self_agg['cnt'] and self_agg['cog'] is not None else '',
                round(self_agg['beh'], 2) if self_agg['cnt'] and self_agg['beh'] is not None else '',
                round(self_agg['e'], 2) if self_agg['cnt'] and self_agg['e'] is not None else '',
                stake_agg['cnt'] or 0,
                round(stake_agg['env'], 2) if stake_agg['cnt'] and stake_agg['env'] is not None else '',
                round(stake_agg['cog'], 2) if stake_agg['cnt'] and stake_agg['cog'] is not None else '',
                round(stake_agg['beh'], 2) if stake_agg['cnt'] and stake_agg['beh'] is not None else '',
                round(stake_agg['e'], 2) if stake_agg['cnt'] and stake_agg['e'] is not None else '',
                user_global['total_daily'],
                round(user_global['avg_daily'], 2) if user_global['avg_daily'] else '',
                user_global['tasks_created'],
                user_global['executor_assignments'],
                user_global['stakeholder_assignments'],
                user_global['self_evals'],
                user_global['stakeholder_evals_received'],
            ])

    return response


import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64
import urllib.parse
import os
from django.db.models import Avg, Q

from django.db.models.functions import TruncDate

@user_passes_test(is_admin)
def dashboard_estatisticas(request):
    # 0. Date Filters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Defaults: All time by default
    today = date.today()
    default_start = date(2000, 1, 1) 
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
    except:
        start_date = default_start
        
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except:
        end_date = today

    company_filter = request.GET.get('company')
    country_filter = request.GET.get('country')

    from django.utils.timezone import make_aware
    from datetime import time
    
    # Boundary datetimes for TaskRate filtering (DateTimeField)
    start_dt = make_aware(datetime.combine(start_date, time.min))
    end_dt = make_aware(datetime.combine(end_date, time.max))

    # 1. Base Querysets
    task_rates_filtered = TaskRate.objects.filter(created_at__range=[start_dt, end_dt])
    history_filtered = UserAspectHistory.objects.filter(effectiveness__day__range=[start_date, end_date])
    daily_logs_filtered = Effectiveness.objects.filter(day__range=[start_date, end_date])

    # Apply Company/Country Filters
    if company_filter:
        task_rates_filtered = task_rates_filtered.filter(user__company=company_filter)
        history_filtered = history_filtered.filter(effectiveness__user__company=company_filter)
        daily_logs_filtered = daily_logs_filtered.filter(user__company=company_filter)
    
    if country_filter:
        task_rates_filtered = task_rates_filtered.filter(user__country=country_filter)
        history_filtered = history_filtered.filter(effectiveness__user__country=country_filter)
        daily_logs_filtered = daily_logs_filtered.filter(user__country=country_filter)

    # 2. Aggregations
    avg_self = task_rates_filtered.filter(rate_type=TaskRate.RateType.SELF).aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0
    avg_stakeholder = task_rates_filtered.filter(rate_type=TaskRate.RateType.STAKEHOLDER).aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0
    
    avg_dims = {
        'avg_env': history_filtered.filter(dimension='ENVIRONMENT').aggregate(Avg('parametrized'))['parametrized__avg'] or 0,
        'avg_cog': history_filtered.filter(dimension='COGNITION').aggregate(Avg('parametrized'))['parametrized__avg'] or 0,
        'avg_beh': history_filtered.filter(dimension='BEHAVIOR').aggregate(Avg('parametrized'))['parametrized__avg'] or 0,
    }
    
    # --- GRAPH 1: Effectiveness Comparison ---
    plt.figure(figsize=(8, 5))
    sns.set_style("whitegrid")
    col_label_1 = _('Evaluation')
    col_val_1 = _('Average')
    eff_data = pd.DataFrame({
        col_label_1: [_('Self Assessment'), _('Stakeholder Evaluation')],
        col_val_1: [avg_self, avg_stakeholder]
    })
    ax1 = sns.barplot(x=col_label_1, y=col_val_1, data=eff_data, hue=col_label_1, palette='viridis', legend=False)
    for i in ax1.containers:
        ax1.bar_label(i, fmt='%.2f', padding=3)
    plt.title(_('Effectiveness Comparison: Self vs Stakeholder'))
    plt.ylabel(_('Score (1-5)'))
    plt.ylim(0, 5.5)
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='png', bbox_inches='tight', dpi=100)
    buf1.seek(0)
    uri_eff = urllib.parse.quote(base64.b64encode(buf1.read()))
    plt.close()
    
    # --- GRAPH 2: Dimensions Analysis ---
    plt.figure(figsize=(8, 5))
    col_label_2 = _('Dimension')
    col_val_2 = _('Average')
    dim_data = pd.DataFrame({
        col_label_2: [_('Environment'), _('Cognition'), _('Behavior')],
        col_val_2: [avg_dims['avg_env'] or 0, avg_dims['avg_cog'] or 0, avg_dims['avg_beh'] or 0]
    })
    ax2 = sns.barplot(x=col_label_2, y=col_val_2, data=dim_data, hue=col_label_2, palette='magma', legend=False)
    for i in ax2.containers:
        ax2.bar_label(i, fmt='%.2f', padding=3)
    plt.title(_('Impact Analysis: ABC Dimensions'))
    plt.ylabel(_('Average Score'))
    plt.ylim(0, 5.5)
    buf2 = io.BytesIO()
    plt.savefig(buf2, format='png', bbox_inches='tight', dpi=100)
    buf2.seek(0)
    uri_dims = urllib.parse.quote(base64.b64encode(buf2.read()))
    plt.close()

    # --- NEW GRAPH 3: Evolution (Daily Log vs. Task Evaluations) ---
    # Aggregate Daily Effectiveness by Date (DateField is direct)
    daily_eff = daily_logs_filtered.values('day').annotate(avg=Avg('effectiveness')).order_by('day')
    df_daily = pd.DataFrame(list(daily_eff))
    if not df_daily.empty:
        df_daily.rename(columns={'day': 'date'}, inplace=True)
    
    # Aggregate Task Evaluation by Date (Python-level fallback for SQLite/TruncDate issues)
    all_task_rates = task_rates_filtered.values('created_at', 'effectiveness')
    task_list = []
    for tr in all_task_rates:
        if tr['created_at']:
            task_list.append({
                'date': tr['created_at'].date() if hasattr(tr['created_at'], 'date') else tr['created_at'],
                'effectiveness': tr['effectiveness']
            })
    
    if task_list:
        df_task = pd.DataFrame(task_list)
        # Group by date and calculate mean
        df_task = df_task.groupby('date')['effectiveness'].mean().reset_index()
        df_task.rename(columns={'effectiveness': 'avg'}, inplace=True)
    else:
        df_task = pd.DataFrame()
    
    plt.figure(figsize=(10, 5))
    has_data = False

    if not df_daily.empty:
        df_daily = df_daily.dropna(subset=['date'])
        if not df_daily.empty:
            df_daily['date'] = pd.to_datetime(df_daily['date'])
            sns.lineplot(x='date', y='avg', data=df_daily, label=_('Daily Log Effectiveness'), marker='o', color='#1A4645', linewidth=2.5)
            has_data = True
    
    if not df_task.empty:
        df_task = df_task.dropna(subset=['date'])
        if not df_task.empty:
            df_task['date'] = pd.to_datetime(df_task['date'])
            sns.lineplot(x='date', y='avg', data=df_task, label=_('Task-level Effectiveness'), marker='s', color='#ea580c', linewidth=2.5)
            has_data = True
    
    if not has_data:
        plt.text(0.5, 0.5, _('No historical data available for this period'), 
                 horizontalalignment='center', verticalalignment='center', 
                 fontsize=14, color='gray', transform=plt.gca().transAxes)
    else:
        # Add horizontal reference lines for overall averages
        if not df_daily.empty:
            avg_logs = daily_logs_filtered.aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0
            plt.axhline(y=avg_logs, color='#1A4645', linestyle='--', alpha=0.4, linewidth=1.5,
                        label=f"{_('Overall Mean (Logs)')}: {avg_logs:.2f}")
            
        if not df_task.empty:
            avg_tasks = task_rates_filtered.aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0
            plt.axhline(y=avg_tasks, color='#ea580c', linestyle='--', alpha=0.4, linewidth=1.5,
                        label=f"{_('Overall Mean (Tasks)')}: {avg_tasks:.2f}")
        
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    
    plt.title(_('Evolution: Daily Log vs. Task Evaluations'), fontweight='bold', pad=15)
    plt.ylabel(_('Average Score'), fontsize=10)
    plt.xlabel(_('Date'), fontsize=10)
    plt.ylim(0.5, 5.5)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(frameon=True, shadow=True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buf3 = io.BytesIO()
    plt.savefig(buf3, format='png', bbox_inches='tight', dpi=100)
    buf3.seek(0)
    uri_trend = urllib.parse.quote(base64.b64encode(buf3.read()))
    plt.close()

    # 3. Summary Table
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resumo_estatistico_ergo.csv')
    avg_daily_total = daily_logs_filtered.aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0
    
    summary_data = {
        'Métrica': [
            _('General Average Effectiveness (Daily Logs)'),
            _('Average Effectiveness (Executors)'),
            _('Average Effectiveness (Stakeholders)'),
            _('General Average Effectiveness (Tasks)'),
            _('Total Task Evaluations'),
            _('Total Daily Logs'),
            _('Average Environmental Impact'),
            _('Average Cognitive Impact'),
            _('Average Behavioral Impact')
        ],
        'Valor': [
            round(avg_daily_total, 2),
            round(avg_self, 2),
            round(avg_stakeholder, 2),
            round(task_rates_filtered.aggregate(Avg('effectiveness'))['effectiveness__avg'] or 0, 2),
            task_rates_filtered.count(),
            daily_logs_filtered.count(),
            round(avg_dims['avg_env'] or 0, 2),
            round(avg_dims['avg_cog'] or 0, 2),
            round(avg_dims['avg_beh'] or 0, 2)
        ]
    }
    pd.DataFrame(summary_data).to_csv(csv_path, index=False, encoding='utf-8')
    
    try:
        df = pd.read_csv(csv_path)
        # Use localized strings for detection
        label_total = _('Total')
        def fmt_valor(row):
            val = row['Valor']
            metrica = row['Métrica']
            # If it's a 'Total' metric or an integer > 5 (unlikely to be an average 1-5)
            if label_total in metrica or (val == int(val) and abs(val) > 5):
                return str(int(val))
            return f"{val:.2f}"
        df['Valor'] = df.apply(fmt_valor, axis=1)
        table_html = df.to_html(classes='table table-bordered table-striped table-hover mt-3', index=False, escape=False)
    except Exception as e:
        table_html = f"<p class='text-danger'>Error: {e}</p>"

    from accounts.models import CustomUser
    all_companies = CustomUser.objects.exclude(company__isnull=True).exclude(company='').values_list('company', flat=True).distinct().order_by('company')
    all_countries = CustomUser.objects.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct().order_by('country')

    context = {
        'uri_eff': uri_eff,
        'uri_dims': uri_dims,
        'uri_trend': uri_trend,
        'table_summary': table_html,
        'start_date': start_date_str or '',
        'end_date': end_date_str or end_date.strftime('%Y-%m-%d'),
        'company_filter': company_filter or '',
        'country_filter': country_filter or '',
        'all_companies': all_companies,
        'all_countries': all_countries,
    }
    return render(request, "params/dashboard_estatisticas.html", context)

@user_passes_test(is_admin)
def download_summary_csv(request):
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resumo_estatistico_ergo.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="text/csv")
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(csv_path)
            return response
    messages.error(request, _("Summary file not found. Try visiting the dashboard first to generate it."))
    return redirect('dashboard_estatisticas')

from django.db.models.functions import TruncDate

@user_passes_test(is_admin)
def dashboard_estatisticas_extended(request):
    # (The previous logic will be inside here, I'll replace the old function)
    pass

@user_passes_test(is_admin)
def export_daily_summary_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ergo_daily_summary_{date.today()}.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    
    writer.writerow([
        _('User ID'),
        _('User Email'), 
        _('User Name'), 
        _('Company'),
        _('Country'),
        _('Birthdate'),
        _('Date Joined'),
        _('Last Login'),
        _('Is Active'),
        _('Date'), 
        _('Daily Effectiveness'),
        _('Avg Environment'), 
        _('Avg Cognition'), 
        _('Avg Behavior')
    ])
    
    # Query all effectiveness records
    eff_records = Effectiveness.objects.select_related('user').all().order_by('-day', 'user__email')
    
    for e in eff_records:
        u = e.user
        # Calculate averages for this specific effectiveness record
        avgs = e.history.aggregate(
            env=Avg('parametrized', filter=Q(dimension=UserAspects.Dimension.ENVIRONMENT)),
            cog=Avg('parametrized', filter=Q(dimension=UserAspects.Dimension.COGNITION)),
            beh=Avg('parametrized', filter=Q(dimension=UserAspects.Dimension.BEHAVIOR))
        )
        
        writer.writerow([
            u.id,
            u.email,
            f"{u.first_name} {u.last_name}",
            u.company or '',
            u.country or '',
            u.birthdate or '',
            u.date_joined.date(),
            u.last_login.date() if u.last_login else '',
            _('Yes') if u.is_active else _('No'),
            e.day,
            e.effectiveness,
            round(avgs['env'] or 0, 2),
            round(avgs['cog'] or 0, 2),
            round(avgs['beh'] or 0, 2)
        ])
    
    return response
