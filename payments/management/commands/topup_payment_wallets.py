from django.core.management.base import BaseCommand
from decimal import Decimal
from django.contrib.auth import get_user_model
from payments.models import PaymentUserWallet

class Command(BaseCommand):
    help = 'Top up all PaymentUserWallet balances by a specified amount (development only)'

    def add_arguments(self, parser):
        parser.add_argument('--amount', type=str, default='10000.00', help='Amount to add to each user wallet')

    def handle(self, *args, **options):
        amount = Decimal(options['amount'])
        User = get_user_model()
        count = 0
        for u in User.objects.all():
            w, _ = PaymentUserWallet.objects.get_or_create(user=u)
            w.balance = w.balance + amount
            w.save()
            self.stdout.write(f"{u.id} -> {w.balance}")
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Topped up {count} wallets by {amount}"))
