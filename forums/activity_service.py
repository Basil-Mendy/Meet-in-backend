from django.utils import timezone
from django.db import transaction
from .models import ForumMembership, MemberActivity
from django.shortcuts import get_object_or_404

# Points mapping
EVENT_POINTS = {
    'post_created': 5,
    'comment_created': 2,
    'reaction_created': 1,
    'meeting_attended': 8,
    'meeting_missed': -2,
    'payment_paid': 6,
    'payment_late': 2,
    'payment_failed': -8,
    'poll_voted': 4,
    'poll_missed': -1,
    'daily_open': 1,
}

# Recency multipliers
def recency_multiplier(last_activity_at):
    if not last_activity_at:
        return 0.6
    delta = timezone.now() - last_activity_at
    days = delta.days
    if days <= 7:
        return 1.2
    if days <= 30:
        return 1.0
    return 0.6

# Ring thresholds
RING_THRESHOLDS = [
    (0, 19, 'Dormant', '#9CA3AF'),
    (20, 49, 'Passive', '#3B82F6'),
    (50, 99, 'Active', '#22C55E'),
    (100, 199, 'Very Active', '#8B5CF6'),
    (200, 10**9, 'Elite', '#F59E0B'),
]


def compute_ring(score):
    for low, high, name, color in RING_THRESHOLDS:
        if low <= score <= high:
            return name, color
    return 'Dormant', '#9CA3AF'


@transaction.atomic
def get_or_create_activity(user, forum):
    # Get membership then activity
    membership = ForumMembership.objects.filter(user=user, forum=forum).first()
    if not membership:
        # If there's no membership, nothing to track
        return None
    activity, created = MemberActivity.objects.get_or_create(membership=membership)
    return activity


@transaction.atomic
def record_event(user, forum, event_type, metadata=None):
    """Record an event and update activity counters and score."""
    metadata = metadata or {}
    activity = get_or_create_activity(user, forum)
    if not activity:
        return None

    points = EVENT_POINTS.get(event_type, 0)

    # Update counters based on event
    if event_type == 'post_created':
        activity.posts_count += 1
    elif event_type == 'comment_created':
        activity.comments_count += 1
    elif event_type == 'reaction_created':
        activity.reactions_count += 1
    elif event_type == 'meeting_attended':
        activity.meetings_attended += 1
    elif event_type in ('payment_paid', 'payment_late'):
        activity.payments_paid += 1
    elif event_type == 'poll_voted':
        activity.polls_participated += 1
    elif event_type == 'daily_open':
        # handle daily open specially in record_daily_open
        pass

    # Apply points and recency multiplier
    activity.activity_score = (activity.activity_score + points)
    activity.last_activity_at = timezone.now()
    activity.last_calculated_at = timezone.now()

    # Recalculate ring
    ring_name, ring_color = compute_ring(activity.activity_score)
    activity.ring_level = ring_name
    activity.ring_color = ring_color

    activity.save()
    return activity


@transaction.atomic
def record_daily_open(user, forum):
    activity = get_or_create_activity(user, forum)
    if not activity:
        return None

    today = timezone.localdate()
    # Prevent double counting
    if activity.last_open_date == today:
        return activity

    # Increment forum_open_days and score
    activity.forum_open_days = (activity.forum_open_days or 0) + 1
    activity.last_open_date = today
    points = EVENT_POINTS.get('daily_open', 1)
    activity.activity_score = (activity.activity_score or 0) + points
    activity.last_activity_at = timezone.now()
    activity.last_calculated_at = timezone.now()

    # Recalculate ring
    ring_name, ring_color = compute_ring(activity.activity_score)
    activity.ring_level = ring_name
    activity.ring_color = ring_color

    activity.save()
    return activity


@transaction.atomic
def recalculate_activity(activity):
    # Placeholder for more advanced recalculation, decay, etc.
    if not activity:
        return None
    multiplier = recency_multiplier(activity.last_activity_at)
    activity.activity_score = activity.activity_score * multiplier
    activity.last_calculated_at = timezone.now()
    ring_name, ring_color = compute_ring(activity.activity_score)
    activity.ring_level = ring_name
    activity.ring_color = ring_color
    activity.save()
    return activity
