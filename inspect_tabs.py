import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Notification
from django.db.models import Count

# Group all unread notifications by tab
by_tab = Notification.objects.filter(is_read=False).values('tab').annotate(count=Count('id')).order_by('-count')
print("Notifications by tab:")
for row in by_tab:
    print(f"  Tab: '{row['tab']}' -> {row['count']} unread")

print("\nAll unique tabs in DB:")
tabs = Notification.objects.filter(is_read=False).values_list('tab', flat=True).distinct()
for tab in tabs:
    print(f"  '{tab}'")
