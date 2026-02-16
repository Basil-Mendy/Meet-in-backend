# Generated migration for Poll model updates

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('forums', '0009_announcementrecipient_and_more'),
    ]

    operations = [
        # Add new fields to Poll
        migrations.AddField(
            model_name='poll',
            name='title',
            field=models.CharField(default='Untitled Poll', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='poll',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='poll',
            name='start_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='poll',
            name='end_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='poll',
            name='ballot_type',
            field=models.CharField(choices=[('SECRET', 'Secret Ballot'), ('OPEN', 'Open Ballot')], default='SECRET', max_length=10),
        ),
        migrations.AddField(
            model_name='poll',
            name='vote_type',
            field=models.CharField(choices=[('SINGLE', 'Vote Once Only'), ('MULTIPLE', 'Vote Multiple Times')], default='SINGLE', max_length=10),
        ),
        migrations.AddField(
            model_name='poll',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='poll',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        
        # Alter ends_at field
        migrations.AlterField(
            model_name='poll',
            name='ends_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        
        # Rename question field and Make it optional for backward compat
        migrations.AlterField(
            model_name='poll',
            name='question',
            field=models.CharField(blank=True, max_length=500),
        ),
        
        # Add indexes to Poll
        migrations.AddIndex(
            model_name='poll',
            index=models.Index(fields=['forum', 'is_archived'], name='forums_poll_forum_is_ar_idx'),
        ),
        migrations.AddIndex(
            model_name='poll',
            index=models.Index(fields=['start_time', 'end_time'], name='forums_poll_start_end_idx'),
        ),
        
        # Update PollOption
        migrations.AddField(
            model_name='polloption',
            name='option_text',
            field=models.CharField(default='Option', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='polloption',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='polloption',
            name='text',
            field=models.CharField(blank=True, max_length=255),
        ),
        
        migrations.AddIndex(
            model_name='polloption',
            index=models.Index(fields=['poll'], name='forums_poll_option_poll_idx'),
        ),
        
        # Update PollVote
        migrations.AddField(
            model_name='pollvote',
            name='voter',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='poll_votes', to='accounts.user'),
        ),
        migrations.AddField(
            model_name='pollvote',
            name='voted_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        
        # Rename user to maintain backward compat but use voter as primary
        migrations.AlterField(
            model_name='pollvote',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='poll_votes_alt', to='accounts.user'),
        ),
        
        # Remove unique_together constraint, will re-add with voter field
        migrations.AlterUniqueTogether(
            name='pollvote',
            unique_together=set(),
        ),
        
        # Add new unique constraint with voter field
        migrations.AddConstraint(
            model_name='pollvote',
            constraint=models.UniqueConstraint(fields=['poll', 'option', 'voter'], name='unique_vote_per_user_option'),
        ),
        
        migrations.AddIndex(
            model_name='pollvote',
            index=models.Index(fields=['poll', 'voter'], name='forums_poll_vote_poll_voter_idx'),
        ),
        migrations.AddIndex(
            model_name='pollvote',
            index=models.Index(fields=['option'], name='forums_poll_vote_option_idx'),
        ),
    ]
