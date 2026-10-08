from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_dailyreport_uploaded_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyreport',
            name='original_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nom du fichier'),
        ),
        migrations.AddField(
            model_name='dailyreport',
            name='file_size',
            field=models.PositiveIntegerField(default=0, verbose_name='Taille'),
        ),
    ]
