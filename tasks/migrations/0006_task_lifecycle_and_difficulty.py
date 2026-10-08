import django.db.models.deletion
from django.db import migrations, models


def backfill_task_times(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    Task.objects.filter(status='completed', completed_at__isnull=True).update(
        completed_at=models.F('updated_at'),
    )
    Task.objects.filter(
        status__in=['in_progress', 'review', 'completed'],
        started_at__isnull=True,
    ).update(started_at=models.F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0001_initial'),
        ('projects', '0002_project_is_demo'),
        ('tasks', '0005_task_assignment_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Commencée le'),
        ),
        migrations.AddField(
            model_name='task',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Terminée le'),
        ),
        migrations.AddField(
            model_name='task',
            name='result_file',
            field=models.FileField(blank=True, upload_to='task_results/%Y/%m/', verbose_name='Fichier résultat'),
        ),
        migrations.AddField(
            model_name='task',
            name='result_original_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nom du fichier résultat'),
        ),
        migrations.AddField(
            model_name='task',
            name='result_file_size',
            field=models.PositiveIntegerField(default=0, verbose_name='Taille du résultat'),
        ),
        migrations.RunPython(backfill_task_times, migrations.RunPython.noop),
        migrations.CreateModel(
            name='Difficulty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(verbose_name='Description')),
                ('reported_on', models.DateField(verbose_name='Date')),
                ('status', models.CharField(choices=[('open', 'Ouverte'), ('resolved', 'Résolue')], default='open', max_length=20, verbose_name='Statut')),
                ('priority', models.CharField(choices=[('low', 'Faible'), ('medium', 'Moyenne'), ('high', 'Haute')], default='medium', max_length=20, verbose_name='Priorité')),
                ('is_demo', models.BooleanField(default=False, verbose_name='Donnée de démonstration')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Mise à jour le')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='difficulties', to='employees.employee', verbose_name='Employé')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='difficulties', to='projects.project', verbose_name='Projet')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='difficulties', to='tasks.task', verbose_name='Tâche')),
            ],
            options={
                'verbose_name': 'Difficulté',
                'verbose_name_plural': 'Difficultés',
                'ordering': ['-reported_on', '-created_at'],
            },
        ),
    ]
