from django.db import migrations, models
from django.db.models import F


def populate_updated_at(apps, schema_editor):
    TaskRate = apps.get_model('tasks', 'TaskRate')
    TaskRate.objects.filter(updated_at__isnull=True).update(updated_at=F('created_at'))


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0018_task_workflow_integrity'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskrate',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(populate_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='taskrate',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
