#!/usr/bin/env python
"""
Debug script to check notification state in database
Run from backend folder with: python manage.py shell < debug_notifications.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from forums.models import Notification, Forum
from forums.notification_service import NotificationService

User = get_user_model()

print("\n" + "="*80)
print("NOTIFICATION DEBUG REPORT")
print("="*80)

# Get current user (first superuser)
try:
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()
    
    if not user:
        print("❌ No users found in database!")
        sys.exit(1)
    
    print(f"\n✓ Using user: {user.email}")

    # Get user's forums
    forums = Forum.objects.filter(memberships__user=user, memberships__is_active=True).distinct()
    print(f"✓ User has {forums.count()} forums\n")

    # Check notifications for each forum
    for forum in forums[:3]:  # Limit to first 3 forums
        print(f"\n📋 Forum: {forum.name} (ID: {forum.id})")
        print("-" * 80)
        
        # Get all unread notifications for this forum
        notifications = Notification.objects.filter(
            user=user,
            forum=forum,
            is_read=False
        ).order_by('-created_at')
        
        print(f"Total unread notifications: {notifications.count()}")
        
        # Group by tab
        tab_summary = {}
        for notif in notifications:
            tab = notif.tab or 'no_tab'
            if tab not in tab_summary:
                tab_summary[tab] = []
            tab_summary[tab].append({
                'type': notif.notification_type,
                'title': notif.title,
                'created': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        # Display summary
        if not tab_summary:
            print("  (no unread notifications)")
        else:
            for tab in sorted(tab_summary.keys()):
                count = len(tab_summary[tab])
                print(f"\n  Tab: {tab:20} Count: {count}")
                for notif in tab_summary[tab][:2]:  # Show first 2
                    print(f"    - [{notif['type']}] {notif['title']} ({notif['created']})")
                if count > 2:
                    print(f"    ... and {count - 2} more")
    
    # Display tab mapping for reference
    print(f"\n\n📚 NOTIFICATION TAB MAPPING REFERENCE")
    print("-" * 80)
    for notif_type, tab in sorted(NotificationService.NOTIFICATION_TAB_MAP.items()):
        print(f"  {notif_type:30} → {tab}")

    print("\n" + "="*80 + "\n")

except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)
