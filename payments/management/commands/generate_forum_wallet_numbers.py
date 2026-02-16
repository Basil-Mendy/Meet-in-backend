from django.core.management.base import BaseCommand
from django.db.models import Q

from payments.models import ForumWallet


class Command(BaseCommand):
    help = (
        "Generate wallet numbers for existing ForumWallet records that lack one.\n"
        "Usage: python manage.py generate_forum_wallet_numbers [--force]"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing wallet_number values",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        if force:
            qs = ForumWallet.objects.all()
        else:
            qs = ForumWallet.objects.filter(Q(wallet_number__isnull=True) | Q(wallet_number=""))

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No forum wallets require provisioning."))
            return

        self.stdout.write(f"Provisioning wallet numbers for {total} forum wallets...")

        updated = 0
        for w in qs:
            # Use wallet UUID as the stable base for wallet number
            candidate = f"FW{w.id.hex[:12].upper()}"
            # If force and candidate collides (very unlikely), append short uuid
            if ForumWallet.objects.filter(wallet_number=candidate).exclude(pk=w.pk).exists():
                import uuid

                candidate = f"FW{uuid.uuid4().hex[:12].upper()}"

            w.wallet_number = candidate
            w.save(update_fields=["wallet_number"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Provisioned wallet numbers for {updated} forum wallets."))
