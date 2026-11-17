from django.db import migrations, models
import django.db.models.deletion


def normalize_and_deduplicate(apps, schema_editor):
    TaskUser = apps.get_model('tasks', 'TaskUser')
    TaskRate = apps.get_model('tasks', 'TaskRate')
    connection = schema_editor.connection

    # Normalize invalid legacy values before DB constraints are added.
    TaskUser.objects.exclude(type__in=['EXECUTOR', 'STAKEHOLDER']).delete()
    TaskUser.objects.filter(type='STAKEHOLDER').update(status='NONE')
    TaskUser.objects.filter(type='EXECUTOR', status='NONE').update(status='DOING')
    TaskUser.objects.filter(type='EXECUTOR').exclude(status__in=['DOING', 'PAUSED', 'CANCELED', 'DONE']).update(status='DOING')

    TaskRate.objects.filter(effectiveness__lt=1).update(effectiveness=1)
    TaskRate.objects.filter(effectiveness__gt=5).update(effectiveness=5)
    for field in ('environment', 'cognition', 'behavior'):
        TaskRate.objects.filter(**{f'{field}__lt': 1}).update(**{field: None})
        TaskRate.objects.filter(**{f'{field}__gt': 5}).update(**{field: None})
    TaskRate.objects.exclude(rate_type__in=['SELF', 'STAKEHOLDER']).update(rate_type='SELF')
    for rating in TaskRate.objects.select_related('taskuser__task').filter(user_id__isnull=True).iterator():
        rating.user_id = (
            rating.taskuser.user_id
            if rating.rate_type == 'SELF'
            else rating.taskuser.task.user_id
        )
        rating.save(update_fields=['user'])
    # Normalize payload shape by evaluation type.
    for rating in TaskRate.objects.filter(rate_type='SELF').iterator():
        fallback = min(5, max(1, rating.effectiveness or 1))
        updates = {}
        for field in ('environment', 'cognition', 'behavior'):
            if getattr(rating, field) is None:
                updates[field] = fallback
        if updates:
            TaskRate.objects.filter(pk=rating.pk).update(**updates)
    TaskRate.objects.filter(rate_type='STAKEHOLDER').update(
        environment=None,
        cognition=None,
        behavior=None,
    )
    # Legacy DONE rows without an executor self-assessment are not valid final
    # states. Return them to DOING so they can be completed through the guarded
    # workflow and receive a valid assessment.
    for assignment in TaskUser.objects.filter(type='EXECUTOR', status='DONE').iterator():
        if not TaskRate.objects.filter(
            taskuser_id=assignment.id,
            user_id=assignment.user_id,
            rate_type='SELF',
        ).exists():
            TaskUser.objects.filter(pk=assignment.pk).update(status='DOING')

    duplicate_groups = (
        TaskUser.objects.values('task_id', 'user_id', 'type')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
    )
    table_names = set(connection.introspection.table_names())
    quote = connection.ops.quote_name

    for group in duplicate_groups.iterator():
        rows = list(
            TaskUser.objects.filter(
                task_id=group['task_id'],
                user_id=group['user_id'],
                type=group['type'],
            ).order_by('id')
        )
        keeper = rows[0]
        for duplicate in rows[1:]:
            # Preserve evaluations, favoring the most recent duplicate value.
            for rating in TaskRate.objects.filter(taskuser_id=duplicate.id).order_by('id'):
                existing = TaskRate.objects.filter(
                    taskuser_id=keeper.id,
                    user_id=rating.user_id,
                    rate_type=rating.rate_type,
                ).first()
                if existing:
                    existing.environment = rating.environment
                    existing.cognition = rating.cognition
                    existing.behavior = rating.behavior
                    existing.effectiveness = rating.effectiveness
                    existing.save(update_fields=['environment', 'cognition', 'behavior', 'effectiveness'])
                    rating.delete()
                else:
                    rating.taskuser_id = keeper.id
                    rating.save(update_fields=['taskuser'])

            # Move optional upgrade history when those tables already exist.
            with connection.cursor() as cursor:
                for table in ('task_review', 'task_start_checklist'):
                    if table in table_names:
                        cursor.execute(
                            f'UPDATE {quote(table)} SET {quote("taskuser_id")} = %s WHERE {quote("taskuser_id")} = %s',
                            [keeper.id, duplicate.id],
                        )
            duplicate.delete()


class Migration(migrations.Migration):
    dependencies = [('tasks', '0017_task_difficulty_range')]

    operations = [
        migrations.RunPython(normalize_and_deduplicate, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='taskuser',
            constraint=models.UniqueConstraint(
                fields=('task', 'user', 'type'),
                name='uq_task_assignment_task_user_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskuser',
            constraint=models.CheckConstraint(
                condition=models.Q(type__in=['EXECUTOR', 'STAKEHOLDER']),
                name='ck_task_assignment_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskuser',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(type='STAKEHOLDER', status='NONE')
                    | models.Q(type='EXECUTOR', status__in=['DOING', 'PAUSED', 'CANCELED', 'DONE'])
                ),
                name='ck_task_assignment_type_status_consistent',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='taskrate',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='taskrate',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rate', to='accounts.customuser'),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.UniqueConstraint(
                fields=('taskuser', 'user', 'rate_type'),
                name='uq_task_evaluation_assignment_user_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
                condition=models.Q(effectiveness__gte=1, effectiveness__lte=5),
                name='ck_task_evaluation_effectiveness_1_5',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
                condition=models.Q(environment__isnull=True) | models.Q(environment__gte=1, environment__lte=5),
                name='ck_task_evaluation_environment_1_5',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
                condition=models.Q(cognition__isnull=True) | models.Q(cognition__gte=1, cognition__lte=5),
                name='ck_task_evaluation_cognition_1_5',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
                condition=models.Q(behavior__isnull=True) | models.Q(behavior__gte=1, behavior__lte=5),
                name='ck_task_evaluation_behavior_1_5',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
                condition=models.Q(rate_type__in=['SELF', 'STAKEHOLDER']),
                name='ck_task_evaluation_rate_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskrate',
            constraint=models.CheckConstraint(
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
        ),
    ]
