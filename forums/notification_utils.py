"""
Notifications utility - Helper functions to create notifications for forum events
"""

from .models import Notification, UserNotificationPreference
from django.contrib.auth import get_user_model

User = get_user_model()


def create_notification(
    user,
    forum,
    notification_type,
    title,
    message,
    tab,
    object_id=None
):
    """
    Create a notification for a user
    
    Args:
        user: User object (recipient)
        forum: Forum object
        notification_type: One of Notification.NOTIFICATION_TYPES
        title: Short notification title
        message: Detailed notification message
        tab: Which tab to direct user to (feed, meetings, payments, etc.)
        object_id: Optional ID of the related object (post, meeting, payment, etc.)
    
    Returns:
        Notification object or None if user has disabled this notification type
    """
    # Check user preferences
    prefs = get_notification_preferences(user)
    
    # Get the preference field for this notification type
    pref_field = get_preference_field(notification_type)
    
    # Check if user wants in-app notifications for this type
    if not getattr(prefs, f"{pref_field}_in_app", True):
        return None
    
    # Create the notification
    notification = Notification.objects.create(
        user=user,
        forum=forum,
        notification_type=notification_type,
        title=title,
        message=message,
        tab=tab,
        object_id=str(object_id) if object_id else None
    )
    
    return notification


def create_forum_notifications(
    forum,
    excluded_user=None,
    notification_type=None,
    title=None,
    message=None,
    tab=None,
    object_id=None
):
    """
    Create notifications for all members of a forum
    
    Args:
        forum: Forum object
        excluded_user: User to exclude (e.g., the one who triggered the event)
        notification_type: Notification type
        title: Notification title
        message: Notification message
        tab: Tab to direct to
        object_id: Related object ID
    
    Returns:
        List of created notifications
    """
    from .models import ForumMembership
    
    notifications = []
    
    # Get all active members of the forum
    members = ForumMembership.objects.filter(
        forum=forum,
        is_active=True
    ).select_related('user')
    
    for membership in members:
        # Skip excluded user
        if excluded_user and membership.user == excluded_user:
            continue
        
        # Create notification for this member
        notif = create_notification(
            user=membership.user,
            forum=forum,
            notification_type=notification_type,
            title=title,
            message=message,
            tab=tab,
            object_id=object_id
        )
        
        if notif:
            notifications.append(notif)
    
    return notifications


def get_notification_preferences(user):
    """
    Get or create notification preferences for a user
    """
    prefs, created = UserNotificationPreference.objects.get_or_create(
        user=user
    )
    return prefs


def get_preference_field(notification_type):
    """
    Map notification type to preference field prefix
    
    Returns the prefix like 'feed', 'meetings', 'payments', etc.
    """
    type_mapping = {
        # Feed
        'FEED_NEW_POST': 'feed',
        
        # Meetings
        'MEETING_CREATED': 'meetings',
        'MEETING_LIVE': 'meetings',
        'MEETING_ENDED': 'meetings',
        
        # Payments
        'PAYMENT_CREATED': 'payments',
        
        # Disbursements
        'DISBURSEMENT_CREATED': 'disbursements',
        
        # Members
        'MEMBER_ADDED': 'members',
        'MEMBER_REMOVED': 'members',
        'MEMBER_ROLE_ASSIGNED': 'members',
        'MEMBER_ROLE_REMOVED': 'members',
        'MEMBER_APPROVED': 'members',
        
        # Forum Info
        'FORUM_INFO_UPDATED': 'forum_info',
        
        # Announcements
        'ANNOUNCEMENT_CREATED': 'announcements',
        
        # Polls
        'POLL_CREATED': 'polls',
        'POLL_ACTIVE': 'polls',
        'POLL_CLOSED': 'polls',
    }
    
    return type_mapping.get(notification_type, 'feed')


def should_send_notification(user, notification_type, channel='in_app'):
    """
    Check if a user should receive a notification of a certain type via a channel
    
    Args:
        user: User object
        notification_type: Notification type
        channel: 'in_app', 'push', or 'email'
    
    Returns:
        Boolean indicating if notification should be sent
    """
    prefs = get_notification_preferences(user)
    pref_field = get_preference_field(notification_type)
    
    return getattr(prefs, f"{pref_field}_{channel}", True)


# Example usage in views.py:
#
# from .notification_utils import create_notification, create_forum_notifications
#
# # When a new post is created:
# post = ForumPost.objects.create(...)
# create_forum_notifications(
#     forum=forum,
#     excluded_user=request.user,  # Don't notify the creator
#     notification_type='FEED_NEW_POST',
#     title=f"New post in {forum.name}",
#     message=f"{request.user.get_full_name()} posted: {post.title[:50]}...",
#     tab='feed',
#     object_id=post.id
# )
#
# # When a meeting is created:
# meeting = Meeting.objects.create(...)
# create_forum_notifications(
#     forum=forum,
#     excluded_user=request.user,
#     notification_type='MEETING_CREATED',
#     title=f"New meeting in {forum.name}",
#     message=f"Admin created a new meeting: {meeting.title}",
#     tab='meetings',
#     object_id=meeting.id
# )
