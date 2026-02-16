from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (
    Forum, ForumMembership, MemberActivity, ProfileRing, 
    ForumInvitationCode, ForumPost, Meeting, Announcement, Poll, ForumSettings
)
from payments.models import ForumWallet, ForumPayment, Disbursement
from .notification_service import NotificationService
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
        except Exception as e:
            print(f"Error creating post notification: {e}")
            import traceback
            traceback.print_exc()


@receiver(post_save, sender=Meeting)
def notify_meeting_events(sender, instance, created, **kwargs):
    """Notify members when meeting is created or goes live"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='MEETING_CREATED',
                title=f"New meeting in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)} created meeting: \"{instance.title}\"",
                tab='meetings',
                object_id=str(instance.id),
                excluded_users=[instance.created_by],
            )
        elif instance.is_live and not kwargs.get('force_insert'):
            # Meeting went live (not first creation)
            # Check if this is a state change by comparing with old value
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='MEETING_LIVE',
                title=f"Meeting is live in {instance.forum.name}",
                message=f"Meeting \"{instance.title}\" is now live",
                tab='meetings',
                object_id=str(instance.id),
            )
    except Exception as e:
        print(f"Error creating meeting notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=Announcement)
def notify_new_announcement(sender, instance, created, **kwargs):
    """Notify members when new announcement is made"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='ANNOUNCEMENT_CREATED',
                title=f"New announcement in {instance.forum.name}",
                message=f"{get_user_display_name(instance.created_by)}: \"{instance.title}\"",
                tab='announcements',
                object_id=str(instance.id),
                excluded_users=[instance.created_by],
            )
    except Exception as e:
        print(f"Error creating announcement notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=Poll)
def notify_poll_events(sender, instance, created, **kwargs):
    """Notify members when poll is created"""
    try:
        if created:
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='POLL_CREATED',
                title=f"New poll in {instance.forum.name}",
                message=f"Poll: {instance.question}",
                tab='polls',
                object_id=str(instance.id),
                excluded_users=[instance.created_by] if hasattr(instance, 'created_by') else [],
            )
    except Exception as e:
        print(f"Error creating poll notification: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=ForumMembership)
def notify_member_added(sender, instance, created, **kwargs):
    """Notify forum members when new member joins"""
    try:
        if created:
            # Notify OTHER members about new member
            NotificationService.create_forum_notifications(
                forum=instance.forum,
                notification_type='MEMBER_ADDED',
                title=f"New member in {instance.forum.name}",
                message=f"{get_user_display_name(instance.user)} has joined the forum",
                tab='members',
                object_id=str(instance.user.id),
                excluded_users=[instance.user],
            )
    except Exception as e:
        print(f"Error creating member notification: {e}")
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
    """Notify members when poll is created or becomes active"""
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
            # Check if poll status changed to ACTIVE
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
                old_instance = ForumMembership.objects.get(pk=instance.pk)
                if old_instance.role != instance.role:
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

