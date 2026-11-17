import uuid
from accounts.models import CustomUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from django.utils.crypto import get_random_string

class Task(models.Model):
    
    class Meta:
        db_table = 'task'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=0, difficulty__lte=5),
                name='ck_task_difficulty_0_5',
            ),
        ]

    class Status(models.TextChoices):
        DOING = 'DOING', _('Doing')
        PAUSED = 'PAUSED', _('Paused')
        CANCELED = 'CANCELED', _('Canceled')
        DONE = 'DONE', _('Done')
        NONE = 'NONE', _('')
    
    class UserType(models.TextChoices):
        STAKEHOLDER = 'STAKEHOLDER', _('Stakeholder')
        EXECUTOR = 'EXECUTOR', _('Executor')        

    def __str__(self):
        return self.name

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=250, blank=False, null=False)
    description = models.CharField(max_length=250)
    dias = models.PositiveSmallIntegerField(default=0)
    horas = models.PositiveSmallIntegerField(default=0)
    difficulty = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    user = models.ForeignKey(CustomUser, related_name='owner', on_delete=models.DO_NOTHING)
    users = models.ManyToManyField(CustomUser, through='TaskUser')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def stakeholder(self):
        stakeholders = self.tasks.filter(type=self.UserType.STAKEHOLDER).order_by('user__first_name')
        return ", ".join([s.user.first_name for s in stakeholders]) if stakeholders.exists() else "-"

    @property
    def executor(self):
        executors = self.tasks.filter(type=self.UserType.EXECUTOR).order_by('user__first_name')
        return ", ".join([e.user.first_name for e in executors]) if executors.exists() else "-"

class TaskUser(models.Model):
    class Meta:
        db_table = 'task_assignment'
        constraints = [
            models.UniqueConstraint(
                fields=['task', 'user', 'type'],
                name='uq_task_assignment_task_user_type',
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=['EXECUTOR', 'STAKEHOLDER']),
                name='ck_task_assignment_type_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(type='STAKEHOLDER', status='NONE')
                    | models.Q(type='EXECUTOR', status__in=['DOING', 'PAUSED', 'CANCELED', 'DONE'])
                ),
                name='ck_task_assignment_type_status_consistent',
            ),
        ]

    type = models.CharField(max_length=15, choices=Task.UserType.choices)
    user = models.ForeignKey(CustomUser, related_name='users', on_delete=models.CASCADE)
    task = models.ForeignKey(Task, related_name='tasks', on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=Task.Status.choices, default=Task.Status.DOING)

    def save(self, *args, **kwargs):
        if self.type == Task.UserType.STAKEHOLDER:
            self.status = Task.Status.NONE
        elif self.status == Task.Status.NONE:
            self.status = Task.Status.DOING
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.first_name

    @property
    def is_evaluated(self):
        return self.rate.filter(rate_type=TaskRate.RateType.STAKEHOLDER).exists()



class TaskRate(models.Model):
    class Meta:
        db_table = 'task_evaluation'
        constraints = [
            models.UniqueConstraint(
                fields=['taskuser', 'user', 'rate_type'],
                name='uq_task_evaluation_assignment_user_type',
            ),
            models.CheckConstraint(
                condition=models.Q(effectiveness__gte=1, effectiveness__lte=5),
                name='ck_task_evaluation_effectiveness_1_5',
            ),
            models.CheckConstraint(
                condition=(models.Q(environment__isnull=True) | models.Q(environment__gte=1, environment__lte=5)),
                name='ck_task_evaluation_environment_1_5',
            ),
            models.CheckConstraint(
                condition=(models.Q(cognition__isnull=True) | models.Q(cognition__gte=1, cognition__lte=5)),
                name='ck_task_evaluation_cognition_1_5',
            ),
            models.CheckConstraint(
                condition=(models.Q(behavior__isnull=True) | models.Q(behavior__gte=1, behavior__lte=5)),
                name='ck_task_evaluation_behavior_1_5',
            ),
            models.CheckConstraint(
                condition=models.Q(rate_type__in=['SELF', 'STAKEHOLDER']),
                name='ck_task_evaluation_rate_type_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        rate_type='SELF',
                        environment__isnull=False,
                        cognition__isnull=False,
                        behavior__isnull=False,
                    )
                    | models.Q(
                        rate_type='STAKEHOLDER',
                        environment__isnull=True,
                        cognition__isnull=True,
                        behavior__isnull=True,
                    )
                ),
                name='ck_task_evaluation_payload_by_type',
            ),
        ]

    class RateType(models.TextChoices):
        SELF = 'SELF', _('Self Assessment')
        STAKEHOLDER = 'STAKEHOLDER', _('Stakeholder Evaluation')

    environment = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    cognition = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    behavior = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    effectiveness = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    taskuser = models.ForeignKey(TaskUser, related_name='rate', on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, related_name='rate', on_delete=models.CASCADE)
    rate_type = models.CharField(
        max_length=15, 
        choices=RateType.choices, 
        default=RateType.SELF
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.rate_type} - {self.taskuser}"

class TaskInvitation(models.Model):
    class Meta:
        db_table = 'task_invitation'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    task = models.ForeignKey(Task, related_name='invitations', on_delete=models.CASCADE)
    type = models.CharField(max_length=15, choices=Task.UserType.choices)
    invited_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Invite for {self.email} to {self.task.name} as {self.type}"

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=48)


class TaskShareLink(models.Model):
    class Meta:
        db_table = 'task_share_link'

    """Unique shareable link for a task, allowing external users to view it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(Task, related_name='share_link', on_delete=models.CASCADE)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"ShareLink for {self.task.name}"


class TaskJoinRequest(models.Model):
    class Meta:
        db_table = 'task_join_request'
        unique_together = ('share_link', 'email')

    """Request from an external user who wants to participate in a shared task."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    share_link = models.ForeignKey(TaskShareLink, related_name='join_requests', on_delete=models.CASCADE)
    email = models.EmailField()
    name = models.CharField(max_length=150, blank=True, default='')
    message = models.TextField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_requests'
    )

    def __str__(self):
        return f"JoinRequest from {self.email} for {self.share_link.task.name} [{self.status}]"
