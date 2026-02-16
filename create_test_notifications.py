import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from forums.models import Notification, Forum
from django.contrib.auth import get_user_model

User = get_user_model()

# Get first forum and first user
forums = Forum.objects.all()[:1]
users = User.objects.all()[:1]

if forums and users:
    forum = forums[0]
    user = users[0]
    
    # Delete any existing test notifications
    Notification.objects.filter(user=user, forum=forum).delete()
    
    # Create test notifications
    notifs = []
    notifs.append(Notification.objects.create(
        user=user,
        forum=forum,
        notification_type='FEED_NEW_POST',
        title=f'New post in {forum.name}',
        message='John posted: Check out this amazing discussion!',
        tab='feed'
    ))
    notifs.append(Notification.objects.create(
        user=user,
        forum=forum,
        notification_type='MEETING_CREATED',
        title='New meeting scheduled',
        message='Admin created: Q1 Planning Meeting',
        tab='meetings'
    ))
    notifs.append(Notification.objects.create(
        user=user,
        forum=forum,
        notification_type='ANNOUNCEMENT_CREATED',
        title='New announcement',
        message='Important: Click to read the latest announcement',
        tab='announcements'
    ))
    
    print(f'✅ Created {len(notifs)} test notifications')
    print(f'User: {user.email}')
    print(f'Forum: {forum.name}')
    print(f'Total unread: {Notification.objects.filter(user=user, is_read=False).count()}')
else:
    print('❌ No forums or users found')
