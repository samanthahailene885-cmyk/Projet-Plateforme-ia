from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_user_address_user_bio_user_birth_date_user_gender'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_demo',
            field=models.BooleanField(
                default=False,
                help_text="Compte créé par le générateur. Il ne représente pas un employé réel.",
                verbose_name='Donnée de démonstration',
            ),
        ),
    ]
