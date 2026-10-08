from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0006_task_lifecycle_and_difficulty'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyplan',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Envoyée le'),
        ),
    ]
