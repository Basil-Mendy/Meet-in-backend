import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Notification, Forum
from django.contrib.auth import get_user_model

User = get_user_model()

# Find a user with unread notifications
users_with_notifs = User.objects.filter(notifications__is_read=False).distinct()
print(f"Users with unread: {users_with_notifs.count()}")

if users_with_notifs.exists():
    user = users_with_notifs.first()
    print(f"\nUser: {user.email}")
    
    # Per-tab breakdown
    notifs = Notification.objects.filter(user=user, is_read=False)
    print(f"\nTotal unread for user: {notifs.count()}")
    
    from django.db.models import Count
    by_forum = notifs.values('forum_id').annotate(count=Count('id'))
    for row in by_forum:
        print(f"  Forum {row['forum_id']}: {row['count']} unread")
        
        by_tab = notifs.filter(forum_id=row['forum_id']).values('tab').annotate(count=Count('id'))
        for tab_row in by_tab:
            print(f"    Tab '{tab_row['tab']}': {tab_row['count']} unread")
