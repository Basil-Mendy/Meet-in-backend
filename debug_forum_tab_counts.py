import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Forum, Notification
from django.db.models import Count

forum_name = 'Abia Arise'
forum = Forum.objects.filter(name__icontains=forum_name).first()
if not forum:
    print('FORUM_NOT_FOUND')
    forums = Forum.objects.all()[:5]
    print('Sample forums:')
    for f in forums:
        print(f.id, f.name)
    exit(0)

print('Forum:', forum.id, forum.name)

# Total tab counts for this forum
tabs = Notification.objects.filter(forum=forum, is_read=False).values('tab').annotate(count=Count('id'))
print('\nUnread counts by tab for forum:')
for r in tabs:
    print(f"  tab='{r['tab']}' -> {r['count']}")

# Per-user breakdown
users = Notification.objects.filter(forum=forum, is_read=False).values('user_id').distinct()
print('\nPer-user totals:')
for u in users:
    uid = u['user_id']
    total = Notification.objects.filter(forum=forum, user_id=uid, is_read=False).count()
    tabs_u = Notification.objects.filter(forum=forum, user_id=uid, is_read=False).values('tab').annotate(count=Count('id'))
    print(f"  user {uid} -> total {total}")
    for tr in tabs_u:
        print(f"    {tr['tab']}: {tr['count']}")
