import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Forum, ForumMembership, Poll, Meeting, Announcement, ForumPayment
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

# Get first forum and a member
forum = Forum.objects.first()
if not forum:
    print("NO_FORUM")
    exit(1)

# Get members
members = ForumMembership.objects.filter(forum=forum)
if members.count() < 2:
    print(f"NEED_2_MEMBERS, found {members.count()}")
    exit(1)

creator = members.first().user
other_user = members[1].user

print("Creating test notifications across different tabs...")

# 1. Announcement (announcements tab)
try:
    ann = Announcement.objects.create(
        forum=forum,
        created_by=creator,
        title='Test Announcement',
        message='This is a test announcement',
        announcement_type='FORUM'
    )
    print("✓ Created Announcement")
except Exception as e:
    print(f"✗ Failed to create Announcement: {e}")

# 2. Meeting (meetings tab)
try:
    meeting = Meeting.objects.create(
        forum=forum,
        created_by=creator,
        title='Test Meeting',
        description='Test meeting',
        meeting_type='VIRTUAL',
        scheduled_start=timezone.now() + timedelta(hours=1),
        scheduled_end=timezone.now() + timedelta(hours=2),
        room_id='test-room.nNqRu'
    )
    print("✓ Created Meeting")
except Exception as e:
    print(f"✗ Failed to create Meeting: {e}")

# 3. Poll (polls tab)
try:
    poll = Poll.objects.create(
        forum=forum,
        created_by=creator,
        title='Test Poll',
        description='Test poll',
        ballot_type='SECRET',
        vote_type='SINGLE',
        start_time=timezone.now(),
        end_time=timezone.now() + timedelta(days=1)
    )
    print("✓ Created Poll")
except Exception as e:
    print(f"✗ Failed to create Poll: {e}")

# 4. ForumPayment (payments tab)
try:
    payment = ForumPayment.objects.create(
        forum=forum,
        created_by=creator,
        payment_type='DUES',
        name='Test Payment',
        amount=1000.00
    )
    print("✓ Created ForumPayment")
except Exception as e:
    print(f"✗ Failed to create ForumPayment: {e}")

print("\nCheck notifications by tab in DB...")
from django.db.models import Count
by_tab = Announcement.objects.filter(is_read=False).values('tab').annotate(count=Count('id'))
