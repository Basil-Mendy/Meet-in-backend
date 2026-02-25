from django.db import migrations, models
import uuid
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('forums', '0015_merge_20260222_2333'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename email_sent_at -> added_at on AnnouncementRecipient
        migrations.RenameField(
            model_name='announcementrecipient',
            old_name='email_sent_at',
            new_name='added_at',
        ),

        # Remove email-specific fields
        migrations.RemoveField(
            model_name='announcementrecipient',
            name='email_delivery_status',
        ),
        migrations.RemoveField(
            model_name='announcementrecipient',
            name='email_error',
        ),

        # Remove email-only flag from Announcement
        migrations.RemoveField(
            model_name='announcement',
            name='save_to_forum_feed',
        ),

        # Create AnnouncementAttachment model
        migrations.CreateModel(
            name='AnnouncementAttachment',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('file', models.FileField(upload_to='announcement_attachments/')),
                ('filename', models.CharField(max_length=255)),
                ('size', models.BigIntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_announcement_attachments', to=settings.AUTH_USER_MODEL)),
                ('announcement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='forums.announcement')),
            ],
        ),
    ]
