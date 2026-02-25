from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (
    Forum, ForumMembership, MemberActivity, ProfileRing,
    ForumInvitationCode, ForumPost, PostReaction, PostComment, PostCommentReply,
    MeetingParticipant, ForumPaymentSubmission, PollVote, Meeting, Announcement, Poll, ForumSettings,
    ForumJoinRequest
)
from payments.models import ForumWallet, ForumPayment, Disbursement
from .notification_service import NotificationService
from .activity_service import record_event
import random
import string


def get_user_display_name(user):
    """Get user's full name or fallback to username"""
    if hasattr(user, 'get_full_name') and callable(user.get_full_name):
        full_name = user.get_full_name()
        if full_name:
            return full_name
    # Fallback: try first_name + last_name
    if hasattr(user, 'first_name') and hasattr(user, 'last_name'):
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            return full_name
    # Final fallback: username
    return user.username or "Unknown User"


# ==================== TRACKING HELPERS ====================

# Track state changes for detecting transitions
_post_pinned_states = {}
_meeting_live_states = {}
_poll_active_states = {}
_forum_settings_changes = {}
_meeting_participant_present_states = {}


def generate_forum_id():
    """Generate a unique forum ID"""
    while True:
        forum_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Forum.objects.filter(forum_id=forum_id).exists():
            return forum_id


