from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alumni", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolmembership",
            name="role",
            field=models.CharField(choices=[("MEMBER", "Member"), ("CHAIRMAN", "Chairman"), ("SECRETARY", "Secretary")], default="MEMBER", max_length=20),
        ),
    ]
