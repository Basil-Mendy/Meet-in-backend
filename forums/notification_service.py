"""
Unified Notification Service
Handles all notification creation, delivery, and management
Event-driven architecture with WebSocket support
"""

import json
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import (
    Notification, 
    UserNotificationPreference, 
    Forum, 
    ForumMembership
)
from accounts.models import User
from .email_service import EmailService


class NotificationService:
    """
    Central service for managing forum notifications
    Handles creation, delivery (in-app, push, email), and tracking
    """

    # Tab mapping for notification types
    NOTIFICATION_TAB_MAP = {
        'FEED_NEW_POST': 'feed',
        'FEED_POST_PINNED': 'feed',
        'MEETING_CREATED': 'meetings',
        'MEETING_LIVE': 'meetings',
        'MEETING_ENDED': 'meetings',
        'PAYMENT_CREATED': 'payments',
        'DISBURSEMENT_CREATED': 'disbursements',
        'MEMBER_ADDED': 'members',
        'MEMBER_REMOVED': 'members',
        'MEMBER_ROLE_ASSIGNED': 'members',
        'MEMBER_ROLE_REMOVED': 'members',
        'MEMBER_APPROVED': 'settings',
        'FORUM_INFO_UPDATED': 'about',
        'ANNOUNCEMENT_CREATED': 'announcements',
        'POLL_CREATED': 'polls',
        'POLL_ACTIVE': 'polls',
        'POLL_CLOSED': 'polls',
    }

    NOTIFICATION_MESSAGES = {
        'FEED_NEW_POST': {
            'title_template': 'New post in {forum_name}',
            'message_template': '{user_name} posted: "{content[:50]}..."',
        },
        'FEED_POST_PINNED': {
            'title_template': 'Post pinned in {forum_name}',
            'message_template': 'Admin pinned a post: "{content[:50]}..."',
        },
        'MEETING_CREATED': {
            'title_template': 'New meeting in {forum_name}',
            'message_template': '{user_name} created meeting: {meeting_title}',
        },
        'MEETING_LIVE': {
            'title_template': 'Meeting is live in {forum_name}',
            'message_template': 'Meeting "{meeting_title}" is now live',
        },
        'MEETING_ENDED': {
            'title_template': 'Meeting ended in {forum_name}',
            'message_template': 'Meeting "{meeting_title}" has ended',
        },
        'PAYMENT_CREATED': {
            'title_template': 'New payment in {forum_name}',
            'message_template': 'New payment created: {payment_title}',
        },
        'DISBURSEMENT_CREATED': {
            'title_template': 'Disbursement in {forum_name}',
            'message_template': 'Disbursement made: {amount}',
        },
        'MEMBER_ADDED': {
            'title_template': 'New member in {forum_name}',
            'message_template': '{user_name} has joined the forum',
        },
        'MEMBER_REMOVED': {
            'title_template': 'Member removed from {forum_name}',
            'message_template': '{user_name} has been removed',
        },
        'MEMBER_ROLE_ASSIGNED': {
            'title_template': 'Role assignment in {forum_name}',
            'message_template': '{user_name} is now {role}',
        },
        'MEMBER_ROLE_REMOVED': {
            'title_template': 'Role removed in {forum_name}',
            'message_template': '{user_name}\'s {role} role was removed',
        },
        'MEMBER_APPROVED': {
            'title_template': 'Membership approved in {forum_name}',
            'message_template': 'Your membership has been approved',
        },
        'FORUM_INFO_UPDATED': {
            'title_template': '{forum_name} information updated',
            'message_template': 'Forum information has been updated',
        },
        'ANNOUNCEMENT_CREATED': {
            'title_template': 'New announcement in {forum_name}',
            'message_template': 'New announcement: {announcement_title}',
        },
        'POLL_CREATED': {
            'title_template': 'New poll in {forum_name}',
            'message_template': 'Poll: {poll_question}',
        },
        'POLL_ACTIVE': {
            'title_template': 'Poll active in {forum_name}',
            'message_template': 'Poll is now active: {poll_question}',
        },
        'POLL_CLOSED': {
            'title_template': 'Poll closed in {forum_name}',
            'message_template': 'Poll has closed: {poll_question}',
        },
    }

    @staticmethod
    def create_notification(
        forum: Forum,
        user: User,
        notification_type: str,
        title: str,
        message: str,
        tab: Optional[str] = None,
        object_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        send_push: Optional[bool] = None,
        send_email: Optional[bool] = None,
    ) -> Notification:
        """
        Create a single notification for a user
        
        Args:
            forum: Forum object
            user: User object to notify
            notification_type: Type of notification (FEED_NEW_POST, etc)
            title: Notification title
            message: Notification message
            tab: Forum tab to direct user to
            object_id: ID of related object (post, meeting, payment, etc)
            metadata: Additional metadata as dict
            send_push: Override preference and force push (True/False/None)
            send_email: Override preference and force email (True/False/None)
        
        Returns:
            Notification object
        """
        
        # Determine tab if not provided
        if not tab:
            tab = NotificationService.NOTIFICATION_TAB_MAP.get(notification_type, 'feed')
        
        # Create the notification
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                forum=forum,
                notification_type=notification_type,
                title=title,
                message=message,
                tab=tab,
                object_id=object_id or '',
                is_read=False,
            )
            
            # Send push and email based on preferences
            NotificationService._send_notification(
                notification=notification,
                send_push=send_push,
                send_email=send_email,
            )
            
            # Broadcast via WebSocket
            NotificationService._broadcast_notification(notification)
        
        return notification

    @staticmethod
    def create_forum_notifications(
        forum: Forum,
        notification_type: str,
        title: str,
        message: str,
        tab: Optional[str] = None,
        object_id: Optional[str] = None,
        excluded_users: Optional[List[User]] = None,
        include_users: Optional[List[User]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        send_push: Optional[bool] = None,
        send_email: Optional[bool] = None,
    ) -> List[Notification]:
        """
        Create notifications for multiple forum members
        
        Args:
            forum: Forum object
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            tab: Forum tab to direct to
            object_id: ID of related object
            excluded_users: Users to exclude from notification
            include_users: If provided, only notify these users. If None, notify all active members
            metadata: Additional metadata
            send_push: Override default push preference
            send_email: Override default email preference
        
        Returns:
            List of created Notification objects
        """
        
        excluded_users = excluded_users or []
        
        # Get target users
        if include_users is not None:
            target_users = include_users
        else:
            # Get all active forum members
            target_users = User.objects.filter(
                forummembership__forum=forum,
                forummembership__is_active=True,
            ).exclude(id__in=[u.id for u in excluded_users]).distinct()
        
        print(f"[Notification] Creating {notification_type} for {forum.name}, notifying {target_users.count()} users (push={send_push}, email={send_email})")
        
        notifications = []
        with transaction.atomic():
            for user in target_users:
                try:
                    notification = NotificationService.create_notification(
                        forum=forum,
                        user=user,
                        notification_type=notification_type,
                        title=title,
                        message=message,
                        tab=tab,
                        object_id=object_id,
                        metadata=metadata,
                        send_push=send_push,
                        send_email=send_email,
                    )
                    notifications.append(notification)
                    print(f"[Notification] ✓ Created notification for {user.email}")
                except Exception as e:
                    print(f"[Notification] ✗ Failed to create notification for {user.email}: {e}")
        
        print(f"[Notification] Created {len(notifications)} notifications")
        return notifications
        return notifications

    @staticmethod
    def _send_notification(
        notification: Notification,
        send_push: Optional[bool] = None,
        send_email: Optional[bool] = None,
    ) -> None:
        """
        Send push and email notifications based on user preferences
        
        Args:
            notification: Notification object
            send_push: Override preference
            send_email: Override preference
        """
        
        # Get user preferences
        try:
            prefs = UserNotificationPreference.objects.get(user=notification.user)
        except UserNotificationPreference.DoesNotExist:
            prefs = UserNotificationPreference.objects.create(user=notification.user)
        
        # Determine notification type category (feed, meetings, etc)
        notif_type = notification.notification_type
        
        # Map to preference field prefix
        prefix_map = {
            'FEED': 'feed',
            'MEETING': 'meetings',
            'PAYMENT': 'payments',
            'DISBURSEMENT': 'disbursements',
            'MEMBER': 'members',
            'FORUM_INFO': 'forum_info',
            'ANNOUNCEMENT': 'announcements',
            'POLL': 'polls',
        }
        
        # Find matching prefix
        pref_prefix = None
        for key, prefix in prefix_map.items():
            if notif_type.startswith(key):
                pref_prefix = prefix
                break
        
        if not pref_prefix:
            pref_prefix = 'feed'
        
        # Check push preference (default True)
        should_push = send_push if send_push is not None else getattr(prefs, f'{pref_prefix}_push', True)
        
        # Check email preference (default False for most, True for meetings/payments)
        should_email = send_email if send_email is not None else getattr(
            prefs, 
            f'{pref_prefix}_email', 
            pref_prefix in ['meetings', 'payments', 'announcements']
        )
        
        # Send push notification
        if should_push:
            NotificationService._send_push_notification(notification)
        
        # Send email notification
        if should_email:
            NotificationService._send_email_notification(notification)

    @staticmethod
    def _send_push_notification(notification: Notification) -> None:
        """Send push notification via WebSocket (for now, can integrate with Firebase later)"""
        print(f"[Notification] Sending push notification to {notification.user.email}")
        NotificationService._broadcast_notification(notification, is_push=True)

    @staticmethod
    def _send_email_notification(notification: Notification) -> None:
        """Send email notification"""
        try:
            subject = notification.title
            html_message = f"""
            <h2>{notification.title}</h2>
            <p>{notification.message}</p>
            <p style="margin-top: 20px; color: #666;">
                Forum: <strong>{notification.forum.name}</strong>
            </p>
            <a href="{settings.FRONTEND_URL}/forum/{notification.forum.id}/{notification.tab}" 
               style="display: inline-block; margin-top: 15px; padding: 10px 20px; 
                      background-color: #007bff; color: white; text-decoration: none; 
                      border-radius: 5px;">
                View in {notification.tab.title()}
            </a>
            """
            plain_message = strip_tags(html_message)

            # Use EmailService for sending central/system emails (Flow A)
            print(f"[Notification] Sending system email to {notification.user.email}")
            EmailService.send_system_notification(
                subject=subject,
                html_body=html_message,
                text_body=plain_message,
                to=[notification.user.email],
                forum=notification.forum,
            )
            print(f"[Notification] ✓ System email sent to {notification.user.email}")
        except Exception as e:
            print(f"[Notification] ✗ Failed to send email notification: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _broadcast_notification(
        notification: Notification,
        is_push: bool = False,
    ) -> None:
        """
        Broadcast notification via WebSocket to connected clients
        
        Args:
            notification: Notification object
            is_push: If True, mark as push notification
        """
        try:
            channel_layer = get_channel_layer()
            
            # Construct notification payload
            payload = {
                'type': 'notification_message',
                'notification': {
                    'id': str(notification.id),
                    'forum_id': str(notification.forum.id),
                    'forum_name': notification.forum.name,
                    'user_id': str(notification.user.id),
                    'notification_type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'tab': notification.tab,
                    'object_id': notification.object_id,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                    'is_push': is_push,
                },
            }
            
            # Send to user's notification group
            user_room = f'notification_{notification.user.id}'
            
            print(f"[WebSocket] Broadcasting to {user_room}")
            async_to_sync(channel_layer.group_send)(
                user_room,
                payload
            )
            print(f"[WebSocket] ✓ Notification broadcasted to {user_room}")
        except Exception as e:
            print(f"[WebSocket] ✗ Failed to broadcast notification: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def mark_as_read(
        notification_ids: Optional[List[str]] = None,
        user: Optional[User] = None,
        forum: Optional[Forum] = None,
        tab: Optional[str] = None,
    ) -> int:
        """
        Mark notifications as read
        
        Args:
            notification_ids: Specific notification IDs to mark
            user: User whose notifications to mark
            forum: Forum to limit to
            tab: Tab to limit to
        
        Returns:
            Number of notifications marked as read
        """
        
        query = Notification.objects.filter(is_read=False)
        
        if notification_ids:
            query = query.filter(id__in=notification_ids)
        
        if user:
            query = query.filter(user=user)
        
        if forum:
            query = query.filter(forum=forum)
        
        if tab:
            query = query.filter(tab=tab)
        
        count, _ = query.update(is_read=True)
        return count

    @staticmethod
    def get_unread_counts(user: User) -> Dict[str, Any]:
        """
        Get unread notification counts for a user
        
        Returns:
            {
                'global_count': int,
                'forum_counts': {forum_id: count, ...},
                'tab_counts': {forum_id: {tab: count, ...}, ...}
            }
        """
        
        # Get user's forums
        forums = Forum.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
        ).distinct()
        
        global_count = 0
        forum_counts = {}
        tab_counts = {}
        
        for forum in forums:
            forum_id = str(forum.id)
            
            # Get unread count for this forum
            forum_unread = Notification.objects.filter(
                user=user,
                forum=forum,
                is_read=False,
            ).count()
            
            forum_counts[forum_id] = forum_unread
            global_count += forum_unread
            
            # Get tab-level counts
            tab_data = {}
            for tab_choice in ['feed', 'meetings', 'payments', 'disbursements', 'members', 'about', 'announcements', 'polls', 'settings']:
                tab_unread = Notification.objects.filter(
                    user=user,
                    forum=forum,
                    tab=tab_choice,
                    is_read=False,
                ).count()
                
                if tab_unread > 0:
                    tab_data[tab_choice] = tab_unread
            
            if tab_data:
                tab_counts[forum_id] = tab_data
        
        return {
            'global_count': global_count,
            'forum_counts': forum_counts,
            'tab_counts': tab_counts,
        }

    @staticmethod
    def get_tab_notifications(
        user: User,
        forum: Forum,
        tab: str,
        limit: int = 10,
    ) -> List[Notification]:
        """Get notifications for a specific tab"""
        
        return Notification.objects.filter(
            user=user,
            forum=forum,
            tab=tab,
        ).order_by('-created_at')[:limit]


# Convenience function for backward compatibility
def create_forum_notifications(
    forum: Forum,
    notification_type: str,
    title: str,
    message: str,
    tab: Optional[str] = None,
    object_id: Optional[str] = None,
    excluded_user: Optional[User] = None,
    excluded_users: Optional[List[User]] = None,
    include_users: Optional[List[User]] = None,
) -> List[Notification]:
    """
    Convenience function for creating notifications for all forum members
    """
    
    if excluded_user:
        excluded_users = [excluded_user]
    
    return NotificationService.create_forum_notifications(
        forum=forum,
        notification_type=notification_type,
        title=title,
        message=message,
        tab=tab,
        object_id=object_id,
        excluded_users=excluded_users,
        include_users=include_users,
    )
