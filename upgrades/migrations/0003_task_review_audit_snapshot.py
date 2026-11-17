from django.core.validators import MinValueValidator
from django.db import migrations, models


def populate_review_cycles(apps, schema_editor):
    """Best-effort cycle numbering for review rows created before v5.

    Historical evaluation values cannot be reconstructed reliably, so existing
    snapshots remain empty. Their review order and cycle are preserved.
    """
    TaskReview = apps.get_model('upgrades', 'TaskReview')
    taskuser_ids = (
        TaskReview.objects.order_by()
        .values_list('taskuser_id', flat=True)
        .distinct()
    )
    for taskuser_id in taskuser_ids.iterator():
        cycle = 1
        reviews = TaskReview.objects.filter(taskuser_id=taskuser_id).order_by('created_at', 'pk')
        for review in reviews.iterator():
            if review.cycle_number != cycle:
                TaskReview.objects.filter(pk=review.pk).update(cycle_number=cycle)
            if review.status == 'RETURNED':
                cycle += 1


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0019_taskrate_updated_at'),
        ('upgrades', '0002_security_workflow_and_validation'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='taskreview',
            options={'ordering': ['-created_at', '-pk']},
        ),
        migrations.AddField(
            model_name='taskreview',
            name='cycle_number',
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
            ),
        ),
        migrations.AddField(
            model_name='taskreview',
            name='evaluation_snapshot',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Immutable copy of the self and stakeholder evaluations at review time.',
            ),
        ),
        migrations.RunPython(populate_review_cycles, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='taskreview',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=['PENDING', 'APPROVED', 'RETURNED']),
                name='ck_task_review_status_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskreview',
            constraint=models.CheckConstraint(
                condition=models.Q(cycle_number__gte=1),
                name='ck_task_review_cycle_positive',
            ),
        ),
    ]
