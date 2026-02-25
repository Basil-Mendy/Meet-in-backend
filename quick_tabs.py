import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from forums.models import Notification
from django.db.models import Count
for r in Notification.objects.filter(is_read=False).values('tab').annotate(count=Count('id')):
    print(f"{r['tab']}: {r['count']}")
