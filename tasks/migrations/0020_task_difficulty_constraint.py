from django.db import migrations, models


def normalize_task_difficulty(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    Task.objects.filter(difficulty__gt=5).update(difficulty=5)
    Task.objects.filter(difficulty__lt=0).update(difficulty=0)


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0019_taskrate_updated_at'),
    ]

    operations = [
        migrations.RunPython(normalize_task_difficulty, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(
                condition=models.Q(difficulty__gte=0, difficulty__lte=5),
                name='ck_task_difficulty_0_5',
            ),
        ),
    ]
