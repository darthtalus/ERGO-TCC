import calendar
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tasks.models import Task, TaskUser

from .storage import private_attachment_storage
from .validators import validate_attachment_extension, validate_attachment_size


class TaskComment(models.Model):
    """Collaboration layer for tasks: comments plus optional attachments."""

    class Meta:
        db_table = 'task_comment'
        ordering = ['-created_at']

    task = models.ForeignKey(Task, related_name='upgrade_comments', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='task_comments', on_delete=models.CASCADE)
    content = models.TextField(max_length=2000)
    attachment = models.FileField(
        upload_to='task_attachments/',
        storage=private_attachment_storage,
        validators=[validate_attachment_extension, validate_attachment_size],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment #{self.id} - {self.task}'


class TaskReview(models.Model):
    """Approval workflow layer without changing legacy Task.Status choices."""

    class Meta:
        db_table = 'task_review'
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=['PENDING', 'APPROVED', 'RETURNED']),
                name='ck_task_review_status_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(cycle_number__gte=1),
                name='ck_task_review_cycle_positive',
            ),
        ]

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending review')
        APPROVED = 'APPROVED', _('Approved')
        RETURNED = 'RETURNED', _('Returned for adjustments')

    taskuser = models.ForeignKey(TaskUser, related_name='upgrade_reviews', on_delete=models.CASCADE)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='task_reviews', on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    comment = models.TextField(max_length=2000, blank=True, default='')
    cycle_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    evaluation_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Immutable copy of the self and stakeholder evaluations at review time.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Reviews are append-only audit records. A correction must be recorded
        # as a new review instead of rewriting an earlier decision/snapshot.
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(_('Task reviews are immutable audit records.'))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.taskuser.task} - {self.status}'


class TaskTemplate(models.Model):
    """Reusable task templates with default estimates and checklist text."""

    class Meta:
        db_table = 'task_template'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=0, difficulty__lte=5),
                name='ck_task_template_difficulty_0_5',
            ),
        ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='task_templates', on_delete=models.CASCADE)
    name = models.CharField(max_length=250)
    description = models.CharField(max_length=250, blank=True, default='')
    dias = models.PositiveSmallIntegerField(default=0)
    horas = models.PositiveSmallIntegerField(default=0)
    difficulty = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    checklist = models.TextField(
        blank=True,
        default='',
        help_text=_('One checklist item per line. These items are shown before starting the task.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RecurringTaskRule(models.Model):
    """Simple recurring task generator based on a template."""

    class Meta:
        db_table = 'recurring_task_rule'
        ordering = ['next_run']

    class Frequency(models.TextChoices):
        DAILY = 'DAILY', _('Daily')
        WEEKLY = 'WEEKLY', _('Weekly')
        MONTHLY = 'MONTHLY', _('Monthly')

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='recurring_task_rules', on_delete=models.CASCADE)
    template = models.ForeignKey(TaskTemplate, related_name='recurring_rules', on_delete=models.CASCADE)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.WEEKLY)
    next_run = models.DateField(default=timezone.localdate)
    anchor_day = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(31)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def add_one_month(value, anchor_day=None):
        """Advance by one calendar month while preserving the day when possible."""
        if value.month == 12:
            year, month = value.year + 1, 1
        else:
            year, month = value.year, value.month + 1
        day = min(anchor_day or value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    def next_date_after(self, value=None):
        value = value or self.next_run
        if self.frequency == self.Frequency.DAILY:
            return value + timedelta(days=1)
        if self.frequency == self.Frequency.WEEKLY:
            return value + timedelta(weeks=1)
        return self.add_one_month(value, self.anchor_day or self.next_run.day)

    def save(self, *args, **kwargs):
        if self.anchor_day is None and self.next_run:
            self.anchor_day = self.next_run.day
        super().save(*args, **kwargs)

    def advance_next_run(self):
        if self.anchor_day is None:
            self.anchor_day = self.next_run.day
        self.next_run = self.next_date_after(self.next_run)
        self.save(update_fields=['next_run', 'anchor_day'])

    def __str__(self):
        return f'{self.template.name} ({self.frequency})'


class TaskStartChecklist(models.Model):
    """Pre-task ergonomic checklist, used for preventive risk alerts."""

    class Meta:
        db_table = 'task_start_checklist'
        ordering = ['-created_at']

    taskuser = models.ForeignKey(TaskUser, related_name='start_checklists', on_delete=models.CASCADE)
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='start_checklists', on_delete=models.CASCADE)
    environment_ok = models.BooleanField(default=True)
    lighting_ok = models.BooleanField(default=True)
    noise_ok = models.BooleanField(default=True)
    fatigue_low = models.BooleanField(default=True)
    clarity_ok = models.BooleanField(default=True)
    acceptance_criteria_ok = models.BooleanField(default=True)
    risk_score = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(6)])
    recommendations = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Checklist {self.taskuser.task} - risk {self.risk_score}'


class SensorReading(models.Model):
    """Manual/API sensor reading placeholder for future IoT integrations."""

    class Meta:
        db_table = 'sensor_reading'
        ordering = ['-captured_at']

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sensor_readings', on_delete=models.CASCADE)
    captured_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=120, blank=True, default='manual')
    temperature_c = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(-50), MaxValueValidator(70)])
    humidity_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    noise_db = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(200)])
    luminosity_lux = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(200000)])
    air_quality_index = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(500)])
    note = models.CharField(max_length=250, blank=True, default='')

    def __str__(self):
        return f'{self.user} - {self.captured_at:%Y-%m-%d %H:%M}'

class TaskChecklistItem(models.Model):
    """Operational checklist copied from a task template."""

    class Meta:
        db_table = 'task_checklist_item'
        ordering = ['position', 'id']

    task = models.ForeignKey(Task, related_name='operational_checklist_items', on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    position = models.PositiveSmallIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='completed_task_checklist_items',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.text


class RecurringTaskOccurrence(models.Model):
    """Idempotency record for each scheduled recurring-task occurrence."""

    class Meta:
        db_table = 'recurring_task_occurrence'
        ordering = ['scheduled_for']
        constraints = [
            models.UniqueConstraint(fields=['rule', 'scheduled_for'], name='uq_recurring_rule_scheduled_for'),
        ]

    rule = models.ForeignKey(RecurringTaskRule, related_name='occurrences', on_delete=models.CASCADE)
    scheduled_for = models.DateField()
    task = models.OneToOneField(
        Task,
        related_name='recurring_occurrence',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.rule} - {self.scheduled_for}'


class SensorApiToken(models.Model):
    """Hashed API token for external sensor ingestion."""

    class Meta:
        db_table = 'sensor_api_token'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='sensor_api_token', on_delete=models.CASCADE)
    prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    @classmethod
    def issue_for_user(cls, user):
        raw_key = 'ergo_' + secrets.token_urlsafe(32)
        token, _ = cls.objects.update_or_create(
            user=user,
            defaults={
                'prefix': raw_key[:12],
                'key_hash': cls.hash_key(raw_key),
                'is_active': True,
                'last_used_at': None,
            },
        )
        return token, raw_key

    @classmethod
    def authenticate(cls, raw_key):
        if not raw_key or len(raw_key) < 12:
            return None
        token = cls.objects.select_related('user').filter(prefix=raw_key[:12], is_active=True).first()
        if token and hmac.compare_digest(token.key_hash, cls.hash_key(raw_key)):
            token.last_used_at = timezone.now()
            token.save(update_fields=['last_used_at'])
            return token.user
        return None

    def __str__(self):
        return f'{self.user} - {self.prefix}…'

