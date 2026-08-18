from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('forums', '0016_targeted_announcements'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberactivity',
            name='posts_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='comments_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='reactions_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='payments_paid',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='polls_participated',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='forum_open_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='last_open_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='last_calculated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='ring_level',
            field=models.CharField(default='Dormant', max_length=32),
        ),
        migrations.AddField(
            model_name='memberactivity',
            name='ring_color',
            field=models.CharField(default='#9CA3AF', max_length=16),
        ),
        migrations.AlterField(
            model_name='memberactivity',
            name='activity_score',
            field=models.FloatField(default=0.0),
        ),
    ]
