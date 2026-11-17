from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0016_alter_task_table_alter_taskinvitation_table_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='difficulty',
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[MinValueValidator(0), MaxValueValidator(5)],
            ),
        ),
    ]
