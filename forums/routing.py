"""
WebSocket routes configuration for Django Channels
"""

from django.urls import re_path
from .consumers import NotificationConsumer

websocket_urlpatterns = [
    # WebSocket endpoint for notifications with token authentication
    re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
    re_path(r'^ws/notifications$', NotificationConsumer.as_asgi()),
]
