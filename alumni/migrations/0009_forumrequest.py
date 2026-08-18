from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("alumni", "0008_add_school_forum_message"),
    ]

    operations = [
        migrations.CreateModel(
            name="ForumRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("request_type", models.CharField(choices=[("SCHOOL", "School Alumni"), ("ORGANIZATION", "Organization / Association")], default="SCHOOL", max_length=20)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("UNDER_REVIEW", "Under Review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("remarks", models.TextField(blank=True)),
                ("school_name", models.CharField(blank=True, max_length=255)),
                ("organization_name", models.CharField(blank=True, max_length=255)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("lga", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, default="Nigeria", max_length=100)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("website", models.URLField(blank=True)),
                ("year_established", models.PositiveIntegerField(blank=True, null=True)),
                ("school_type", models.CharField(blank=True, max_length=40)),
                ("organization_type", models.CharField(blank=True, max_length=40)),
                ("contact_person", models.CharField(blank=True, max_length=255)),
                ("contact_position", models.CharField(blank=True, max_length=255)),
                ("contact_phone", models.CharField(blank=True, max_length=20)),
                ("contact_email", models.EmailField(blank=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_forum_requests",
                        to="accounts.user",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forum_requests",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
