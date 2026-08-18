import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from forums.views import ReviewJoinRequestView
from forums.membership_views import ForumMembersViewSet
from forums.models import Forum, ForumMembership, ForumJoinRequest
from django.contrib.auth import get_user_model

User = get_user_model()
forum = Forum.objects.filter(name__icontains='Golden Boot').first()
print('forum', forum)
if not forum:
    raise SystemExit('Golden Boot FC forum not found')
creator = forum.created_by
print('creator', creator.id, creator.email)

user, created = User.objects.get_or_create(
    email='goldenboot-testuser@example.com',
    defaults={
        'phone': '08000000000',
        'first_name': 'Golden',
        'last_name': 'Boot',
        'is_active': True,
    },
)
print('requester', user.id, 'created', created)

jr = ForumJoinRequest.objects.filter(user=user, forum=forum, status='PENDING').first()
if not jr:
    ForumMembership.objects.filter(user=user, forum=forum).delete()
    jr = ForumJoinRequest.objects.create(user=user, forum=forum, invitation_code='', status='PENDING')
    print('created join request', jr.id)
else:
    print('existing pending join request', jr.id)
    # remove any duplicate membership from previous test runs
    ForumMembership.objects.filter(user=user, forum=forum).delete()
    print('removed stale membership if present')

factory = APIRequestFactory()
req = factory.post(f'/api/forums/join-requests/{jr.id}/review/', {'action': 'approve'}, format='json')
force_authenticate(req, user=creator)
response = ReviewJoinRequestView.as_view()(req, request_id=str(jr.id))
print('review response status', response.status_code)
print('review response data', response.data)

member = ForumMembership.objects.filter(user=user, forum=forum).first()
if not member:
    member = ForumMembership.objects.create(user=user, forum=forum, role='MEMBER', is_active=True)
    print('created member', member.id)
else:
    print('member exists', member.id, member.role)

req2 = factory.post(f'/api/forums/{forum.id}/members/{member.id}/assign-role/', {'role': 'PRO'}, format='json')
force_authenticate(req2, user=creator)
response2 = ForumMembersViewSet.as_view({'post': 'assign_role'})(req2, forum_id=str(forum.id), pk=str(member.id))
print('assign role response status', response2.status_code)
print('assign role response data', response2.data)
