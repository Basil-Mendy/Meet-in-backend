"""
Activity tracking utilities for recording forum activities/history.
Used to create ForumActivityHistory records throughout the application.
"""

from django.utils import timezone
from .models import ForumActivityHistory


def log_activity(
    forum,
    performed_by,
    activity_type,
    tab,
    title,
    description="",
    object_id=None,
    object_type=None,
    metadata=None
):
    """
    Log a forum activity to the activity history.
    
    Args:
        forum: Forum instance
        performed_by: User instance who performed the action
        activity_type: Type of activity (from ACTIVITY_TYPE_CHOICES)
        tab: Tab affected (from TAB_CHOICES)
        title: Short title of the activity
        description: Detailed description (optional)
        object_id: ID of related object (optional)
        object_type: Type of related object (optional)
        metadata: Additional JSON metadata (optional)
    
    Returns:
        ForumActivityHistory instance (created)
    """
    return ForumActivityHistory.objects.create(
        forum=forum,
        performed_by=performed_by,
        activity_type=activity_type,
        tab=tab,
        title=title,
        description=description,
        object_id=str(object_id) if object_id else None,
        object_type=object_type,
        metadata=metadata or {}
    )


# Convenience functions for common activity types

def log_post_created(forum, performed_by, post):
    """Log when a forum post is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="post_created",
        tab="feed",
        title=f"Post created: {post.content[:50]}...",
        description=post.content,
        object_id=post.id,
        object_type="ForumPost"
    )


def log_post_deleted(forum, performed_by, post_title):
    """Log when a forum post is deleted"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="post_deleted",
        tab="feed",
        title=f"Post deleted: {post_title[:50]}...",
        object_type="ForumPost"
    )


def log_comment_created(forum, performed_by, comment):
    """Log when a comment is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="comment_created",
        tab="feed",
        title=f"Comment added: {comment.content[:50]}...",
        description=comment.content,
        object_id=comment.id,
        object_type="PostComment"
    )


def log_meeting_created(forum, performed_by, meeting):
    """Log when a meeting is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="meeting_created",
        tab="meetings",
        title=f"Meeting scheduled: {meeting.title}",
        description=meeting.description or "",
        object_id=meeting.id,
        object_type="Meeting",
        metadata={
            "meeting_title": meeting.title,
            "scheduled_for": meeting.start_time.isoformat() if meeting.start_time else None
        }
    )


def log_payment_created(forum, performed_by, payment):
    """Log when a payment is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="payment_created",
        tab="payments",
        title=f"Payment created: {payment.name}",
        description=payment.description or "",
        object_id=payment.id,
        object_type="ForumPayment",
        metadata={
            "amount": str(payment.amount) if hasattr(payment, 'amount') else None
        }
    )


def log_member_joined(forum, performed_by, user):
    """Log when a member joins the forum"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="member_joined",
        tab="members",
        title=f"Member joined: {user.get_full_name()}",
        object_id=user.id,
        object_type="User"
    )


def log_member_role_changed(forum, performed_by, member, old_role, new_role):
    """Log when a member's role is changed"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="member_role_changed",
        tab="members",
        title=f"Role changed: {member.user.get_full_name()}",
        description=f"{old_role} → {new_role}",
        object_id=member.id,
        object_type="ForumMembership",
        metadata={
            "old_role": old_role,
            "new_role": new_role,
            "member_name": member.user.get_full_name()
        }
    )


def log_announcement_created(forum, performed_by, announcement):
    """Log when an announcement is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="announcement_created",
        tab="announcements",
        title=f"Announcement: {announcement.title}",
        description=announcement.content or "",
        object_id=announcement.id,
        object_type="Announcement"
    )


def log_poll_created(forum, performed_by, poll):
    """Log when a poll is created"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="poll_created",
        tab="polls",
        title=f"Poll created: {poll.question}",
        object_id=poll.id,
        object_type="Poll"
    )


def log_document_uploaded(forum, performed_by, document):
    """Log when a document is uploaded"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="document_uploaded",
        tab="about",
        title=f"Document uploaded: {document.title}",
        object_id=document.id,
        object_type="ForumDocument"
    )


def log_settings_changed(forum, performed_by, setting_name, old_value, new_value):
    """Log when forum settings are changed"""
    return log_activity(
        forum=forum,
        performed_by=performed_by,
        activity_type="settings_changed",
        tab="settings",
        title=f"Settings updated: {setting_name}",
        description=f"{old_value} → {new_value}",
        metadata={
            "setting_name": setting_name,
            "old_value": str(old_value),
            "new_value": str(new_value)
        }
    )
