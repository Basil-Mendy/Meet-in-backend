"""
WebSocket routes configuration for Django Channels
"""

from django.urls import re_path
from .consumers import TestConsumer, DebugConsumer, NotificationConsumer, ForumConsumer

websocket_urlpatterns = [
    # Try both with and without leading slash - one should match
    re_path(r'^/ws/notifications/?$', TestConsumer.as_asgi()),
    re_path(r'^ws/notifications/?$', TestConsumer.as_asgi()),
    
    # Catch-all to see what paths are being received
    re_path(r'^.*$', DebugConsumer.as_asgi()),
]
