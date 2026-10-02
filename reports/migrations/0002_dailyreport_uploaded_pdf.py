from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyreport',
            name='uploaded_pdf',
            field=models.FileField(
                blank=True,
                help_text="Rapport PDF envoyé par l'employé, sans génération par l'IA.",
                upload_to='reports/imported/%Y/%m/',
                verbose_name='PDF importé',
            ),
        ),
    ]
