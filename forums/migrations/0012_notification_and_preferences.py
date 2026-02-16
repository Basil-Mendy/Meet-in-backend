# Generated migration for Notification and UserNotificationPreference models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('forums', '0011_pollgroup'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('notification_type', models.CharField(choices=[('FEED_NEW_POST', 'New post in feed'), ('MEETING_CREATED', 'Meeting created'), ('MEETING_LIVE', 'Meeting is now live'), ('MEETING_ENDED', 'Meeting has ended'), ('PAYMENT_CREATED', 'Payment created'), ('DISBURSEMENT_CREATED', 'Disbursement made'), ('MEMBER_ADDED', 'New member added'), ('MEMBER_REMOVED', 'Member removed'), ('MEMBER_ROLE_ASSIGNED', 'Member role assigned'), ('MEMBER_ROLE_REMOVED', 'Member role removed'), ('MEMBER_APPROVED', 'Member approved'), ('FORUM_INFO_UPDATED', 'Forum info updated'), ('ANNOUNCEMENT_CREATED', 'Announcement made'), ('POLL_CREATED', 'Poll created'), ('POLL_ACTIVE', 'Poll is active'), ('POLL_CLOSED', 'Poll closed')], max_length=50)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('tab', models.CharField(choices=[('feed', 'Feed'), ('meetings', 'Meetings'), ('payments', 'Payments'), ('disbursements', 'Disbursements'), ('members', 'Members'), ('about', 'About'), ('announcements', 'Announcements'), ('polls', 'Polls'), ('settings', 'Settings')], help_text='Which tab should user be directed to', max_length=50)),
                ('object_id', models.CharField(blank=True, help_text='ID of related object (post, meeting, payment, etc)', max_length=50)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('forum', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='forums.forum')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserNotificationPreference',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('feed_in_app', models.BooleanField(default=True)),
                ('feed_push', models.BooleanField(default=True)),
                ('feed_email', models.BooleanField(default=False)),
                ('meetings_in_app', models.BooleanField(default=True)),
                ('meetings_push', models.BooleanField(default=True)),
                ('meetings_email', models.BooleanField(default=True)),
                ('payments_in_app', models.BooleanField(default=True)),
                ('payments_push', models.BooleanField(default=False)),
                ('payments_email', models.BooleanField(default=True)),
                ('disbursements_in_app', models.BooleanField(default=True)),
                ('disbursements_push', models.BooleanField(default=False)),
                ('disbursements_email', models.BooleanField(default=True)),
                ('members_in_app', models.BooleanField(default=True)),
                ('members_push', models.BooleanField(default=False)),
                ('members_email', models.BooleanField(default=False)),
                ('forum_info_in_app', models.BooleanField(default=True)),
                ('forum_info_push', models.BooleanField(default=False)),
                ('forum_info_email', models.BooleanField(default=False)),
                ('announcements_in_app', models.BooleanField(default=True)),
                ('announcements_push', models.BooleanField(default=True)),
                ('announcements_email', models.BooleanField(default=True)),
                ('polls_in_app', models.BooleanField(default=True)),
                ('polls_push', models.BooleanField(default=False)),
                ('polls_email', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'User notification preferences',
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'forum', '-created_at'], name='forums_notif_user_forum_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read'], name='forums_notif_user_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['forum', '-created_at'], name='forums_notif_forum_created_idx'),
        ),
    ]
