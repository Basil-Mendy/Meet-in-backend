from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Profile
from wallet.models import Wallet
from payments.models import PaymentUserWallet
from forums.models import UserNotificationPreference


@receiver(post_save, sender=User)
def create_profile_and_wallet(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        Wallet.objects.create(user=instance)
        PaymentUserWallet.objects.create(user=instance)
        # Create default notification preferences for the user
        UserNotificationPreference.objects.create(
            user=instance,
            feed_push=True,
            feed_email=True,
            meetings_push=True,
            meetings_email=True,
            announcements_push=True,
            announcements_email=True,
        )
