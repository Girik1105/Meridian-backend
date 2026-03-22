from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_merge_20260322_0040'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='careerpath',
                    name='roi_data',
                    field=models.JSONField(default=dict),
                ),
            ],
            state_operations=[],
        ),
    ]
