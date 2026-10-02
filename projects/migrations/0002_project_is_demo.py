from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_demo',
            field=models.BooleanField(
                default=False,
                help_text="Projet créé par le générateur. Il ne représente pas un projet réel.",
                verbose_name='Donnée de démonstration',
            ),
        ),
    ]
