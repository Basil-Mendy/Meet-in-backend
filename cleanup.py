#!/usr/bin/env python
"""Clear all notifications for fresh test."""
if __name__ == '__main__':
    import os
    import sys
    import django
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    from forums.models import Notification
    
    count = Notification.objects.count()
    print(f"\n{'='*50}")
    print("CLEARING NOTIFICATIONS")
    print(f"{'='*50}")
    print(f"Before: {count} notifications")
    
    Notification.objects.all().delete()
    
    remaining = Notification.objects.count()
    print(f"After:  {remaining} notifications")
    print(f"{'='*50}\n")
