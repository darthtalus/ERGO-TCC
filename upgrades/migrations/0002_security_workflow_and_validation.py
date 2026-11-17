from pathlib import Path
import shutil

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion

import upgrades.storage
import upgrades.validators


def populate_recurring_anchor_day(apps, schema_editor):
    RecurringTaskRule = apps.get_model('upgrades', 'RecurringTaskRule')
    for rule in RecurringTaskRule.objects.filter(anchor_day__isnull=True).iterator():
        rule.anchor_day = rule.next_run.day
        rule.save(update_fields=['anchor_day'])


def move_legacy_attachments(apps, schema_editor):
    TaskComment = apps.get_model('upgrades', 'TaskComment')
    media_root = Path(settings.MEDIA_ROOT)
    private_root = Path(getattr(settings, 'PRIVATE_MEDIA_ROOT', Path(settings.BASE_DIR) / 'private_media'))
    for comment in TaskComment.objects.exclude(attachment='').exclude(attachment__isnull=True).iterator():
        relative_name = str(comment.attachment).replace('\\', '/').lstrip('/')
        source = media_root / relative_name
        destination = private_root / relative_name
        if source.exists() and not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))


def reverse_move_legacy_attachments(apps, schema_editor):
    # Files are intentionally left in private storage on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0017_task_difficulty_range'),
        ('upgrades', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='recurringtaskrule',
            name='anchor_day',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(31)],
            ),
        ),
        migrations.RunPython(populate_recurring_anchor_day, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='taskcomment',
            name='attachment',
            field=models.FileField(
                blank=True,
                null=True,
                storage=upgrades.storage.PrivateAttachmentStorage(),
                upload_to='task_attachments/',
                validators=[
                    upgrades.validators.validate_attachment_extension,
                    upgrades.validators.validate_attachment_size,
                ],
            ),
        ),
        migrations.RunPython(move_legacy_attachments, reverse_move_legacy_attachments),
        migrations.AlterField(
            model_name='tasktemplate',
            name='difficulty',
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[MinValueValidator(0), MaxValueValidator(5)],
            ),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='temperature_c',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                validators=[MinValueValidator(-50), MaxValueValidator(70)],
            ),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='humidity_percent',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
            ),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='noise_db',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(200)],
            ),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='luminosity_lux',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(200000)],
            ),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='air_quality_index',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(500)],
            ),
        ),
        migrations.CreateModel(
            name='TaskChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=500)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('is_completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('completed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='completed_task_checklist_items',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='operational_checklist_items',
                    to='tasks.task',
                )),
            ],
            options={
                'db_table': 'task_checklist_item',
                'ordering': ['position', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RecurringTaskOccurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_for', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('rule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='occurrences',
                    to='upgrades.recurringtaskrule',
                )),
                ('task', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurring_occurrence',
                    to='tasks.task',
                )),
            ],
            options={
                'db_table': 'recurring_task_occurrence',
                'ordering': ['scheduled_for'],
            },
        ),
        migrations.AddConstraint(
            model_name='recurringtaskoccurrence',
            constraint=models.UniqueConstraint(
                fields=('rule', 'scheduled_for'),
                name='uq_recurring_rule_scheduled_for',
            ),
        ),
        migrations.CreateModel(
            name='SensorApiToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.CharField(db_index=True, max_length=12)),
                ('key_hash', models.CharField(max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sensor_api_token',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sensor_api_token'},
        ),
    ]
