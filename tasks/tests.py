"""Regression and end-to-end tests for the task workflow.

The suite exercises authorization, valid/invalid state transitions, rating
validation, review cycles and data-integrity constraints through HTTP views.
Run with:
    python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
"""
from __future__ import annotations
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from upgrades.models import TaskReview, TaskStartChecklist

from .models import Task, TaskInvitation, TaskRate, TaskUser


User = get_user_model()


class TaskFlowBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner-flow', 'owner-flow@example.com', 'pass')
        cls.executor = User.objects.create_user('executor-flow', 'executor-flow@example.com', 'pass')
        cls.executor2 = User.objects.create_user('executor2-flow', 'executor2-flow@example.com', 'pass')
        cls.stakeholder = User.objects.create_user('stakeholder-flow', 'stakeholder-flow@example.com', 'pass')
        cls.stakeholder2 = User.objects.create_user('stakeholder2-flow', 'stakeholder2-flow@example.com', 'pass')
        cls.outsider = User.objects.create_user('outsider-flow', 'outsider-flow@example.com', 'pass')
        cls.admin = User.objects.create_user('admin-flow', 'admin-flow@example.com', 'pass', role='ADMIN')
        cls.task = Task.objects.create(
            name='Validated flow', description='End-to-end task', dias=1, horas=2,
            difficulty=3, user=cls.owner,
        )
        cls.assignment = TaskUser.objects.create(
            task=cls.task, user=cls.executor, type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        cls.assignment2 = TaskUser.objects.create(
            task=cls.task, user=cls.executor2, type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        cls.stakeholder_role = TaskUser.objects.create(
            task=cls.task, user=cls.stakeholder, type=Task.UserType.STAKEHOLDER,
        )
        cls.stakeholder_role2 = TaskUser.objects.create(
            task=cls.task, user=cls.stakeholder2, type=Task.UserType.STAKEHOLDER,
        )

    def status_post(self, user, assignment, status):
        self.client.force_login(user)
        return self.client.post(reverse('tasks_change'), {
            'taskuser_id': assignment.pk,
            'status': status,
        })

    def complete_post(self, user, assignment, **overrides):
        payload = {
            'taskuser_id': assignment.pk,
            'environmentRadio': '4',
            'cognitionRadio': '4',
            'behaviorRadio': '4',
            'effectiveness': '4',
        }
        payload.update(overrides)
        self.client.force_login(user)
        return self.client.post(reverse('tasks_change_done'), payload)

    def evaluate_post(self, user, assignment, value='5'):
        self.client.force_login(user)
        return self.client.post(reverse('stakeholder_evaluate'), {
            'taskuser_id': assignment.pk,
            'effectiveness': value,
        })


class OwnerTaskListingTests(TaskFlowBase):
    def test_task_with_mixed_executor_statuses_appears_once(self):
        TaskUser.objects.filter(pk=self.assignment2.pk).update(status=Task.Status.DONE)
        unassigned = Task.objects.create(
            name='Unassigned task', description='No executor yet', dias=1,
            horas=2, difficulty=3, user=self.owner,
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse('tasks_created_by_me'))
        self.assertEqual(response.status_code, 200)
        page = response.context['mytasks']
        self.assertEqual([task.pk for task in page], [self.task.pk, unassigned.pk])
        self.assertEqual(page.paginator.count, 2)
        self.assertEqual(response.context['status_counts']['ALL'], 2)
        self.assertContains(response, 'No executor assigned', count=1)

    def test_owner_status_filter_deduplicates_mixed_assignments(self):
        TaskUser.objects.filter(pk=self.assignment2.pk).update(status=Task.Status.DONE)
        self.client.force_login(self.owner)
        for status in (Task.Status.DOING, Task.Status.DONE):
            with self.subTest(status=status):
                response = self.client.get(reverse('tasks_created_by_me'), {'status': status})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([task.pk for task in response.context['mytasks']], [self.task.pk])


class TaskCreationAndEditingTests(TaskFlowBase):
    def _task_payload(self, *, name='Created through HTTP', executor=None, stakeholder=None):
        executor = executor or self.outsider
        stakeholder = stakeholder or self.stakeholder2
        return {
            'name': name,
            'description': 'Created by validated form',
            'dias': '1',
            'horas': '2',
            'difficulty': '3',
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-user': str(executor.pk),
            'form-0-type': Task.UserType.EXECUTOR,
            'form-1-user': str(stakeholder.pk),
            'form-1-type': Task.UserType.STAKEHOLDER,
            'total_invitations': '0',
        }

    def test_owner_creates_task_with_normalized_assignments(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tasks_new'), self._task_payload())
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(name='Created through HTTP')
        self.assertEqual(task.user, self.owner)
        self.assertEqual(
            task.tasks.get(user=self.outsider, type=Task.UserType.EXECUTOR).status,
            Task.Status.DOING,
        )
        self.assertEqual(
            task.tasks.get(user=self.stakeholder2, type=Task.UserType.STAKEHOLDER).status,
            Task.Status.NONE,
        )

    def test_duplicate_formset_role_is_rejected_without_creating_task(self):
        payload = self._task_payload(name='Must not exist')
        payload['form-1-user'] = payload['form-0-user']
        payload['form-1-type'] = payload['form-0-type']
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tasks_new'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(name='Must not exist').exists())

    def test_owner_edits_task_and_removes_only_history_free_assignment(self):
        payload = {
            'name': 'Edited task',
            'description': self.task.description,
            'dias': str(self.task.dias),
            'horas': str(self.task.horas),
            'difficulty': str(self.task.difficulty),
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-user': str(self.executor.pk),
            'form-0-type': Task.UserType.EXECUTOR,
            'form-1-user': str(self.stakeholder.pk),
            'form-1-type': Task.UserType.STAKEHOLDER,
            'total_invitations': '0',
        }
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tasks_edit', args=[self.task.pk]), payload)
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.name, 'Edited task')
        self.assertFalse(TaskUser.objects.filter(pk=self.assignment2.pk).exists())
        self.assertFalse(TaskUser.objects.filter(pk=self.stakeholder_role2.pk).exists())


class TaskAuthorizationTests(TaskFlowBase):
    def test_outsider_cannot_edit_delete_or_manage_roles(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('tasks_edit', args=[self.task.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('tasks_delete', args=[self.task.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('tasks_roles', args=[self.task.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('tasks_role_new', args=[self.task.pk]), {
            'user': self.outsider.pk, 'type': Task.UserType.EXECUTOR,
        }).status_code, 403)

    def test_task_deletion_is_allowed_before_history_and_blocked_after_history(self):
        disposable = Task.objects.create(
            name='Disposable',
            description='No workflow history',
            user=self.owner,
        )
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tasks_delete', args=[disposable.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=disposable.pk).exists())

        self.complete_post(self.executor, self.assignment)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tasks_delete', args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_django_superuser_is_privileged_without_manual_role_promotion(self):
        root = User.objects.create_superuser(
            'root-flow', 'root-flow@example.com', 'pass',
        )
        self.assertEqual(root.role, 'USUARIO')
        self.client.force_login(root)
        self.assertEqual(
            self.client.get(reverse('tasks_edit', args=[self.task.pk])).status_code,
            200,
        )
        response = self.client.post(reverse('tasks_change'), {
            'taskuser_id': self.assignment.pk,
            'status': Task.Status.PAUSED,
        })
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.PAUSED)

    def test_role_delete_is_post_only_and_owner_authorized(self):
        self.client.force_login(self.owner)
        url = reverse('tasks_role_delete', args=[self.assignment2.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskUser.objects.filter(pk=self.assignment2.pk).exists())

    def test_assignment_with_history_cannot_be_removed(self):
        self.complete_post(self.executor, self.assignment)
        self.client.force_login(self.owner)
        self.client.post(reverse('tasks_role_delete', args=[self.assignment.pk]))
        self.assertTrue(TaskUser.objects.filter(pk=self.assignment.pk).exists())

    def test_reminder_is_post_only_and_executor_only(self):
        self.client.force_login(self.stakeholder)
        self.assertEqual(
            self.client.get(reverse('send_task_reminder', args=[self.assignment.pk])).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(reverse('send_task_reminder', args=[self.stakeholder_role.pk])).status_code,
            403,
        )


class StatusTransitionTests(TaskFlowBase):
    def test_executor_manages_only_their_own_nonfinal_status(self):
        response = self.status_post(self.executor, self.assignment2, Task.Status.PAUSED)
        self.assertEqual(response.status_code, 403)
        self.assignment2.refresh_from_db()
        self.assertEqual(self.assignment2.status, Task.Status.DOING)

        for status in (Task.Status.PAUSED, Task.Status.DOING, Task.Status.CANCELED, Task.Status.DOING):
            response = self.status_post(self.executor, self.assignment, status)
            self.assertEqual(response.status_code, 302)
            self.assignment.refresh_from_db()
            self.assertEqual(self.assignment.status, status)

    def test_owner_can_manage_progress_but_cannot_force_completion(self):
        response = self.status_post(self.owner, self.assignment, Task.Status.PAUSED)
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.PAUSED)

        response = self.status_post(self.owner, self.assignment, Task.Status.DONE)
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.PAUSED)

    def test_invalid_status_and_invalid_transition_do_not_change_data(self):
        self.status_post(self.executor, self.assignment, 'HACKED')
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DOING)

        self.complete_post(self.executor, self.assignment)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)
        self.status_post(self.executor, self.assignment, Task.Status.DOING)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)


class CompletionAndEvaluationTests(TaskFlowBase):
    def test_only_assigned_executor_can_complete(self):
        self.assertEqual(self.complete_post(self.outsider, self.assignment).status_code, 403)
        self.assertEqual(self.complete_post(self.owner, self.assignment).status_code, 403)
        self.assertEqual(self.complete_post(self.stakeholder, self.stakeholder_role).status_code, 403)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DOING)
        self.assertFalse(self.assignment.rate.exists())

    def test_invalid_assessment_never_marks_done(self):
        invalid_payloads = [
            {'environmentRadio': ''},
            {'cognitionRadio': 'abc'},
            {'behaviorRadio': '0'},
            {'effectiveness': '6'},
        ]
        for payload in invalid_payloads:
            self.complete_post(self.executor, self.assignment, **payload)
            self.assignment.refresh_from_db()
            self.assertEqual(self.assignment.status, Task.Status.DOING)
            self.assertFalse(self.assignment.rate.exists())

    def test_valid_completion_is_atomic_and_unique(self):
        response = self.complete_post(self.executor, self.assignment)
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)
        rating = self.assignment.rate.get(rate_type=TaskRate.RateType.SELF)
        self.assertEqual(rating.user, self.executor)
        self.assertEqual((rating.environment, rating.cognition, rating.behavior, rating.effectiveness), (4, 4, 4, 4))

        self.complete_post(self.executor, self.assignment, effectiveness='5')
        self.assertEqual(
            self.assignment.rate.filter(rate_type=TaskRate.RateType.SELF).count(), 1,
        )
        rating.refresh_from_db()
        self.assertEqual(rating.effectiveness, 4)

    def test_stakeholder_evaluation_permissions_and_range(self):
        self.assertEqual(self.evaluate_post(self.stakeholder, self.assignment).status_code, 302)
        self.assertFalse(TaskRate.objects.filter(
            taskuser=self.assignment, rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())

        self.complete_post(self.executor, self.assignment)
        self.assertEqual(self.evaluate_post(self.outsider, self.assignment).status_code, 403)
        self.evaluate_post(self.stakeholder, self.assignment, 'abc')
        self.evaluate_post(self.stakeholder, self.assignment, '6')
        self.assertFalse(TaskRate.objects.filter(
            taskuser=self.assignment, user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())

        self.evaluate_post(self.stakeholder, self.assignment, '5')
        self.evaluate_post(self.stakeholder, self.assignment, '3')
        ratings = TaskRate.objects.filter(
            taskuser=self.assignment, user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        )
        self.assertEqual(ratings.count(), 1)
        self.assertEqual(ratings.get().effectiveness, 3)

    def test_executor_cannot_evaluate_or_review_their_own_assignment_even_if_owner(self):
        own_assignment = TaskUser.objects.create(
            task=self.task,
            user=self.owner,
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        self.complete_post(self.owner, own_assignment)
        own_assignment.refresh_from_db()
        self.assertEqual(own_assignment.status, Task.Status.DONE)

        self.assertEqual(self.evaluate_post(self.owner, own_assignment).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('upgrades_review_assignment', args=[own_assignment.pk]),
            {'status': TaskReview.Status.APPROVED, 'comment': 'Self approval attempt.'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(own_assignment.upgrade_reviews.exists())

    def test_admin_evaluated_flag_is_scoped_to_current_admin_not_executor_self_rating(self):
        self.complete_post(self.executor, self.assignment)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('stakeholder_tasks'))
        self.assertEqual(response.status_code, 200)
        page = response.context['stakeholder_tasks_all']
        row = next(item for item in page.object_list if item.pk == self.assignment.pk)
        self.assertFalse(row.evaluated_by_me)

        self.evaluate_post(self.admin, self.assignment, '4')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('stakeholder_tasks'))
        row = next(item for item in response.context['stakeholder_tasks_all'].object_list if item.pk == self.assignment.pk)
        self.assertTrue(row.evaluated_by_me)

    def test_owner_review_queue_includes_owned_tasks_but_never_self_assignment(self):
        self.complete_post(self.executor, self.assignment)
        own_assignment = TaskUser.objects.create(
            task=self.task,
            user=self.owner,
            type=Task.UserType.EXECUTOR,
            status=Task.Status.DOING,
        )
        self.complete_post(self.owner, own_assignment)

        self.client.force_login(self.owner)
        response = self.client.get(reverse('stakeholder_tasks'))
        self.assertEqual(response.status_code, 200)
        rows = {row.pk: row for row in response.context['stakeholder_tasks_all'].object_list}
        self.assertTrue(rows[self.assignment.pk].is_pending_evaluation)
        self.assertFalse(rows[own_assignment.pk].is_pending_evaluation)

    def test_clear_evaluation_is_post_only_and_user_scoped(self):
        self.complete_post(self.executor, self.assignment)
        self.evaluate_post(self.stakeholder, self.assignment)
        clear_url = reverse('stakeholder_clear_evaluate', args=[self.assignment.pk])
        self.client.force_login(self.stakeholder)
        self.assertEqual(self.client.get(clear_url).status_code, 405)

        self.client.force_login(self.stakeholder2)
        self.client.post(clear_url)
        self.assertTrue(TaskRate.objects.filter(
            taskuser=self.assignment, user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())

        self.client.force_login(self.stakeholder)
        self.client.post(clear_url)
        self.assertFalse(TaskRate.objects.filter(
            taskuser=self.assignment, user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())


class FinalApprovalInterfaceTests(TaskFlowBase):
    def test_approved_assignment_has_no_review_or_evaluation_control(self):
        self.complete_post(self.executor, self.assignment)
        self.complete_post(self.executor2, self.assignment2)
        self.evaluate_post(self.stakeholder, self.assignment, '5')
        self.client.post(reverse('upgrades_review_assignment', args=[self.assignment.pk]), {
            'status': TaskReview.Status.APPROVED,
        })
        response = self.client.get(reverse('upgrades_task_collaboration', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('upgrades_review_assignment', args=[self.assignment.pk]))
        self.assertContains(response, reverse('upgrades_review_assignment', args=[self.assignment2.pk]))
        response = self.client.get(reverse('stakeholder_tasks'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'data-taskid="{self.assignment.pk}"')
        self.assertContains(response, f'data-taskid="{self.assignment2.pk}"')
        rows = {row.pk: row for row in response.context['stakeholder_tasks_all']}
        self.assertTrue(rows[self.assignment.pk].is_final_approved)
        self.assertFalse(rows[self.assignment.pk].is_pending_evaluation)

    def test_history_preserves_both_cycles_and_uses_last_assessment_time(self):
        self.complete_post(self.executor, self.assignment, effectiveness='2')
        first = self.assignment.rate.get(rate_type=TaskRate.RateType.SELF)
        first_time = timezone.now() - timedelta(days=1)
        TaskRate.objects.filter(pk=first.pk).update(created_at=first_time, updated_at=first_time)
        self.evaluate_post(self.stakeholder, self.assignment, '3')
        self.client.post(reverse('upgrades_review_assignment', args=[self.assignment.pk]), {
            'status': TaskReview.Status.RETURNED, 'comment': 'First cycle',
        })
        self.complete_post(self.executor, self.assignment, effectiveness='5')
        first.refresh_from_db()
        self.assertGreater(first.updated_at, first_time)
        self.assertEqual(first.created_at, first_time)
        self.evaluate_post(self.stakeholder, self.assignment, '4')
        self.client.post(reverse('upgrades_review_assignment', args=[self.assignment.pk]), {
            'status': TaskReview.Status.APPROVED, 'comment': 'Second cycle',
        })
        response = self.client.get(reverse('task_history', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        assignment = next(row for row in response.context['assignments'] if row.pk == self.assignment.pk)
        reviews = assignment.review_history
        self.assertEqual([r['review'].cycle_number for r in reviews], [2, 1])
        self.assertEqual([r['self_assessment']['effectiveness'] for r in reviews], [5, 2])
        self.assertEqual([r['stakeholder_assessments'][0]['effectiveness'] for r in reviews], [4, 3])
        self.assertEqual(reviews[1]['self_assessment']['rated_at'], first_time)
        self.assertContains(response, 'First cycle')
        self.assertContains(response, 'Second cycle')
        self.assertNotContains(response, f'data-taskid="{self.assignment.pk}"')


class FullWorkflowScenarioTests(TaskFlowBase):
    def test_create_execute_return_reexecute_evaluate_and_approve(self):
        # Preventive checklist by the assigned executor.
        self.client.force_login(self.executor)
        prefix = f'checklist-{self.assignment.pk}'
        checklist_response = self.client.post(
            reverse('upgrades_add_checklist', args=[self.assignment.pk]),
            {
                f'{prefix}-environment_ok': 'on',
                f'{prefix}-lighting_ok': 'on',
                f'{prefix}-noise_ok': 'on',
                f'{prefix}-fatigue_low': 'on',
                f'{prefix}-clarity_ok': 'on',
                f'{prefix}-acceptance_criteria_ok': 'on',
            },
        )
        self.assertEqual(checklist_response.status_code, 302)
        self.assertTrue(TaskStartChecklist.objects.filter(
            taskuser=self.assignment, answered_by=self.executor,
        ).exists())

        # Normal progress and first completion.
        self.status_post(self.executor, self.assignment, Task.Status.PAUSED)
        self.status_post(self.executor, self.assignment, Task.Status.DOING)
        self.complete_post(self.executor, self.assignment, effectiveness='4')
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)

        # Stakeholder evaluates, then returns for adjustments.
        self.evaluate_post(self.stakeholder, self.assignment, '4')
        self.client.force_login(self.stakeholder)
        returned = self.client.post(
            reverse('upgrades_review_assignment', args=[self.assignment.pk]),
            {'status': TaskReview.Status.RETURNED, 'comment': 'Please adjust.'},
        )
        self.assertEqual(returned.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DOING)
        self.assertFalse(self.assignment.rate.filter(
            rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())
        returned_review = self.assignment.upgrade_reviews.first()
        self.assertEqual(returned_review.status, TaskReview.Status.RETURNED)
        self.assertEqual(returned_review.cycle_number, 1)
        self.assertEqual(returned_review.evaluation_snapshot['task']['name'], self.task.name)
        self.assertEqual(returned_review.evaluation_snapshot['assignment']['id'], self.assignment.pk)
        self.assertEqual(returned_review.evaluation_snapshot['self_assessment']['effectiveness'], 4)
        self.assertEqual(len(returned_review.evaluation_snapshot['stakeholder_assessments']), 1)

        # New cycle requires a fresh completion and stakeholder evaluation.
        self.complete_post(self.executor, self.assignment, effectiveness='5')
        self.evaluate_post(self.stakeholder, self.assignment, '5')
        self.client.force_login(self.stakeholder)
        approved = self.client.post(
            reverse('upgrades_review_assignment', args=[self.assignment.pk]),
            {'status': TaskReview.Status.APPROVED, 'comment': 'Approved.'},
        )
        self.assertEqual(approved.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)
        approved_review = self.assignment.upgrade_reviews.first()
        self.assertEqual(approved_review.status, TaskReview.Status.APPROVED)
        self.assertEqual(approved_review.cycle_number, 2)
        self.assertEqual(approved_review.evaluation_snapshot['self_assessment']['effectiveness'], 5)
        self.assertEqual(approved_review.evaluation_snapshot['stakeholder_assessments'][0]['effectiveness'], 5)

        # Approval is final: review history and live stakeholder ratings freeze.
        review_count = self.assignment.upgrade_reviews.count()
        self.client.post(
            reverse('upgrades_review_assignment', args=[self.assignment.pk]),
            {'status': TaskReview.Status.RETURNED, 'comment': 'Must not reopen.'},
        )
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Task.Status.DONE)
        self.assertEqual(self.assignment.upgrade_reviews.count(), review_count)

        self.evaluate_post(self.stakeholder, self.assignment, '1')
        stakeholder_rate = self.assignment.rate.get(
            user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        )
        self.assertEqual(stakeholder_rate.effectiveness, 5)
        self.client.force_login(self.stakeholder)
        self.client.post(reverse('stakeholder_clear_evaluate', args=[self.assignment.pk]))
        self.assertTrue(self.assignment.rate.filter(
            user=self.stakeholder,
            rate_type=TaskRate.RateType.STAKEHOLDER,
        ).exists())

        approved_review.comment = 'A forged rewrite'
        with self.assertRaises(ValidationError):
            approved_review.save()

        # History and collaboration remain accessible to authorized actors.
        self.assertEqual(self.client.get(reverse('task_history', args=[self.task.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('upgrades_task_collaboration', args=[self.task.pk])).status_code, 200)


class InvitationFlowTests(TaskFlowBase):
    def test_invitation_get_only_confirms_and_post_accepts_once(self):
        invitation = TaskInvitation.objects.create(
            email=self.outsider.email,
            task=self.task,
            type=Task.UserType.EXECUTOR,
            invited_by=self.owner,
        )
        self.client.force_login(self.outsider)
        url = reverse('tasks_accept_invitation', args=[invitation.pk])
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)
        self.assertFalse(TaskUser.objects.filter(
            task=self.task, user=self.outsider, type=Task.UserType.EXECUTOR,
        ).exists())

        post_response = self.client.post(url)
        self.assertEqual(post_response.status_code, 302)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(TaskUser.objects.filter(
            task=self.task, user=self.outsider, type=Task.UserType.EXECUTOR,
        ).count(), 1)

    def test_public_join_page_does_not_disclose_request_status_by_email(self):
        from .models import TaskJoinRequest, TaskShareLink

        share = TaskShareLink.objects.create(task=self.task, created_by=self.owner)
        join = TaskJoinRequest.objects.create(
            share_link=share,
            email='private-status@example.com',
            status=TaskJoinRequest.Status.APPROVED,
        )
        response = self.client.get(
            reverse('task_public_view', args=[share.pk]),
            {'email': join.email},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['request_status'])
        self.assertFalse(response.context['already_requested'])
        self.assertFalse(response.context['show_participant_names'])
        self.assertEqual(response.context['executors'], [])
        self.assertEqual(response.context['executor_count'], 2)



class DatabaseIntegrityTests(TaskFlowBase):
    def test_duplicate_assignment_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TaskUser.objects.create(
                    task=self.task,
                    user=self.executor,
                    type=Task.UserType.EXECUTOR,
                )

    def test_invalid_evaluation_range_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TaskRate.objects.create(
                    taskuser=self.assignment,
                    user=self.executor,
                    rate_type=TaskRate.RateType.SELF,
                    environment=4,
                    cognition=4,
                    behavior=4,
                    effectiveness=9,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Task.objects.create(
                    name='Invalid difficulty',
                    description='Must be rejected by database constraint',
                    difficulty=9,
                    user=self.owner,
                )

    def test_stakeholder_assignment_status_is_normalized(self):
        assignment = TaskUser.objects.create(
            task=self.task,
            user=self.outsider,
            type=Task.UserType.STAKEHOLDER,
            status=Task.Status.DOING,
        )
        self.assertEqual(assignment.status, Task.Status.NONE)
