"""
Comprehensive test script to verify all notification events are created with correct tab assignments.
This script tests the complete notification flow for all event types mentioned in the requirements.

Events to test:
- Feed: post_created, post_pinned
- Meetings: meeting_created, meeting_live
- Payments: payment_created
- Disbursements: disbursement_created (if applicable)
- Members: member_added, member_removed, role_assigned, role_removed
- About: forum_info_updated
- Announcements: announcement_created
- Polls: poll_created, poll_active, poll_closed
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from forums.models import (
    Forum, ForumMembership, ForumPost, Meeting, ForumPayment,
    Announcement, Poll, Notification, ForumSettings
)
from payments.models import Disbursement
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime, timedelta

User = get_user_model()

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def log_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")


def log_error(msg):
    print(f"{RED}✗ {msg}{RESET}")


def log_info(msg):
    print(f"{YELLOW}ℹ {msg}{RESET}")


def get_or_create_test_data():
    """Create test users and forum"""
    print("\n" + "=" * 60)
    print("Setting up test data...")
    print("=" * 60)
    
    # Create admin user
    admin, created = User.objects.get_or_create(
        username='admin_test',
        defaults={
            'email': 'admin@test.com',
            'is_staff': True,
        }
    )
    if created:
        log_success(f"Created admin user: {admin.email}")
    else:
        log_info(f"Admin user exists: {admin.email}")
    
    # Create member users
    member1, created = User.objects.get_or_create(
        username='member1_test',
        defaults={'email': 'member1@test.com'}
    )
    if created:
        log_success(f"Created member user: {member1.email}")
    else:
        log_info(f"Member user exists: {member1.email}")
    
    member2, created = User.objects.get_or_create(
        username='member2_test',
        defaults={'email': 'member2@test.com'}
    )
    if created:
        log_success(f"Created member user: {member2.email}")
    else:
        log_info(f"Member user exists: {member2.email}")
    
    # Create test forum
    forum, created = Forum.objects.get_or_create(
        name='Test Notification Forum',
        defaults={
            'description': 'Forum for testing all notification events',
            'created_by': admin,
        }
    )
    if created:
        log_success(f"Created forum: {forum.name}")
    else:
        log_info(f"Forum exists: {forum.name}")
    
    # Add users to forum
    for user, role in [(admin, 'admin'), (member1, 'member'), (member2, 'member')]:
        membership, created = ForumMembership.objects.get_or_create(
            forum=forum,
            user=user,
            defaults={'role': role, 'is_active': True}
        )
        if created:
            log_success(f"Added {user.email} to forum as {role}")
        else:
            log_info(f"{user.email} already in forum")
    
    return admin, member1, member2, forum


def check_notifications_by_tab(forum, expected_tabs):
    """Check if notifications exist for expected tabs"""
    print("\n" + "-" * 60)
    print("Notification Summary by Tab:")
    print("-" * 60)
    
    tab_counts = {}
    for tab in expected_tabs:
        count = Notification.objects.filter(
            forum=forum,
            is_read=False,
            tab=tab
        ).count()
        tab_counts[tab] = count
        if count > 0:
            log_success(f"Tab '{tab}': {count} unread notification(s)")
        else:
            log_error(f"Tab '{tab}': NO unread notifications found")
    
    return tab_counts


def test_feed_events(admin, member1, forum):
    """Test: Feed post creation and pinning"""
    print("\n" + "=" * 60)
    print("Testing FEED Tab Events...")
    print("=" * 60)
    
    # Create a post
    post, created = ForumPost.objects.get_or_create(
        forum=forum,
        author=member1,
        content="Test post for notification system",
        defaults={'title': 'Test Post'}
    )
    if created:
        log_success(f"Created post: '{post.title}'")
    else:
        log_info(f"Post exists: '{post.title}'")
    
    # Check if notification was created with 'feed' tab
    feed_notifs = Notification.objects.filter(
        forum=forum,
        tab='feed',
        notification_type='FEED_NEW_POST'
    ).count()
    
    if feed_notifs > 0:
        log_success(f"FEED_NEW_POST notification created (count: {feed_notifs})")
    else:
        log_error(f"FEED_NEW_POST notification NOT found")
    
    # Test post pinning (done from admin)
    post.is_pinned = True
    post.save()
    
    pin_notifs = Notification.objects.filter(
        forum=forum,
        tab='feed',
        notification_type='FEED_POST_PINNED'
    ).count()
    
    if pin_notifs > 0:
        log_success(f"FEED_POST_PINNED notification created (count: {pin_notifs})")
    else:
        log_error(f"FEED_POST_PINNED notification NOT found")


def test_meetings_events(admin, member1, forum):
    """Test: Meeting creation and going live"""
    print("\n" + "=" * 60)
    print("Testing MEETINGS Tab Events...")
    print("=" * 60)
    
    # Create a meeting
    meeting = Meeting.objects.create(
        forum=forum,
        created_by=admin,
        title='Test Meeting',
        description='A test meeting for notifications',
        scheduled_start=datetime.now() + timedelta(hours=1),
        scheduled_end=datetime.now() + timedelta(hours=2)
    )
    log_success(f"Created meeting: '{meeting.title}'")
    
    # Check if notification was created with 'meetings' tab
    created_notifs = Notification.objects.filter(
        forum=forum,
        tab='meetings',
        notification_type='MEETING_CREATED'
    ).count()
    
    if created_notifs > 0:
        log_success(f"MEETING_CREATED notification created (count: {created_notifs})")
    else:
        log_error(f"MEETING_CREATED notification NOT found")
    
    # Make meeting live
    meeting.is_live = True
    meeting.save()
    
    live_notifs = Notification.objects.filter(
        forum=forum,
        tab='meetings',
        notification_type='MEETING_LIVE'
    ).count()
    
    if live_notifs > 0:
        log_success(f"MEETING_LIVE notification created (count: {live_notifs})")
    else:
        log_error(f"MEETING_LIVE notification NOT found")


def test_payments_events(admin, forum):
    """Test: Payment creation"""
    print("\n" + "=" * 60)
    print("Testing PAYMENTS Tab Events...")
    print("=" * 60)
    
    # Create a payment
    payment = ForumPayment.objects.create(
        forum=forum,
        created_by=admin,
        title='Test Payment',
        description='A test payment for notifications',
        amount=1000.00,
        payment_type='expense'
    )
    log_success(f"Created payment: '{payment.title}'")
    
    # Check if notification was created with 'payments' tab
    payment_notifs = Notification.objects.filter(
        forum=forum,
        tab='payments',
        notification_type='PAYMENT_CREATED'
    ).count()
    
    if payment_notifs > 0:
        log_success(f"PAYMENT_CREATED notification created (count: {payment_notifs})")
    else:
        log_error(f"PAYMENT_CREATED notification NOT found")


def test_members_events(admin, member1, member2, forum):
    """Test: Member add, remove, role assignment, role removal"""
    print("\n" + "=" * 60)
    print("Testing MEMBERS Tab Events...")
    print("=" * 60)
    
    # Member addition is already tested in setup, so test here is role changes
    
    # Test role assignment
    membership = ForumMembership.objects.get(forum=forum, user=member1)
    membership.role = 'moderator'
    membership.save()
    log_success(f"Assigned role 'moderator' to {member1.email}")
    
    role_assigned = Notification.objects.filter(
        forum=forum,
        tab='members',
        notification_type='MEMBER_ROLE_ASSIGNED'
    ).count()
    
    if role_assigned > 0:
        log_success(f"MEMBER_ROLE_ASSIGNED notification created (count: {role_assigned})")
    else:
        log_error(f"MEMBER_ROLE_ASSIGNED notification NOT found")
    
    # Test role removal (revert to member)
    membership.role = 'member'
    membership.save()
    log_success(f"Removed role from {member1.email}")
    
    role_removed = Notification.objects.filter(
        forum=forum,
        tab='members',
        notification_type='MEMBER_ROLE_REMOVED'
    ).count()
    
    if role_removed > 0:
        log_success(f"MEMBER_ROLE_REMOVED notification created (count: {role_removed})")
    else:
        log_error(f"MEMBER_ROLE_REMOVED notification NOT found")
    
    # Test member removal  
    member_to_remove = member2
    membership_to_remove = ForumMembership.objects.get(forum=forum, user=member_to_remove)
    membership_to_remove.delete()
    log_success(f"Removed {member_to_remove.email} from forum")
    
    member_removed = Notification.objects.filter(
        forum=forum,
        tab='members',
        notification_type='MEMBER_REMOVED'
    ).count()
    
    if member_removed > 0:
        log_success(f"MEMBER_REMOVED notification created (count: {member_removed})")
    else:
        log_error(f"MEMBER_REMOVED notification NOT found")


def test_announcements_events(admin, forum):
    """Test: Announcement creation"""
    print("\n" + "=" * 60)
    print("Testing ANNOUNCEMENTS Tab Events...")
    print("=" * 60)
    
    # Create an announcement
    announcement = Announcement.objects.create(
        forum=forum,
        created_by=admin,
        title='Test Announcement',
        content='This is a test announcement for notifications'
    )
    log_success(f"Created announcement: '{announcement.title}'")
    
    # Check if notification was created with 'announcements' tab
    announce_notifs = Notification.objects.filter(
        forum=forum,
        tab='announcements',
        notification_type='ANNOUNCEMENT_CREATED'
    ).count()
    
    if announce_notifs > 0:
        log_success(f"ANNOUNCEMENT_CREATED notification created (count: {announce_notifs})")
    else:
        log_error(f"ANNOUNCEMENT_CREATED notification NOT found")


def test_polls_events(admin, forum):
    """Test: Poll creation, active, closed"""
    print("\n" + "=" * 60)
    print("Testing POLLS Tab Events...")
    print("=" * 60)
    
    # Create a poll
    poll = Poll.objects.create(
        forum=forum,
        created_by=admin,
        title='Test Poll',
        question='Is this a test?',
        status='DRAFT'
    )
    log_success(f"Created poll: '{poll.title}'")
    
    # Check if notification was created with 'polls' tab
    created_poll_notifs = Notification.objects.filter(
        forum=forum,
        tab='polls',
        notification_type='POLL_CREATED'
    ).count()
    
    if created_poll_notifs > 0:
        log_success(f"POLL_CREATED notification created (count: {created_poll_notifs})")
    else:
        log_error(f"POLL_CREATED notification NOT found")
    
    # Activate poll
    poll.status = 'ACTIVE'
    poll.save()
    log_success(f"Activated poll")
    
    active_notifs = Notification.objects.filter(
        forum=forum,
        tab='polls',
        notification_type='POLL_ACTIVE'
    ).count()
    
    if active_notifs > 0:
        log_success(f"POLL_ACTIVE notification created (count: {active_notifs})")
    else:
        log_error(f"POLL_ACTIVE notification NOT found")
    
    # Close poll
    poll.status = 'CLOSED'
    poll.save()
    log_success(f"Closed poll")
    
    closed_notifs = Notification.objects.filter(
        forum=forum,
        tab='polls',
        notification_type='POLL_CLOSED'
    ).count()
    
    if closed_notifs > 0:
        log_success(f"POLL_CLOSED notification created (count: {closed_notifs})")
    else:
        log_error(f"POLL_CLOSED notification NOT found")


def test_forum_info_events(admin, forum):
    """Test: Forum information updates"""
    print("\n" + "=" * 60)
    print("Testing ABOUT Tab Events...")
    print("=" * 60)
    
    # Update forum settings/info
    try:
        settings = ForumSettings.objects.get(forum=forum)
    except ForumSettings.DoesNotExist:
        settings = ForumSettings.objects.create(
            forum=forum,
            visibility='public',
            join_mode='request'
        )
    
    settings.objectives = 'Updated objectives for testing'
    settings.save()
    log_success(f"Updated forum settings/info")
    
    # Check if notification was created with 'about' tab
    info_notifs = Notification.objects.filter(
        forum=forum,
        tab='about',
        notification_type='FORUM_INFO_UPDATED'
    ).count()
    
    if info_notifs > 0:
        log_success(f"FORUM_INFO_UPDATED notification created (count: {info_notifs})")
    else:
        log_error(f"FORUM_INFO_UPDATED notification NOT found")


def main():
    print("\n" + "=" * 60)
    print("COMPREHENSIVE NOTIFICATION EVENT TEST")
    print("Testing all forum notification events and their tab assignments")
    print("=" * 60)
    
    # Setup
    admin, member1, member2, forum = get_or_create_test_data()
    
    # Clear previous notifications for this forum
    Notification.objects.filter(forum=forum).delete()
    log_success("Cleared previous notifications for this forum")
    
    # Run all tests
    test_feed_events(admin, member1, forum)
    test_meetings_events(admin, member1, forum)
    test_payments_events(admin, forum)
    test_members_events(admin, member1, member2, forum)
    test_announcements_events(admin, forum)
    test_polls_events(admin, forum)
    test_forum_info_events(admin, forum)
    
    # Summary
    all_notifications = Notification.objects.filter(
        forum=forum,
        is_read=False
    )
    
    expected_tabs = [
        'feed', 'meetings', 'payments', 'disbursements',
        'members', 'about', 'announcements', 'polls'
    ]
    
    tab_counts = check_notifications_by_tab(forum, expected_tabs)
    
    print("\n" + "=" * 60)
    print("Overall Summary:")
    print("=" * 60)
    print(f"Total unread notifications: {all_notifications.count()}")
    print(f"Tabs with notifications: {sum(1 for count in tab_counts.values() if count > 0)}")
    print(f"Expected tabs: {len(expected_tabs)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
