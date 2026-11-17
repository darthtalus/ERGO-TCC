from django.db import migrations, models


def normalize_template_difficulty(apps, schema_editor):
    TaskTemplate = apps.get_model('upgrades', 'TaskTemplate')
    TaskTemplate.objects.filter(difficulty__gt=5).update(difficulty=5)
    TaskTemplate.objects.filter(difficulty__lt=0).update(difficulty=0)


class Migration(migrations.Migration):
    dependencies = [
        ('upgrades', '0003_task_review_audit_snapshot'),
    ]

    operations = [
        migrations.RunPython(normalize_template_difficulty, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='tasktemplate',
            constraint=models.CheckConstraint(
                condition=models.Q(difficulty__gte=0, difficulty__lte=5),
                name='ck_task_template_difficulty_0_5',
            ),
        ),
    ]
