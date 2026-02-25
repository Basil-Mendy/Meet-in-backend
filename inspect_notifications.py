import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from django.db.models import Count
from forums.models import Notification

qs = Notification.objects.filter(is_read=False).values('user_id','forum_id','tab').annotate(count=Count('id'))
for row in qs:
    print(row)
print('TOTAL_UNREAD', Notification.objects.filter(is_read=False).count())
