"""Static contract validator for ERGO's guarded task workflow.

This complements Django's runtime tests. It fails when critical authorization,
POST-only, transition, finalization, audit, constraint, test, admin or
documentation contracts disappear during a future refactor.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def functions(path: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(source(path), filename=path)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def decorator_names(node) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def function_text(path: str, node) -> str:
    lines = source(path).splitlines()
    return '\n'.join(lines[node.lineno - 1:node.end_lineno])


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate_views(errors: list[str]) -> None:
    path = 'tasks/views.py'
    funcs = functions(path)
    post_only = {
        'task_delete', 'add_user_role', 'role_delete', 'change', 'done',
        'stakeholder_evaluate', 'stakeholder_clear_evaluate',
        'send_task_reminder', 'task_share_link',
    }
    atomic = {
        'new', 'edit', 'task_delete', 'role_new', 'role_delete', 'change',
        'done', 'stakeholder_evaluate', 'stakeholder_clear_evaluate',
        'accept_invitation', 'task_share_link', 'task_join_requests',
    }
    for name in post_only:
        require(errors, name in funcs, f'Missing workflow view: {name}')
        if name in funcs:
            require(errors, 'require_POST' in decorator_names(funcs[name]), f'{name} must be POST-only')
    for name in atomic:
        require(errors, name in funcs, f'Missing transactional view: {name}')
        if name in funcs:
            require(errors, 'atomic' in decorator_names(funcs[name]), f'{name} must be transactional')

    for name in ('edit', 'roles', 'role_new', 'role_delete'):
        text = function_text(path, funcs[name])
        require(errors, 'can_manage_task' in text, f'{name} must enforce can_manage_task')
    delete = function_text(path, funcs['task_delete'])
    require(errors, 'task_has_workflow_history' in delete, 'Task deletion must preserve workflow history')
    require(errors, delete.count('select_for_update') >= 2, 'Task deletion must lock the task and its assignments')

    change = function_text(path, funcs['change'])
    done = function_text(path, funcs['done'])
    evaluation = function_text(path, funcs['stakeholder_evaluate'])
    clear = function_text(path, funcs['stakeholder_clear_evaluate'])
    public = function_text(path, funcs['task_public_view'])
    require(errors, 'AssignmentStatusForm' in change and 'change_assignment_status' in change, 'Status endpoint must use validated form and shared service')
    require(errors, 'SelfAssessmentForm' in done and 'complete_assignment' in done, 'Completion endpoint must validate and use shared service')
    require(errors, 'StakeholderEvaluationForm' in evaluation and 'evaluate_assignment' in evaluation, 'Evaluation endpoint must validate and use shared service')
    require(errors, "'final_approved'" in evaluation and "'final_approved'" in clear, 'Final approval must be handled by evaluation endpoints')
    require(errors, '.status = Task.Status.DONE' not in done, 'Completion view must not write DONE directly')
    require(errors, "request.GET.get('email'" not in public, 'Public join page must not disclose request state by e-mail query')
    require(errors, 'PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES' in public, 'Public task links must default to identity-safe participant display')

    invitation = function_text(path, funcs['accept_invitation'])
    require(errors, "request.method == 'GET'" in invitation, 'Invitation acceptance must have GET confirmation')
    require(errors, 'get_or_create' in invitation and 'invitation.accepted = True' in invitation, 'Invitation POST must be idempotent')


def validate_services_and_permissions(errors: list[str]) -> None:
    services = source('tasks/services.py')
    permissions = source('tasks/permissions.py')
    required_transitions = [
        "Task.Status.DOING: {Task.Status.DOING, Task.Status.PAUSED, Task.Status.CANCELED}",
        "Task.Status.PAUSED: {Task.Status.PAUSED, Task.Status.DOING, Task.Status.CANCELED}",
        "Task.Status.CANCELED: {Task.Status.CANCELED, Task.Status.DOING}",
        "Task.Status.DONE: {Task.Status.DONE}",
    ]
    for transition in required_transitions:
        require(errors, transition in services, f'Missing transition contract: {transition}')
    require(errors, 'new_status not in NON_FINAL_STATUS_VALUES' in services, 'Generic status service must reject DONE')
    require(errors, 'TaskRate.objects.update_or_create' in services, 'Assessments must be idempotent')
    require(errors, 'assignment.status = Task.Status.DONE' in services, 'Completion service must own DONE transition')
    require(errors, 'missing_self_assessment' in services, 'Stakeholder evaluation must require self-assessment')
    require(errors, 'is_assignment_final(assignment)' in services and 'final_approved' in services, 'Approved assignments must freeze evaluations')
    require(errors, 'assignment.user_id == getattr(user, "id", None)' in permissions, 'Review policy must prevent self-review')
    require(errors, 'getattr(user, "is_superuser", False)' in permissions, 'Django superusers must be recognized as privileged')


def validate_models_and_migrations(errors: list[str]) -> None:
    models_text = source('tasks/models.py')
    migration18 = source('tasks/migrations/0018_task_workflow_integrity.py')
    migration19 = source('tasks/migrations/0019_taskrate_updated_at.py')
    migration20 = source('tasks/migrations/0020_task_difficulty_constraint.py')
    constraints = [
        'uq_task_assignment_task_user_type',
        'ck_task_assignment_type_valid',
        'ck_task_assignment_type_status_consistent',
        'uq_task_evaluation_assignment_user_type',
        'ck_task_evaluation_effectiveness_1_5',
        'ck_task_evaluation_environment_1_5',
        'ck_task_evaluation_cognition_1_5',
        'ck_task_evaluation_behavior_1_5',
        'ck_task_evaluation_rate_type_valid',
        'ck_task_evaluation_payload_by_type',
    ]
    for name in constraints:
        require(errors, name in models_text, f'Model constraint missing: {name}')
        require(errors, name in migration18, f'Migration constraint missing: {name}')
    require(errors, "user = models.ForeignKey(CustomUser, related_name='rate'" in models_text, 'Evaluation actor must be non-null')
    require(errors, 'updated_at = models.DateTimeField(auto_now=True)' in models_text, 'Evaluation updates must be timestamped')
    require(errors, 'populate_updated_at' in migration19 and "F('created_at')" in migration19, 'Legacy evaluation timestamps must be populated')
    require(errors, "status='DONE'" in migration18 and "update(status='DOING')" in migration18, 'Migration must repair legacy DONE rows without self-assessment')
    require(errors, 'duplicate_groups' in migration18, 'Migration must deduplicate legacy assignments')
    require(errors, 'ck_task_difficulty_0_5' in models_text, 'Task difficulty database constraint is missing')
    require(errors, 'ck_task_difficulty_0_5' in migration20, 'Task difficulty constraint migration is missing')


def validate_upgrade_review(errors: list[str]) -> None:
    path = 'upgrades/views.py'
    funcs = functions(path)
    for name in ('kanban_update', 'review_assignment', 'add_checklist', 'toggle_operational_checklist'):
        require(errors, 'require_POST' in decorator_names(funcs[name]), f'Upgrade mutation {name} must be POST-only')
    require(errors, 'atomic' in decorator_names(funcs['add_checklist']), 'Checklist state check/write must be transactional')
    require(errors, 'atomic' in decorator_names(funcs['add_comment']), 'Comment creation must be transactional')
    review = function_text(path, funcs['review_assignment'])
    checklist = function_text(path, funcs['add_checklist'])
    require(errors, 'select_for_update' in review, 'Review must lock the assignment row')
    require(errors, 'rate_type=TaskRate.RateType.SELF' in review, 'Review must require executor self-assessment')
    require(errors, 'latest_review.status == TaskReview.Status.APPROVED' in review, 'Approval must be final')
    require(errors, 'assignment.status = Task.Status.DOING' in review, 'Return-for-adjustment must reopen execution')
    require(errors, 'evaluation_snapshot=_review_evaluation_snapshot' in review, 'Reviews must snapshot evaluations')
    snapshot_helper = function_text(path, funcs['_review_evaluation_snapshot'])
    require(errors, "'task': {" in snapshot_helper and "'assignment': {" in snapshot_helper, 'Review snapshots must preserve task and assignment context')
    require(errors, 'cycle_number=cycle_number' in review, 'Reviews must identify execution cycle')
    require(errors, 'select_for_update' in checklist, 'Checklist must lock current assignment state')
    comment = function_text(path, funcs['add_comment'])
    require(errors, 'select_for_update' in comment, 'Comment creation must serialize with guarded task deletion')

    models_text = source('upgrades/models.py')
    migration = source('upgrades/migrations/0003_task_review_audit_snapshot.py')
    difficulty_migration = source('upgrades/migrations/0004_task_template_difficulty_constraint.py')
    for name in ('cycle_number', 'evaluation_snapshot', 'ck_task_review_status_valid', 'ck_task_review_cycle_positive'):
        require(errors, name in models_text, f'Review model contract missing: {name}')
        require(errors, name in migration, f'Review migration contract missing: {name}')
    require(errors, 'populate_review_cycles' in migration, 'Legacy review cycles must be populated')
    require(errors, 'Task reviews are immutable audit records.' in models_text, 'Review records must reject in-place rewriting')
    require(errors, 'ck_task_template_difficulty_0_5' in models_text, 'Template difficulty database constraint is missing')
    require(errors, 'ck_task_template_difficulty_0_5' in difficulty_migration, 'Template difficulty constraint migration is missing')


def validate_admin_and_templates(errors: list[str]) -> None:
    task_admin = source('tasks/admin.py')
    upgrade_admin = source('upgrades/admin.py')
    require(errors, 'class ReadOnlyAuditAdmin' in task_admin and 'class TaskRateAdmin(ReadOnlyAuditAdmin)' in task_admin, 'Task evaluations must be read-only in Django admin')
    require(errors, 'class TaskReviewAdmin(ReadOnlyAuditAdmin)' in upgrade_admin, 'Task reviews must be read-only in Django admin')
    require(errors, task_admin.count('def has_delete_permission') >= 2, 'Task and assignment deletion must be blocked in Django admin')

    role_template = source('templates/tasks/roles.html')
    history = source('templates/tasks/task_history.html')
    invitation = source('templates/tasks/accept_invitation.html')
    public = source('templates/tasks/task_public.html')
    require(errors, 'method="post"' in role_template.lower() and 'csrf_token' in role_template, 'Role deletion UI must POST with CSRF')
    require(errors, 'send_task_reminder' in history and 'method="post"' in history.lower(), 'Reminder UI must POST')
    require(errors, 'method="post"' in invitation.lower() and 'csrf_token' in invitation, 'Invitation confirmation must POST with CSRF')
    require(errors, 'show_participant_names' in public and 'Participant names are hidden on public links.' in public, 'Public task template must support identity-safe display')
    for template in (ROOT / 'templates').rglob('*.html'):
        text = template.read_text(encoding='utf-8', errors='ignore')
        if 'stakeholder_clear_evaluate' in text:
            require(errors, 'method="post"' in text.lower() or "form.method = 'POST'" in text, f'{template}: evaluation deletion must POST')


def validate_tests_and_docs(errors: list[str]) -> tuple[int, int]:
    task_tests = source('tasks/tests.py')
    upgrade_tests = source('upgrades/tests.py')
    task_count = len(re.findall(r'^\s+def test_', task_tests, flags=re.MULTILINE))
    upgrade_count = len(re.findall(r'^\s+def test_', upgrade_tests, flags=re.MULTILINE))
    require(errors, task_count >= 26, f'Expected at least 26 task-flow tests, found {task_count}')
    require(errors, upgrade_count >= 17, f'Expected at least 17 upgrade tests, found {upgrade_count}')
    for phrase in (
        'test_owner_creates_task_with_normalized_assignments',
        'test_invalid_assessment_never_marks_done',
        'test_stakeholder_evaluation_permissions_and_range',
        'test_create_execute_return_reexecute_evaluate_and_approve',
        'test_duplicate_assignment_is_rejected_by_database',
        'test_django_superuser_is_privileged_without_manual_role_promotion',
        'test_owner_review_queue_includes_owned_tasks_but_never_self_assignment',
        'test_public_join_page_does_not_disclose_request_status_by_email',
    ):
        require(errors, phrase in task_tests, f'Missing regression test: {phrase}')
    require(errors, 'test_pre_task_checklist_is_rejected_after_completion' in upgrade_tests, 'Missing final-state checklist regression test')
    for path in (
        'docs/FLUXO_DE_TAREFAS_VALIDADO.md',
        'docs/ROTAS_E_PERMISSOES.md',
        'docs/TESTES_E_VALIDACAO.md',
        'docs/RELATORIO_VALIDACAO_V5.md',
        'ALTERACOES_V5.md',
        'CORRECOES_REALIZADAS.md',
        'CHANGELOG.md',
    ):
        require(errors, (ROOT / path).exists(), f'Missing workflow documentation: {path}')
    return task_count, upgrade_count


def main() -> int:
    errors: list[str] = []
    validate_views(errors)
    validate_services_and_permissions(errors)
    validate_models_and_migrations(errors)
    validate_upgrade_review(errors)
    validate_admin_and_templates(errors)
    task_count, upgrade_count = validate_tests_and_docs(errors)
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print(
        'Task workflow static contract passed '
        f'({task_count} task tests + {upgrade_count} upgrade tests present).'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
