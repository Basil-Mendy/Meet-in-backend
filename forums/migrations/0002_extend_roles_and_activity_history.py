# Generated migration for ForumActivityHistory model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('forums', '0001_initial'),  # Adjust this to your latest migration
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Update ForumMembership ROLE_CHOICES
        migrations.AlterField(
            model_name='forummembership',
            name='role',
            field=models.CharField(
                choices=[
                    ('MOD', 'Moderator (Creator)'),
                    ('C', 'Chairman'),
                    ('VC', 'Vice Chairman'),
                    ('SEC', 'Secretary'),
                    ('ASEC', 'Assistant Secretary'),
                    ('FSEC', 'Financial Secretary'),
                    ('TR', 'Treasurer'),
                    ('PRO', 'Public Relation Officer'),
                    ('POI', 'Provost I'),
                    ('POII', 'Provost II'),
                    ('MEMBER', 'Member'),
                ],
                default='MEMBER',
                max_length=10,
            ),
        ),
        # Create ForumActivityHistory model
        migrations.CreateModel(
            name='ForumActivityHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('activity_type', models.CharField(
                    choices=[
                        ('post_created', 'Post Created'),
                        ('post_deleted', 'Post Deleted'),
                        ('post_edited', 'Post Edited'),
                        ('comment_created', 'Comment Created'),
                        ('comment_deleted', 'Comment Deleted'),
                        ('reaction_added', 'Reaction Added'),
                        ('meeting_created', 'Meeting Created'),
                        ('meeting_updated', 'Meeting Updated'),
                        ('meeting_deleted', 'Meeting Deleted'),
                        ('meeting_attended', 'Meeting Attended'),
                        ('payment_created', 'Payment Created'),
                        ('payment_submitted', 'Payment Submitted'),
                        ('disbursement_created', 'Disbursement Created'),
                        ('disbursement_processed', 'Disbursement Processed'),
                        ('member_joined', 'Member Joined'),
                        ('member_left', 'Member Left'),
                        ('member_role_changed', 'Member Role Changed'),
                        ('announcement_created', 'Announcement Created'),
                        ('announcement_deleted', 'Announcement Deleted'),
                        ('poll_created', 'Poll Created'),
                        ('poll_voted', 'Poll Voted'),
                        ('document_uploaded', 'Document Uploaded'),
                        ('document_deleted', 'Document Deleted'),
                        ('settings_changed', 'Settings Changed'),
                        ('other', 'Other'),
                    ],
                    max_length=50,
                )),
                ('tab', models.CharField(
                    choices=[
                        ('feed', 'Feed'),
                        ('meetings', 'Meetings'),
                        ('payments', 'Payments'),
                        ('disbursements', 'Disbursements'),
                        ('members', 'Members'),
                        ('about', 'About'),
                        ('announcements', 'Announcements'),
                        ('polls', 'Polls'),
                        ('settings', 'Settings'),
                    ],
                    max_length=50,
                )),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('object_id', models.CharField(blank=True, max_length=50)),
                ('object_type', models.CharField(blank=True, max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('forum', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_history', to='forums.forum')),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.SET_NULL, related_name='forum_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='forumactivityhistory',
            index=models.Index(fields=['forum', '-created_at'], name='forums_foru_forum_idx'),
        ),
        migrations.AddIndex(
            model_name='forumactivityhistory',
            index=models.Index(fields=['forum', 'tab', '-created_at'], name='forums_foru_forum_tab_idx'),
        ),
        migrations.AddIndex(
            model_name='forumactivityhistory',
            index=models.Index(fields=['forum', 'activity_type', '-created_at'], name='forums_foru_forum_act_idx'),
        ),
        migrations.AddIndex(
            model_name='forumactivityhistory',
            index=models.Index(fields=['performed_by', '-created_at'], name='forums_foru_perform_idx'),
        ),
    ]
