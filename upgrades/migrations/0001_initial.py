# Generated manually for the ERGO upgrades module.
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0016_alter_task_table_alter_taskinvitation_table_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorReading',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.CharField(blank=True, default='manual', max_length=120)),
                ('temperature_c', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('humidity_percent', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('noise_db', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('luminosity_lux', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('air_quality_index', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('note', models.CharField(blank=True, default='', max_length=250)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sensor_readings', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'sensor_reading', 'ordering': ['-captured_at']},
        ),
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250)),
                ('description', models.CharField(blank=True, default='', max_length=250)),
                ('dias', models.PositiveSmallIntegerField(default=0)),
                ('horas', models.PositiveSmallIntegerField(default=0)),
                ('difficulty', models.PositiveSmallIntegerField(default=0)),
                ('checklist', models.TextField(blank=True, default='', help_text='One checklist item per line. These items are shown before starting the task.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'task_template', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=2000)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='task_attachments/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='upgrade_comments', to='tasks.task')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_comments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'task_comment', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='TaskReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDING', 'Pending review'), ('APPROVED', 'Approved'), ('RETURNED', 'Returned for adjustments')], default='PENDING', max_length=15)),
                ('comment', models.TextField(blank=True, default='', max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_reviews', to=settings.AUTH_USER_MODEL)),
                ('taskuser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='upgrade_reviews', to='tasks.taskuser')),
            ],
            options={'db_table': 'task_review', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='TaskStartChecklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('environment_ok', models.BooleanField(default=True)),
                ('lighting_ok', models.BooleanField(default=True)),
                ('noise_ok', models.BooleanField(default=True)),
                ('fatigue_low', models.BooleanField(default=True)),
                ('clarity_ok', models.BooleanField(default=True)),
                ('acceptance_criteria_ok', models.BooleanField(default=True)),
                ('risk_score', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(6)])),
                ('recommendations', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('answered_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='start_checklists', to=settings.AUTH_USER_MODEL)),
                ('taskuser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='start_checklists', to='tasks.taskuser')),
            ],
            options={'db_table': 'task_start_checklist', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='RecurringTaskRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.CharField(choices=[('DAILY', 'Daily'), ('WEEKLY', 'Weekly'), ('MONTHLY', 'Monthly')], default='WEEKLY', max_length=10)),
                ('next_run', models.DateField(default=django.utils.timezone.localdate)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_task_rules', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_rules', to='upgrades.tasktemplate')),
            ],
            options={'db_table': 'recurring_task_rule', 'ordering': ['next_run']},
        ),
    ]
