import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from accounts.models import User, Profile
from alumni.models import School
from rest_framework.test import APIRequestFactory, force_authenticate
from forums.views import CreateForumView
from accounts.permissions import IsProfileCompleted
import random

email = f'debug{random.randint(100000,999999)}@example.com'
phone = f'080{random.randint(10000000,99999999)}'
user = User.objects.create_user(email=email, password='secret123', phone=phone, first_name='Creator', last_name='User')
profile, _ = Profile.objects.get_or_create(user=user)
profile.is_completed = True
profile.save(update_fields=['is_completed'])
print('profile saved', profile.id, profile.is_completed, hasattr(user, 'profile'))

factory = APIRequestFactory()
view = CreateForumView.as_view()

school = School.objects.create(
    name=f'Debug School {random.randint(1000,9999)}',
    address='Ikeja',
    country='Nigeria',
    state='Lagos',
    lga='Ikeja',
    year_established=1990,
    school_type='SECONDARY',
    created_by=user,
    is_approved=True,
)

payload = {
    'forum_type': 'SCHOOL_CLASS',
    'school': str(school.id),
    'graduation_year': 2025,
    'nickname': 'Alpha Class',
    'name': 'Alpha Class of 2025',
    'description': 'A class forum',
}
request = factory.post('/api/forums/create/', payload, format='json')
force_authenticate(request, user=user)
request.user = user

permission = IsProfileCompleted()
print('profile exists in DB', Profile.objects.filter(user=user).exists())
print('request.user.profile attr', hasattr(request.user, 'profile'))
print('permission has_permission', permission.has_permission(request, view))

response = view(request)
print('response type', type(response))
print('status', response.status_code)
try:
    print('data:', response.data)
except Exception as exc:
    print('no data attr', exc)
print('content', response.rendered_content if hasattr(response, 'rendered_content') else 'no rendered_content')
