from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from forums.models import Forum, ForumMembership, UserNotificationPreference
from forums.notification_service import NotificationService


class Command(BaseCommand):
    help = 'Test notification system by creating a test post notification'

    def handle(self, *args, **options):
        try:
            # Get the first forum
            forum = Forum.objects.first()
            if not forum:
                self.stdout.write(self.style.ERROR("No forums found. Please create a forum first."))
                return

            # Get the first user (resolve actual user model)
            User = get_user_model()
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR("No users found. Please create a user first."))
                return

            self.stdout.write(f"Testing with Forum: {forum.name}")
            self.stdout.write(f"Testing with User: {user.email}")

            # Check notification preferences
            prefs, created = UserNotificationPreference.objects.get_or_create(user=user)
            self.stdout.write(f"Notification Preferences - Feed Push: {prefs.feed_push}, Feed Email: {prefs.feed_email}")

            # Create a test notification
            self.stdout.write("Creating test notification...")
            NotificationService.create_notification(
                forum=forum,
                user=user,
                notification_type='FEED_NEW_POST',
                title=f"Test notification for {forum.name}",
                message="This is a test notification message",
                tab='feed',
                send_push=True,
                send_email=True,
            )

            self.stdout.write(self.style.SUCCESS("✓ Test notification created successfully!"))
            self.stdout.write("Check your email and the browser console for the notification.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()
