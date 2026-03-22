from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_merge_20260322_0558'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
