import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Notification, Forum
from django.contrib.auth import get_user_model
from django.db.models import Count

User = get_user_model()

user = User.objects.filter(notifications__is_read=False).distinct().first()

if user:
    forums = Forum.objects.filter(
        memberships__user=user,
        memberships__is_active=True
    ).distinct()
    
    print(f"User: {user.email}")
    
    forum_counts = {}
    tab_counts = {}
    global_count = 0
    
    for forum in forums:
        forum_id_str = str(forum.id)
        
        # Get total count per forum
        count = Notification.objects.filter(
            user=user,
            forum=forum,
            is_read=False
        ).count()
        forum_counts[forum_id_str] = count
        global_count += count
        
        # Get per-tab counts for this forum
        tab_counts[forum_id_str] = {}
        notifications = Notification.objects.filter(
            user=user,
            forum=forum,
            is_read=False
        ).values('tab').annotate(count=Count('id'))
        
        for notif in notifications:
            if notif['tab']:
                tab_counts[forum_id_str][notif['tab']] = notif['count']
    
    print("\nCounts API Response would be:")
    print(f"global_count: {global_count}")
    print(f"forum_counts: {forum_counts}")
    print(f"tab_counts: {tab_counts}")
else:
    print("No user with unread notifications found")
