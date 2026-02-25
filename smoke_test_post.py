import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from forums.models import Forum, ForumPost, ForumMembership
from django.contrib.auth import get_user_model

User = get_user_model()

forum = Forum.objects.first()
if not forum:
    print('NO_FORUM')
else:
    membership = ForumMembership.objects.filter(forum=forum).first()
    if not membership:
        print('NO_MEMBERSHIP')
    else:
        author = membership.user
        post = ForumPost.objects.create(forum=forum, author=author, content='Smoke test post from automated script')
        print('CREATED_POST', str(post.id))
