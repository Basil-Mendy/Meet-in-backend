from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from forums.models import Forum, ForumVerificationRequest
from payments.models import ForumWallet, PaymentUserWallet, WalletService


class Command(BaseCommand):
    help = "Renew verified forums whose billing period has ended, or revoke them when funds are insufficient."

    def handle(self, *args, **options):
        now = timezone.now()
        renewed = 0
        revoked = 0

        for forum in Forum.objects.filter(is_verified=True, verification_expires_at__lte=now).iterator():
            request = forum.verification_requests.filter(status="APPROVED").select_related("plan").first()
            plan = request.plan if request else None
            fee = request.fee_amount if request else forum.verification_fee_amount
            duration_days = plan.duration_days if plan else 365

            with transaction.atomic():
                wallet = ForumWallet.objects.select_for_update().filter(forum=forum).first()
                if wallet and fee and wallet.balance >= fee:
                    admin_user = request.reviewed_by if request else None
                    if admin_user:
                        admin_wallet, _ = PaymentUserWallet.objects.get_or_create(user=admin_user)
                        WalletService.transfer_forum_to_user(
                            wallet, admin_wallet, fee,
                            reason="Forum verification renewal",
                            reference=f"VERIF-RENEW-{forum.id}-{now.date().isoformat()}",
                        )
                    forum.verification_expires_at = now + timedelta(days=duration_days)
                    forum.save(update_fields=["verification_expires_at"])
                    renewed += 1
                else:
                    forum.is_verified = False
                    forum.verification_expires_at = None
                    forum.save(update_fields=["is_verified", "verification_expires_at"])
                    revoked += 1

        self.stdout.write(self.style.SUCCESS(f"Renewed {renewed}; revoked {revoked} forum verifications."))