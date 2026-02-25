import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from rest_framework.test import APIRequestFactory
from forums.views import NotificationViewSet
from django.contrib.auth import get_user_model

User = get_user_model()

factory = APIRequestFactory()
user = User.objects.filter(notifications__is_read=False).distinct().first()

if user:
    request = factory.get('/forums/notifications/counts/')
    request.user = user
    
    viewset = NotificationViewSet()
    viewset.request = request
    viewset.kwargs = {}
    
    response = viewset.unread_counts(request)
    print("API Response Status:", response.status_code)
    print("API Response Data:", response.data)
else:
    print("No users with unread notifications found")