def generate_invitation_code():
    """Generate a unique invitation code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        if not ForumInvitationCode.objects.filter(code=code).exists():
            return code


@receiver(post_save, sender=Forum)
def create_forum_wallet_and_ids(sender, instance, created, **kwargs):
    if created:
        # Generate unique forum ID if not set
        if not instance.forum_id:
            instance.forum_id = generate_forum_id()
            instance.save()
        
        # Create forum wallet


@receiver(post_save, sender=ForumMembership)
def create_member_activity_and_ring(sender, instance, created, **kwargs):
    if created:
        MemberActivity.objects.create(membership=instance)
        ProfileRing.objects.create(membership=instance)


# ==================== NOTIFICATION SIGNALS ====================

@receiver(post_save, sender=ForumPost)
def notify_new_post(sender, instance, created, **kwargs):
    """Notify forum members when a new post is created"""
    if created:
        try:
            # Create notifications with both push and email enabled for feed posts
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='FEED_NEW_POST',
                title=f"New post in {instance.forum.name}",
                message=f"{get_user_display_name(instance.author)} posted: \"{instance.content[:50]}...\"",
                tab='feed',
                object_id=str(instance.id),
                excluded_users=[instance.author],
                send_push=True,  # Ensure push notification is sent
                send_email=True,  # Ensure email notification is sent
            )
            # Update activity: +5 for post created
            try:
                record_event(instance.author, instance.forum, 'post_created')
            except Exception:
                pass
        except Exception as e:
            print(f"Error creating post notification: {e}")
            import traceback
            traceback.print_exc()


@receiver(post_save, sender=ForumPayment)
def notify_payment_created(sender, instance, created, **kwargs):
    """Notify members when payment is created"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='PAYMENT_CREATED',
                title=f"New payment in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} created a payment for '{instance.title or 'Payment'}'",
                tab='payments',
                object_id=str(instance.id),
                excluded_users=[instance.created_by] if hasattr(instance, 'created_by') else [],
                send_push=True,
                send_email=True,
            )
    except Exception as e:
        print(f"Error creating payment notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=PostReaction)
def notify_reaction_created(sender, instance, created, **kwargs):
    """Notify post author and record reaction activity"""
    try:
        if created:
            # notify post author
            NotificationService.create_forum_notifications(
                forum=instance.post.forum,
                notification_type='POST_REACTION',
                title=f"New reaction in {instance.post.forum.name}",
                message=f"{get_user_display_name(instance.user)} reacted to your post",
                tab='feed',
                object_id=str(instance.post.id),
                excluded_users=[instance.user],
                include_users=[instance.post.author],
                send_push=True,
                send_email=False,
            )
            try:
                record_event(instance.user, instance.post.forum, 'reaction_given')
            except Exception:
                pass
    except Exception as e:
        print(f"Error creating reaction notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=PostComment)
def notify_comment_created(sender, instance, created, **kwargs):
    """Notify post author and record comment activity"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.post.forum,
                notification_type='POST_COMMENT',
                title=f"New comment in {instance.post.forum.name}",
                message=f"{get_user_display_name(instance.author)} commented: \"{instance.content[:50]}...\"",
                tab='feed',
                object_id=str(instance.post.id),
                excluded_users=[instance.author],
                include_users=[instance.post.author],
                send_push=True,
                send_email=False,
            )
            try:
                record_event(instance.author, instance.post.forum, 'comment_created')
            except Exception:
                pass
    except Exception as e:
        print(f"Error creating comment notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=PostCommentReply)
def notify_reply_created(sender, instance, created, **kwargs):
    """Notify comment author and record reply activity"""
    try:
        if created:
            parent_comment = instance.comment
            NotificationService.create_forum_notifications(
                forum=parent_comment.post.forum,
                notification_type='COMMENT_REPLY',
                title=f"New reply in {parent_comment.post.forum.name}",
                message=f"{get_user_display_name(instance.author)} replied: \"{instance.content[:50]}...\"",
                tab='feed',
                object_id=str(parent_comment.post.id),
                excluded_users=[instance.author],
                include_users=[parent_comment.author],
                send_push=True,
                send_email=False,
            )
            try:
                record_event(instance.author, parent_comment.post.forum, 'reply_created')
            except Exception:
                pass
    except Exception as e:
        print(f"Error creating reply notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=PollVote)
def notify_poll_vote_created(sender, instance, created, **kwargs):
    """Record poll vote activity"""
    try:
        if created:
            forum = instance.poll.forum
            try:
                voter = instance.voter or instance.user
            except Exception:
                voter = None
            if voter:
                try:
                    record_event(voter, forum, 'poll_voted')
                except Exception:
                    pass
    except Exception as e:
        print(f"Error recording poll vote activity: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=ForumPaymentSubmission)
def notify_payment_submission(sender, instance, created, **kwargs):
    """Record payment submission activity and notify if needed"""
    try:
        if created:
            try:
                record_event(instance.user, instance.payment.forum, 'payment_made')
            except Exception:
                pass
    except Exception as e:
        print(f"Error recording payment submission activity: {e}")
        import traceback
        traceback.print_exc()


@receiver(pre_save, sender=MeetingParticipant)
def capture_meeting_participant_present_before(sender, instance, **kwargs):
    try:
        if instance.pk:
            old = MeetingParticipant.objects.get(pk=instance.pk)
            _meeting_participant_present_states[instance.pk] = old.is_marked_present
    except MeetingParticipant.DoesNotExist:
        pass


@receiver(post_save, sender=MeetingParticipant)
def notify_meeting_participation(sender, instance, created, **kwargs):
    """When a participant is marked present, record attendance activity"""
    try:
        old_state = _meeting_participant_present_states.pop(instance.pk, False)
        if instance.is_marked_present and not old_state:
            try:
                record_event(instance.user, instance.meeting.forum, 'meeting_attended')
            except Exception:
                pass
    except Exception as e:
        print(f"Error recording meeting participation: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=Disbursement)
def notify_disbursement_created(sender, instance, created, **kwargs):
    """Notify members involved when disbursement is made"""
    try:
        if created:
            # Get users involved in this disbursement
            involved_users = []
            if hasattr(instance, 'transactions') and hasattr(instance.transactions, 'all'):
                # Collect unique users from disbursement transactions
                for transaction in instance.transactions.all():
                    if hasattr(transaction, 'user') and transaction.user:
                        involved_users.append(transaction.user)
            
            # Notify involved members
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='DISBURSEMENT_CREATED',
                title=f"Disbursement in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} created a disbursement for '{instance.title or 'Disbursement'}'",
                tab='disbursements',
                object_id=str(instance.id),
                include_users=involved_users if involved_users else None,  # Notify all if no specific users
                send_push=True,
                send_email=True,
            )
    except Exception as e:
        print(f"Error creating disbursement notification: {e}")
        import traceback
        traceback.print_exc()


# Pin state tracking and signal-level pin notifications removed.
# Pin notifications are created from the view to include actor info
# and to avoid duplicate notifications.


@receiver(pre_save, sender=Meeting)
def capture_meeting_live_state_before(sender, instance, **kwargs):
    """Capture is_live state before save to detect changes"""
    try:
        if instance.pk:
            old_instance = Meeting.objects.get(pk=instance.pk)
            _meeting_live_states[instance.pk] = old_instance.is_live
    except Meeting.DoesNotExist:
        pass


@receiver(post_save, sender=Meeting)
def notify_meeting_created_and_live(sender, instance, created, **kwargs):
    """Notify members when meeting is created or goes live"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='MEETING_CREATED',
                title=f"New meeting in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} created a meeting: \"{instance.title}\" on {instance.scheduled_start.strftime('%Y-%m-%d %H:%M')}",
                tab='meetings',
                object_id=str(instance.id),
                excluded_users=[instance.created_by],
                send_push=True,
                send_email=True,
            )
        else:
            # Check if meeting transitioned to live state
            old_state = _meeting_live_states.pop(instance.pk, False)
            if not old_state and instance.is_live:
                NotificationService.create_forum_notifications(
                    forum=instance.forum,
                    notification_type='MEETING_LIVE',
                    title=f"Live meeting in {instance.forum.name}",
                    message=f"Meeting \"{instance.title}\" is now live",
                    tab='meetings',
                    object_id=str(instance.id),
                    send_push=True,
                    send_email=True,
                )
    except Exception as e:
        print(f"Error creating meeting notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=Announcement)
def notify_announcement_created(sender, instance, created, **kwargs):
    """Notify members when new announcement is made"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='ANNOUNCEMENT_CREATED',
                title=f"Announcement in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} posted an announcement: \"{instance.title}\"",
                tab='announcements',
                object_id=str(instance.id),
                excluded_users=[instance.created_by],
                send_push=True,
                send_email=True,
            )
    except Exception as e:
        print(f"Error creating announcement notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(pre_save, sender=Poll)
def capture_poll_active_state_before(sender, instance, **kwargs):
    """Capture poll status before save to detect state transitions"""
    try:
        if instance.pk:
            old_instance = Poll.objects.get(pk=instance.pk)
            _poll_active_states[instance.pk] = {
                'old_status': old_instance.status,
                'old_start_time': old_instance.start_time,
                'old_end_time': old_instance.end_time,
            }
    except Poll.DoesNotExist:
        pass


@receiver(post_save, sender=Poll)
def notify_poll_created_and_active(sender, instance, created, **kwargs):
    """Notify members when poll is created, becomes active, or closes"""
    try:
        poll_title = instance.title or instance.question
        
        if created:
            poll_type = "a group poll" if instance.group else "a standalone poll"
            start_str = instance.start_time.strftime('%Y-%m-%d') if instance.start_time else 'TBD'
            end_str = instance.end_time.strftime('%Y-%m-%d') if instance.end_time else 'TBD'
            
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='POLL_CREATED',
                title=f"New poll in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} created {poll_type}: \"{poll_title}\" (start: {start_str}, end: {end_str})",
                tab='polls',
                object_id=str(instance.id),
                excluded_users=[instance.created_by],
                send_push=True,
                send_email=True,
            )
        else:
            # Check if poll status changed to ACTIVE or CLOSED
            old_state = _poll_active_states.pop(instance.pk, {})
            old_status = old_state.get('old_status')
            
            if old_status != 'ACTIVE' and instance.status == 'ACTIVE':
                poll_context = f"'{instance.group.title}'" if instance.group else f"'{poll_title}'"
                NotificationService.create_forum_notifications(
                    forum=instance.forum,
                    notification_type='POLL_ACTIVE',
                    title=f"Poll active in {instance.forum.name}",
                    message=f"Voting is now active for {poll_context}",
                    tab='polls',
                    object_id=str(instance.id),
                    send_push=True,
                    send_email=True,
                )
            elif old_status != 'CLOSED' and instance.status == 'CLOSED':
                # Notify when poll closes
                poll_context = f"'{instance.group.title}'" if instance.group else f"'{poll_title}'"
                NotificationService.create_forum_notifications(
                    forum=instance.forum,
                    notification_type='POLL_CLOSED',
                    title=f"Poll closed in {instance.forum.name}",
                    message=f"Voting has closed for {poll_context}",
                    tab='polls',
                    object_id=str(instance.id),
                    send_push=True,
                    send_email=True,
                )
    except Exception as e:
        print(f"Error creating poll notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=ForumMembership)
def notify_member_events(sender, instance, created, **kwargs):
    """Notify members when new member joins or member role changes"""
    try:
        if created:
            # New member accepted into forum
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='MEMBER_ADDED',
                title=f"New member in {instance.forum.name}",
                message=f"{get_user_display_name(instance.user)} has been accepted into the forum",
                tab='members',
                object_id=str(instance.user.id),
                excluded_users=[instance.user],
                send_push=True,
                send_email=True,
            )
        else:
            # Member role change - check if role was updated
            try:
                old_instance = ForumMembership.objects.filter(pk=instance.pk).first()
                if old_instance and old_instance.role != instance.role:
                    # Determine if it's a role assignment or removal
                    new_role = instance.role or 'member'
                    old_role = old_instance.role or 'member'
                    
                    # If changing FROM a special role TO member, it's a removal
                    if old_role != 'member' and new_role == 'member':
                        NotificationService.create_forum_notifications(
                            forum=instance.forum,
                            notification_type='MEMBER_ROLE_REMOVED',
                            title=f"Role removed in {instance.forum.name}",
                            message=f"The '{old_role}' role has been removed from {get_user_display_name(instance.user)}",
                            tab='members',
                            object_id=str(instance.user.id),
                            send_push=True,
                            send_email=True,
                        )
                    else:
                        # Role assignment
                        NotificationService.create_forum_notifications(
                            forum=instance.forum,
                            notification_type='MEMBER_ROLE_ASSIGNED',
                            title=f"Role assignment in {instance.forum.name}",
                            message=f"{get_user_display_name(instance.user)} was assigned the role of '{instance.get_role_display()}'",
                            tab='members',
                            object_id=str(instance.user.id),
                            send_push=True,
                            send_email=True,
                        )
            except ForumMembership.DoesNotExist:
                pass
    except Exception as e:
        print(f"Error creating member notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_delete, sender=ForumMembership)
def notify_member_removed(sender, instance, **kwargs):
    """Notify members when a member is removed from forum"""
    try:
        NotificationService.create_forum_notifications(
            forum=instance.forum,
            notification_type='MEMBER_REMOVED',
            title=f"Member removed from {instance.forum.name}",
            message=f"{get_user_display_name(instance.user)} has been removed from the forum",
            tab='members',
            object_id=str(instance.user.id),
            send_push=True,
            send_email=True,
        )
    except Exception as e:
        print(f"Error creating member removed notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(pre_save, sender=ForumSettings)
def capture_forum_settings_changes(sender, instance, **kwargs):
    """Capture forum settings before save to detect updates"""
    try:
        if instance.pk:
            old_instance = ForumSettings.objects.get(pk=instance.pk)
            changed_fields = []
            
            if old_instance.visibility != instance.visibility:
                changed_fields.append('visibility')
            if old_instance.join_mode != instance.join_mode:
                changed_fields.append('join mode')
            if old_instance.payment_rules != instance.payment_rules:
                changed_fields.append('payment rules')
            if old_instance.rules_regulations != instance.rules_regulations:
                changed_fields.append('forum rules')
            if old_instance.objectives != instance.objectives:
                changed_fields.append('objectives')
            
            if changed_fields:
                _forum_settings_changes[instance.pk] = changed_fields
    except ForumSettings.DoesNotExist:
        pass


@receiver(post_save, sender=ForumSettings)
def notify_forum_info_updated(sender, instance, created, **kwargs):
    """Notify members when forum information is updated"""
    if not created:
        try:
            changed_fields = _forum_settings_changes.pop(instance.pk, [])
            
            if changed_fields:
                fields_str = ", ".join(changed_fields)
                # Get the user who made the change (if available in request context)
                # For now, we'll use a generic message
                NotificationService.create_forum_notifications(
                    forum=instance.forum,
                    notification_type='FORUM_INFO_UPDATED',
                    title=f"Forum information updated",
                    message=f"The following forum information was updated: {fields_str}",
                    tab='about',
                    object_id=str(instance.forum.id),
                    send_push=True,
                    send_email=True,
                )
        except Exception as e:
            print(f"Error creating forum info update notification: {e}")
            import traceback
            traceback.print_exc()


# ============================================================================
# ForumJoinRequest Signals - Handle join request lifecycle
# ============================================================================

@receiver(post_save, sender=ForumJoinRequest)
def handle_forum_join_request_created(sender, instance, created, **kwargs):
    """
    When a user submits a join request, notify all forum admins/moderators
    """
    if not created or instance.status != "PENDING":
        return

    try:
        user = instance.user
        forum = instance.forum
        
        # Get all admins and moderators for this forum
        admin_members = ForumMembership.objects.filter(
            forum=forum,
            role__in=['admin', 'moderator']
        ).exclude(user=user)
        
        for membership in admin_members:
            NotificationService.create_notification(
                user=membership.user,
                forum=forum,
                notification_type='FORUM_JOIN_REQUEST_PENDING',
                title=f"Join request in {forum.name}",
                message=f"{get_user_display_name(user)} is requesting to join the forum",
                tab='settings',
                object_id=str(instance.id),
                send_push=True,
                send_email=True,
            )
    except Exception as e:
        print(f"Error notifying admins of join request: {e}")
        import traceback
        traceback.print_exc()


@receiver(pre_save, sender=ForumJoinRequest)
def handle_forum_join_request_reviewed(sender, instance, **kwargs):
    """
    When a join request is approved or rejected, notify the requesting user
    and clear pending notifications
    """
    try:
        # Get previous state
        previous = ForumJoinRequest.objects.filter(pk=instance.pk).first()
        if not previous:
            return
        
        # Check if status changed
        if previous.status == instance.status:
            return
        
        user = instance.user
        forum = instance.forum
        
        if instance.status == "APPROVED":
            # Notify user of approval
            NotificationService.create_notification(
                user=user,
                forum=forum,
                notification_type='FORUM_JOIN_REQUEST_APPROVED',
                title=f"Join request approved in {forum.name}",
                message=f"Your request to join {forum.name} has been approved",
                tab='settings',
                object_id=str(instance.id),
                send_push=True,
                send_email=True,
            )
        elif instance.status == "REJECTED":
            # Notify user of rejection
            NotificationService.create_notification(
                user=user,
                forum=forum,
                notification_type='FORUM_JOIN_REQUEST_REJECTED',
                title=f"Join request rejected in {forum.name}",
                message=f"Your request to join {forum.name} has been rejected",
                tab='settings',
                object_id=str(instance.id),
                send_push=True,
                send_email=True,
            )
            
    except Exception as e:
        print(f"Error handling join request review: {e}")
        import traceback
        traceback.print_exc()


