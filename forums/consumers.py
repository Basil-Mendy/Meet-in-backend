"""
WebSocket consumers for real-time notification delivery
Uses Django Channels for WebSocket connections
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class TestConsumer(AsyncWebsocketConsumer):
    """Minimal test consumer - accepts all connections"""
    
    async def connect(self):
        print("[TEST-CONSUMER] Connect called!")
        await self.accept()
        print("[TEST-CONSUMER] Connection accepted")


class DebugConsumer(AsyncWebsocketConsumer):
    """Catch-all consumer to debug path matching"""
    
    async def connect(self):
        path = self.scope.get('path', 'NO_PATH')
        print(f"[DEBUG-CATCHALL] Received path: {path}")
        print(f"[DEBUG-CATCHALL] Full scope keys: {list(self.scope.keys())}")
        await self.accept()
        print("[DEBUG-CATCHALL] Connection accepted")


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications
    
    Protocol:
    - Client sends: {"action": "subscribe", "user_id": "..."}
    - Server sends notifications in real-time: {"type": "notification_message", "notification": {...}}
    """

    async def connect(self):
        """Handle WebSocket connection - authenticate via JWT token"""
        # Initialize attributes first to prevent errors if connect fails
        self.user = None
        self.user_id = None
        self.room_name = None
        
        try:
            # Get token from query string
            query_string = self.scope.get("query_string", b"").decode("utf-8")
            print(f"[WS-CONNECT] Query string: {query_string[:100]}")
            
            if "token=" not in query_string:
                print("[WS-CONNECT] ERROR: No token in query string, closing connection")
                await self.close()
                return
            
            # Extract and validate token
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from accounts.models import User
            
            token_string = query_string.split("token=")[1].split("&")[0]
            print(f"[WS-CONNECT] Extracted token (first 50 chars): {token_string[:50]}...")
            
            try:
                access_token = AccessToken(token_string)
                user_id = access_token["user_id"]
                print(f"[WS-CONNECT] Token decoded, user_id: {user_id}")
            except (InvalidToken, TokenError) as e:
                print(f"[WS-CONNECT] Token validation failed: {e}")
                await self.close()
                return
            
            # Get user from database
            self.user = await self.get_user(user_id)
            if not self.user:
                print(f"[WS-CONNECT] User not found: {user_id}")
                await self.close()
                return
            print(f"[WS-CONNECT] User fetched: {self.user}")
            
        except Exception as e:
            print(f"[WS-CONNECT] ERROR: {e}")
            import traceback
            traceback.print_exc()
            await self.close()
            return
        
        # Store user_id and setup group
        self.user_id = str(self.user.id)
        self.room_name = f'notification_{self.user_id}'
        
        # Add to group
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"[WS] ✓ User {self.user_id} connected to notifications")
        logger.info(f"[WS] ✓ User {self.user_id} connected to notifications")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Only try to remove from group if room_name was set (i.e., connection succeeded)
        if hasattr(self, 'room_name') and self.room_name:
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )
            print(f"[WS] ✗ User disconnected from notifications")
            if hasattr(self, 'user_id'):
                logger.info(f"[WS] User {self.user_id} disconnected (code: {close_code})")

    async def receive(self, text_data):
        """
        Handle messages from client
        
        Expected message format:
        {
            "action": "mark_as_read",
            "notification_ids": ["id1", "id2"],
            "tab": "feed",
            "forum_id": "forum_uuid"
        }
        """
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'mark_as_read':
                notification_ids = data.get('notification_ids', [])
                forum_id = data.get('forum_id')
                tab = data.get('tab')
                
                if notification_ids:
                    await self.mark_notifications_read(notification_ids)
                elif forum_id and tab:
                    await self.mark_tab_notifications_read(forum_id, tab)
                elif forum_id:
                    await self.mark_forum_notifications_read(forum_id)
            
            elif action == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': str(__import__('django.utils.timezone', fromlist=['now']).now())
                }))
        
        except json.JSONDecodeError:
            print(f"Invalid JSON received: {text_data}")
        except Exception as e:
            print(f"Error processing message: {e}")

    async def notification_message(self, event):
        """
        Send notification to WebSocket
        Called by other consumers via group_send
        """
        notification = event.get('notification')
        
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': notification,
        }))

    @database_sync_to_async
    def get_user(self, user_id):
        """Get user object from ID"""
        from accounts.models import User
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def mark_notifications_read(self, notification_ids):
        """Mark specific notifications as read"""
        from .models import Notification
        Notification.objects.filter(
            id__in=notification_ids,
            user_id=self.user_id
        ).update(is_read=True)

    @database_sync_to_async
    def mark_tab_notifications_read(self, forum_id, tab):
        """Mark all notifications for a tab as read"""
        from .models import Notification
        Notification.objects.filter(
            user_id=self.user_id,
            forum_id=forum_id,
            tab=tab,
            is_read=False
        ).update(is_read=True)

    @database_sync_to_async
    def mark_forum_notifications_read(self, forum_id):
        """Mark all notifications for a forum as read"""
        from .models import Notification
        Notification.objects.filter(
            user_id=self.user_id,
            forum_id=forum_id,
            is_read=False
        ).update(is_read=True)


class ForumConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for forum-specific real-time updates
    Handles posts, comments, members, etc.
    """

    async def connect(self):
        """Handle forum WebSocket connection"""
        self.forum_id = self.scope['url_route']['kwargs'].get('forum_id')
        self.room_name = f'forum_{self.forum_id}'
        
        # Get user from scope
        self.user = self.scope.get('user')
        if not self.user or self.user == AnonymousUser():
            await self.close()
            return
        
        # Add to forum group
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"User {self.user.id} connected to forum {self.forum_id}")

    async def disconnect(self, close_code):
        """Handle forum disconnection"""
        if self.room_name:
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle messages in forum (typing indicators, etc.)"""
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            if event_type == 'typing':
                await self.channel_layer.group_send(
                    self.room_name,
                    {
                        'type': 'user_typing',
                        'user_id': str(self.user.id),
                        'user_name': self.user.get_full_name(),
                    }
                )
        except Exception as e:
            print(f"Error in forum consumer: {e}")

    async def forum_update(self, event):
        """Send forum update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'forum_update',
            'data': event.get('data'),
        }))

    async def user_typing(self, event):
        """Send typing indicator"""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
        }))
