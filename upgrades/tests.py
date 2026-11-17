import json
import secrets
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from tasks.models import Task, TaskJoinRequest, TaskRate, TaskUser
from user_aspects.models import Effectiveness

from .forms import TaskCommentForm, TaskTemplateForm, RecurringTaskRuleForm
from tasks.forms import RoleForm, TaskForm
from .models import (
    RecurringTaskOccurrence,
    RecurringTaskRule,
    SensorApiToken,
    SensorReading,
    TaskReview,
    TaskStartChecklist,
    TaskTemplate,
)
from .services import (
    SCOPE_ORGANIZATION,
    compute_dashboard,
    create_task_from_template,
    generate_due_recurring_tasks,
    pseudonymized_user_label,
    suggest_executors,
)


User = get_user_model()


class UpgradeBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', 'owner@example.com', 'test-pass')
        cls.executor = User.objects.create_user('executor', 'executor@example.com', 'test-pass')
        cls.other_executor = User.objects.create_user('executor2', 'executor2@example.com', 'test-pass')
        cls.stakeholder = User.objects.create_user('stakeholder', 'stakeholder@example.com', 'test-pass')
        cls.outsider = User.objects.create_user('outsider', 'outsider@example.com', 'test-pass')
        cls.admin = User.objects.create_user('admin', 'admin@example.com', 'test-pass', role='ADMIN')
        cls.task = Task.objects.create(
            name='Test task',
            description='Description',
            dias=1,
            horas=2,
            difficulty=3,
            user=cls.owner,
        )
        cls.executor_assignment = TaskUser.objects.create(
            task=cls.task,
            user=cls.executor,
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        cls.other_assignment = TaskUser.objects.create(
            task=cls.task,
            user=cls.other_executor,
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        cls.stakeholder_assignment = TaskUser.objects.create(
            task=cls.task,
            user=cls.stakeholder,
            type=Task.UserType.STAKEHOLDER,
            status=Task.Status.NONE,
        )


class PermissionTests(UpgradeBaseTestCase):
    def test_executor_cannot_change_another_executor_status(self):
        self.client.force_login(self.executor)
        response = self.client.post(reverse('upgrades_kanban_update'), {
            'taskuser_id': self.other_assignment.pk,
            'status': Task.Status.DONE,
        })
        self.assertEqual(response.status_code, 403)
        self.other_assignment.refresh_from_db()
        self.assertEqual(self.other_assignment.status, Task.Status.DOING)

    def test_owner_can_change_executor_status(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('upgrades_kanban_update'), {
            'taskuser_id': self.other_assignment.pk,
            'status': Task.Status.PAUSED,
        })
        self.assertEqual(response.status_code, 302)
        self.other_assignment.refresh_from_db()
        self.assertEqual(self.other_assignment.status, Task.Status.PAUSED)

    def test_only_assigned_executor_can_answer_checklist(self):
        payload = {
            f'checklist-{self.executor_assignment.pk}-environment_ok': 'on',
            f'checklist-{self.executor_assignment.pk}-lighting_ok': 'on',
            f'checklist-{self.executor_assignment.pk}-noise_ok': 'on',
            f'checklist-{self.executor_assignment.pk}-fatigue_low': 'on',
            f'checklist-{self.executor_assignment.pk}-clarity_ok': 'on',
            f'checklist-{self.executor_assignment.pk}-acceptance_criteria_ok': 'on',
        }
        self.client.force_login(self.stakeholder)
        denied = self.client.post(
            reverse('upgrades_add_checklist', args=[self.executor_assignment.pk]),
            payload,
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.executor)
        allowed = self.client.post(
            reverse('upgrades_add_checklist', args=[self.executor_assignment.pk]),
            payload,
        )
        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(TaskStartChecklist.objects.filter(taskuser=self.executor_assignment).count(), 1)

    def test_pre_task_checklist_is_rejected_after_completion(self):
        TaskRate.objects.create(
            taskuser=self.executor_assignment,
            user=self.executor,
            rate_type=TaskRate.RateType.SELF,
            environment=4,
            cognition=4,
            behavior=4,
            effectiveness=4,
        )
        self.executor_assignment.status = Task.Status.DONE
        self.executor_assignment.save(update_fields=['status'])
        self.client.force_login(self.executor)
        prefix = f'checklist-{self.executor_assignment.pk}'
        response = self.client.post(
            reverse('upgrades_add_checklist', args=[self.executor_assignment.pk]),
            {f'{prefix}-environment_ok': 'on'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TaskStartChecklist.objects.filter(
            taskuser=self.executor_assignment,
        ).exists())

    def test_review_requires_completed_assignment(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('upgrades_review_assignment', args=[self.executor_assignment.pk]),
            {'status': TaskReview.Status.APPROVED},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskReview.objects.filter(taskuser=self.executor_assignment).exists())

        self.executor_assignment.status = Task.Status.DONE
        self.executor_assignment.save(update_fields=['status'])
        TaskRate.objects.create(
            taskuser=self.executor_assignment,
            user=self.executor,
            rate_type=TaskRate.RateType.SELF,
            environment=4,
            cognition=4,
            behavior=4,
            effectiveness=4,
        )
        TaskRate.objects.create(
            taskuser=self.executor_assignment,
            user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
            effectiveness=4,
        )
        response = self.client.post(
            reverse('upgrades_review_assignment', args=[self.executor_assignment.pk]),
            {'status': TaskReview.Status.APPROVED},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TaskReview.objects.filter(taskuser=self.executor_assignment, status=TaskReview.Status.APPROVED).exists())

    def test_regular_user_does_not_receive_peer_ranking(self):
        self.assertEqual(suggest_executors(self.executor), [])
        self.assertTrue(isinstance(suggest_executors(self.admin), list))


class DashboardWorkflowTests(UpgradeBaseTestCase):
    def test_pending_review_uses_latest_review(self):
        self.executor_assignment.status = Task.Status.DONE
        self.executor_assignment.save(update_fields=['status'])
        TaskReview.objects.create(
            taskuser=self.executor_assignment,
            reviewed_by=self.owner,
            status=TaskReview.Status.APPROVED,
        )
        TaskReview.objects.create(
            taskuser=self.executor_assignment,
            reviewed_by=self.owner,
            status=TaskReview.Status.PENDING,
        )
        dashboard = compute_dashboard(self.owner, scope='personal')
        self.assertEqual(dashboard['cards']['pending_reviews'], 1)

        TaskReview.objects.create(
            taskuser=self.executor_assignment,
            reviewed_by=self.owner,
            status=TaskReview.Status.APPROVED,
        )
        dashboard = compute_dashboard(self.owner, scope='personal')
        self.assertEqual(dashboard['cards']['pending_reviews'], 0)

    def test_organization_daily_rows_are_aggregated_by_day(self):
        Effectiveness.objects.create(user=self.executor, effectiveness=2)
        Effectiveness.objects.create(user=self.other_executor, effectiveness=4)
        dashboard = compute_dashboard(self.admin, scope=SCOPE_ORGANIZATION)
        self.assertEqual(len(dashboard['daily_rows']), 1)
        self.assertEqual(dashboard['daily_rows'][0]['effectiveness'], 3)


class TemplateAndRecurringTests(UpgradeBaseTestCase):
    def test_template_checklist_is_copied_to_task(self):
        template = TaskTemplate.objects.create(
            owner=self.owner,
            name='Report',
            description='Prepare report',
            difficulty=4,
            checklist='Collect data\nReview calculations\nSend report',
        )
        task = create_task_from_template(template)
        self.assertEqual(
            list(task.operational_checklist_items.values_list('text', flat=True)),
            ['Collect data', 'Review calculations', 'Send report'],
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TaskTemplate.objects.create(
                    owner=self.owner,
                    name='Invalid template difficulty',
                    difficulty=8,
                )

    def test_monthly_rule_preserves_anchor_day(self):
        template = TaskTemplate.objects.create(owner=self.owner, name='Monthly', difficulty=1)
        rule = RecurringTaskRule.objects.create(
            owner=self.owner,
            template=template,
            frequency=RecurringTaskRule.Frequency.MONTHLY,
            next_run=date(2025, 1, 31),
        )
        february = rule.next_date_after(date(2025, 1, 31))
        march = rule.next_date_after(february)
        self.assertEqual(february, date(2025, 2, 28))
        self.assertEqual(march, date(2025, 3, 31))

    def test_recurring_generation_catches_up_and_is_idempotent(self):
        template = TaskTemplate.objects.create(owner=self.owner, name='Daily', difficulty=1)
        rule = RecurringTaskRule.objects.create(
            owner=self.owner,
            template=template,
            frequency=RecurringTaskRule.Frequency.DAILY,
            next_run=timezone.localdate() - timedelta(days=2),
        )
        first = generate_due_recurring_tasks(owner=self.owner)
        second = generate_due_recurring_tasks(owner=self.owner)
        self.assertEqual(len(first), 3)
        self.assertEqual(second, [])
        self.assertEqual(RecurringTaskOccurrence.objects.filter(rule=rule).count(), 3)


class SensorApiTests(UpgradeBaseTestCase):
    def setUp(self):
        _, self.raw_key = SensorApiToken.issue_for_user(self.executor)

    def test_post_requires_api_key(self):
        response = self.client.post(
            reverse('upgrades_api_sensors'),
            data=json.dumps({'temperature_c': 20}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_zero_values_are_preserved(self):
        response = self.client.post(
            reverse('upgrades_api_sensors'),
            data=json.dumps({
                'temperature_c': 0,
                'humidity_percent': 0,
                'noise_db': 0,
                'luminosity_lux': 0,
                'air_quality_index': 0,
            }),
            content_type='application/json',
            HTTP_X_ERGO_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, 201)
        reading = SensorReading.objects.get(pk=response.json()['id'])
        self.assertEqual(float(reading.temperature_c), 0)
        self.assertEqual(float(reading.humidity_percent), 0)

    def test_invalid_sensor_range_returns_400(self):
        response = self.client.post(
            reverse('upgrades_api_sensors'),
            data=json.dumps({'humidity_percent': 500}),
            content_type='application/json',
            HTTP_X_ERGO_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SensorReading.objects.filter(user=self.executor).exists())


class AttachmentAndPrivacyTests(UpgradeBaseTestCase):
    def test_rejects_executable_attachment(self):
        form = TaskCommentForm(
            data={'content': 'Unsafe'},
            files={'attachment': SimpleUploadedFile('payload.exe', b'MZ', content_type='application/octet-stream')},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

    def test_pseudonym_is_not_sequential_and_changes_per_export(self):
        first = pseudonymized_user_label(self.executor, secrets.token_bytes(32))
        second = pseudonymized_user_label(self.executor, secrets.token_bytes(32))
        self.assertNotEqual(first, f'U{self.executor.pk:05d}')
        self.assertNotEqual(first, second)


class TranslationTests(TestCase):
    def test_corrected_portuguese_catalog(self):
        with translation.override('pt-br'):
            self.assertEqual(str(TaskReview.Status.APPROVED.label), 'Aprovado')
            self.assertEqual(str(TaskJoinRequest.Status.PENDING.label), 'Pendente')
            self.assertEqual(str(TaskJoinRequest.Status.REJECTED.label), 'Rejeitado')

    def test_portuguese_form_labels_and_duration_options(self):
        with translation.override('pt-br'):
            template = TaskTemplateForm()
            self.assertEqual(str(template.fields['name'].label), 'Nome')
            self.assertEqual(str(template.fields['description'].label), 'Descrição')
            self.assertEqual(str(template.fields['difficulty'].label), 'Dificuldade')
            rule = RecurringTaskRuleForm()
            self.assertEqual(str(rule.fields['frequency'].label), 'Frequência')
            self.assertEqual(str(rule.fields['next_run'].label), 'Próxima execução')
            self.assertEqual(str(RoleForm().fields['type'].label), 'Papel')
            self.assertEqual(str(dict(TaskForm().fields['dias'].choices)[2]), '2 dias')
            self.assertEqual(str(dict(TaskForm().fields['horas'].choices)[4]), '4 horas')
