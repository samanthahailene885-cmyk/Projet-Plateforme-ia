from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_project_is_demo'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='brief',
            field=models.FileField(blank=True, null=True, upload_to='project_briefs/%Y/%m/', verbose_name='Fichier du projet'),
        ),
        migrations.AddField(
            model_name='project',
            name='brief_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nom du fichier'),
        ),
    ]
