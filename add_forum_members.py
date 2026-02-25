import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Forum, ForumMembership
from django.contrib.auth import get_user_model

User = get_user_model()

# Get forum
forum = Forum.objects.first()
if not forum:
    print("NO_FORUM")
    exit(1)

# Get or create extra users
users = User.objects.all()[:3]
if len(users) < 2:
    print(f"Need at least 2 users, found {len(users)}")
    exit(1)

# Add them to forum if not already
for user in users[1:]:
    membership, created = ForumMembership.objects.get_or_create(
        user=user,
        forum=forum,
        defaults={'role': 'MEMBER'}
    )
    if created:
        print(f"✓ Added {user.email} to forum")
    else:
        print(f"✓ {user.email} already in forum")

forum_members = ForumMembership.objects.filter(forum=forum)
print(f"Forum now has {forum_members.count()} members")
