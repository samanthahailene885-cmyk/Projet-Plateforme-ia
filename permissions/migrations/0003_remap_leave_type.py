from django.db import migrations


def remap_legacy_types(apps, schema_editor):
    PermissionRequest = apps.get_model('permissions', 'PermissionRequest')
    PermissionRequest.objects.filter(type='leave').update(type='annual')


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0002_permissionrequest_attachment_and_more'),
    ]

    operations = [
        migrations.RunPython(remap_legacy_types, migrations.RunPython.noop),
    ]
