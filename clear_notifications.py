#!/usr/bin/env python
"""
Script to clear all notifications and verify tab mappings
Run with: python manage.py shell < clear_notifications.py
"""

from forums.models import Notification
from forums.notification_service import NotificationService

# Clear all notifications
print("=" * 60)
print("CLEARING ALL NOTIFICATIONS")
print("=" * 60)
count, _ = Notification.objects.all().delete()
print(f"✓ Deleted {count} notifications\n")

# Display tab mapping
print("=" * 60)
print("NOTIFICATION TAB MAPPING")
print("=" * 60)
for notif_type, tab in sorted(NotificationService.NOTIFICATION_TAB_MAP.items()):
    print(f"{notif_type:30} -> {tab}")

print("\n" + "=" * 60)
print("EXPECTED FRONTEND TABS")
print("=" * 60)
expected_tabs = ['feed', 'meetings', 'payments', 'disbursements', 'members', 'about', 'announcements', 'polls', 'settings']
for tab in expected_tabs:
    print(f"  - {tab}")

print("\n" + "=" * 60)
print("DATABASE STATE")
print("=" * 60)
print(f"Total notifications: {Notification.objects.count()}")
print("✓ Database cleared successfully!")
