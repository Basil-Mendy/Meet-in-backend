import uuid
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from forums.models import Forum, ForumMembership

User = settings.AUTH_USER_MODEL


class ForumWallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.OneToOneField(Forum, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    # Optional wallet number that may be issued by us or a partner financial institution
    wallet_number = models.CharField(max_length=64, null=True, blank=True, unique=False)
    updated_at = models.DateTimeField(auto_now=True)


class PaymentUserWallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="payment_wallet")
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    # Optional wallet number for user wallets (human/bank-friendly identifier)
    wallet_number = models.CharField(max_length=64, null=True, blank=True, unique=False)
    updated_at = models.DateTimeField(auto_now=True)


class WalletTransaction(models.Model):
    """
    A record of a movement between wallets. Exactly one source and one destination
    wallet must be set (forum or user).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    source_user_wallet = models.ForeignKey(PaymentUserWallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_transactions")
    source_forum_wallet = models.ForeignKey(ForumWallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_transactions")

    dest_user_wallet = models.ForeignKey(PaymentUserWallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_transactions")
    dest_forum_wallet = models.ForeignKey(ForumWallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_transactions")

    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=200, blank=True)
    reason = models.CharField(max_length=100)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="wallet_transactions", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Ensure exactly one source and one destination is provided
        sources = [bool(self.source_user_wallet), bool(self.source_forum_wallet)]
        dests = [bool(self.dest_user_wallet), bool(self.dest_forum_wallet)]
        if sum(sources) != 1 or sum(dests) != 1:
            raise ValidationError("Must provide exactly one source wallet and one destination wallet")
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be positive")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ForumPayment(models.Model):
    PAYMENT_TYPES = [
        ("DUES", "Dues"),
        ("CONTRIBUTION", "Contribution"),
        ("LEVY", "Levy"),
    ]
    LEVY_BASIS_CHOICES = [
        ("GENDER", "Gender Based"),
        ("AGE", "Age Based"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="payments")
    title = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="DUES")
    levy_basis = models.CharField(max_length=20, choices=LEVY_BASIS_CHOICES, default="GENDER")

    # Common fields
    deadline = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # Dues: fixed amount
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # Contribution: min and optional max
    min_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # Levy: categories defined in PaymentCategory
    # Disbursement: handled by Disbursement model

    def __str__(self):
        return f"{self.forum} - {self.title} ({self.type})"

    def member_amount_for(self, user):
        return assign_member_amount(self, user)


class PaymentCategory(models.Model):
    CATEGORY_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("below_18", "Below 18"),
        ("age_18_plus", "18 and above"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(ForumPayment, on_delete=models.CASCADE, related_name="categories")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("payment", "category")


class MemberPayment(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(ForumPayment, on_delete=models.CASCADE, related_name="member_payments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    amount_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("payment", "user")


class Disbursement(models.Model):
    DISBURSEMENT_TYPES = [
        ("PAY_ALL", "Pay to All Members (with Categories)"),
        ("PAY_SELECTED", "Pay to Selected Members"),
        ("PAY_TO_ALL", "Pay to All Members (Fixed Amount)"),
    ]
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESSFUL", "Successful"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="disbursements")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=150, default="Disbursement")
    type = models.CharField(max_length=20, choices=DISBURSEMENT_TYPES, default="PAY_ALL")
    disbursement_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # For PAY_TO_ALL type
    selected_members = models.ManyToManyField(User, related_name="selected_disbursements", blank=True)

    # Approval workflow fields for disbursements
    president_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="president_approved_disbursements",
    )
    president_approved_at = models.DateTimeField(null=True, blank=True)
    secretary_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secretary_approved_disbursements",
    )
    secretary_approved_at = models.DateTimeField(null=True, blank=True)

    # For PAY_ALL with categories: categories will be in DisbursementCategory
    # For PAY_SELECTED: selected_members will be stored here
    # For PAY_TO_ALL: amount field is used, all members are automatically selected

    ROLE_LABEL_MAP = {
        "P": "President",
        "SEC": "Secretary",
    }

    def __str__(self):
        return f"{self.forum} - {self.title} ({self.type})"

    def required_approval_roles(self):
        roles = ForumMembership.objects.filter(
            forum=self.forum,
            role__in=("P", "SEC"),
            is_active=True,
        ).values_list("role", flat=True)
        return set(roles)

    def required_approval_role_labels(self):
        return [self.ROLE_LABEL_MAP.get(role, role) for role in sorted(self.required_approval_roles())]

    def required_approvals_pending(self):
        pending = []
        required = self.required_approval_roles()
        if "P" in required and not self.president_approved_by:
            pending.append(self.ROLE_LABEL_MAP["P"])
        if "SEC" in required and not self.secretary_approved_by:
            pending.append(self.ROLE_LABEL_MAP["SEC"])
        return pending

    def can_execute(self):
        pending = self.required_approvals_pending()
        return len(pending) == 0


class DisbursementCategory(models.Model):
    """
    Categories for category-based disbursement.
    Allows admin to assign members to categories and specify amount per category.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    disbursement = models.ForeignKey(Disbursement, on_delete=models.CASCADE, related_name="categories")
    category_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    members = models.ManyToManyField(User, related_name="disbursement_categories", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("disbursement", "category_name")

    def __str__(self):
        return f"{self.disbursement} - {self.category_name}"


class DisbursementTransaction(models.Model):
    """
    Tracks individual member transactions for a disbursement.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    disbursement = models.ForeignKey(Disbursement, on_delete=models.CASCADE, related_name="transactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    wallet_transaction = models.ForeignKey(WalletTransaction, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("disbursement", "user")

    def __str__(self):
        return f"{self.disbursement} - {self.user.first_name} - ₦{self.amount}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESSFUL", "Successful"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdrawal_requests")
    wallet = models.ForeignKey(PaymentUserWallet, on_delete=models.CASCADE, related_name="withdrawal_requests")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    bank_account = models.ForeignKey('forums.BankAccount', on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Withdrawal {self.id} - {self.user} - ₦{self.amount} - {self.status}"


# === Wallet service helpers ===
class WalletService:
    @staticmethod
    def transfer_user_to_forum(user_wallet: PaymentUserWallet, forum_wallet: ForumWallet, amount: Decimal, reason: str, reference: str = ""):
        with transaction.atomic():
            # Lock rows
            uw = PaymentUserWallet.objects.select_for_update().get(pk=user_wallet.pk)
            fw = ForumWallet.objects.select_for_update().get(pk=forum_wallet.pk)

            if uw.balance < amount:
                raise ValidationError("Insufficient wallet balance")

            uw.balance -= amount
            fw.balance += amount

            uw.save()
            fw.save()

            tx = WalletTransaction.objects.create(
                source_user_wallet=uw,
                dest_forum_wallet=fw,
                amount=amount,
                reason=reason,
                reference=reference,
                forum=fw.forum
            )

            return tx

    @staticmethod
    def transfer_user_to_user(source_wallet: PaymentUserWallet, dest_wallet: PaymentUserWallet, amount: Decimal, reason: str, reference: str = ""):
        with transaction.atomic():
            src = PaymentUserWallet.objects.select_for_update().get(pk=source_wallet.pk)
            dst = PaymentUserWallet.objects.select_for_update().get(pk=dest_wallet.pk)

            if src.balance < amount:
                raise ValidationError("Insufficient wallet balance")

            src.balance -= amount
            dst.balance += amount

            src.save()
            dst.save()

            tx = WalletTransaction.objects.create(
                source_user_wallet=src,
                dest_user_wallet=dst,
                amount=amount,
                reason=reason,
                reference=reference,
                forum=None
            )

            return tx

    @staticmethod
    def transfer_forum_to_forum(source_forum_wallet: ForumWallet, dest_forum_wallet: ForumWallet, amount: Decimal, reason: str, reference: str = ""):
        with transaction.atomic():
            src = ForumWallet.objects.select_for_update().get(pk=source_forum_wallet.pk)
            dst = ForumWallet.objects.select_for_update().get(pk=dest_forum_wallet.pk)

            if src.balance < amount:
                raise ValidationError("Forum wallet has insufficient balance")

            src.balance -= amount
            dst.balance += amount

            src.save()
            dst.save()

            tx = WalletTransaction.objects.create(
                source_forum_wallet=src,
                dest_forum_wallet=dst,
                amount=amount,
                reason=reason,
                reference=reference,
                forum=src.forum
            )

            return tx

    @staticmethod
    def transfer_forum_to_user(forum_wallet: ForumWallet, user_wallet: PaymentUserWallet, amount: Decimal, reason: str, reference: str = ""):
        with transaction.atomic():
            fw = ForumWallet.objects.select_for_update().get(pk=forum_wallet.pk)
            uw = PaymentUserWallet.objects.select_for_update().get(pk=user_wallet.pk)

            if fw.balance < amount:
                raise ValidationError("Forum wallet has insufficient balance")

            fw.balance -= amount
            uw.balance += amount

            fw.save()
            uw.save()

            tx = WalletTransaction.objects.create(
                source_forum_wallet=fw,
                dest_user_wallet=uw,
                amount=amount,
                reason=reason,
                reference=reference,
                forum=fw.forum
            )

            return tx

    @staticmethod
    def transfer_forum_to_users(forum_wallet: ForumWallet, distributions: list, reason: str, reference: str = ""):
        """
        distributions: list of tuples (PaymentUserWallet instance, Decimal amount)
        Ensures forum has sufficient balance, applies all transfers atomically.
        """
        total = sum([amt for (_uw, amt) in distributions], Decimal("0.00"))
        with transaction.atomic():
            fw = ForumWallet.objects.select_for_update().get(pk=forum_wallet.pk)
            if fw.balance < total:
                raise ValidationError("Forum wallet has insufficient balance for disbursement")

            fw.balance -= total
            fw.save()

            txs = []
            for uw, amt in distributions:
                uw_locked = PaymentUserWallet.objects.select_for_update().get(pk=uw.pk)
                uw_locked.balance += amt
                uw_locked.save()

                tx = WalletTransaction.objects.create(
                    source_forum_wallet=fw,
                    dest_user_wallet=uw_locked,
                    amount=amt,
                    reason=reason,
                    reference=reference,
                    forum=fw.forum
                )
                txs.append(tx)

            return txs


# Utility to assign member amounts for a payment
def determine_member_category(user, basis=None):
    """
    Determine the category for a user based only on the forum profile attributes in use for a levy:
    gender or age bracket.
    Returns a list of categories that apply.
    """
    cats = []
    profile = getattr(user, 'profile', None)
    if not profile:
        return cats

    basis = (basis or '').upper()

    if basis in ('', 'GENDER'):
        gender = (profile.gender or '').lower()
        if gender == 'male':
            cats.append('male')
        elif gender == 'female':
            cats.append('female')

    if basis in ('', 'AGE'):
        try:
            if profile.date_of_birth:
                today = timezone.now().date()
                age = today.year - profile.date_of_birth.year - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day))
                if age < 18:
                    cats.append('below_18')
                else:
                    cats.append('age_18_plus')
        except Exception:
            pass

    # If a specific basis is requested, return only the corresponding categories.
    if basis == 'GENDER':
        return [c for c in cats if c in {'male', 'female'}]
    if basis == 'AGE':
        return [c for c in cats if c in {'below_18', 'age_18_plus'}]

    return cats


def assign_member_amount(payment: ForumPayment, user):
    """
    Returns Decimal amount a user should pay for the given payment according to its type.
    """
    from decimal import Decimal
    if payment.type == 'DUES':
        return Decimal(payment.amount)
    elif payment.type == 'CONTRIBUTION':
        # For assignment, contribution doesn't enforce amount; store min as due (user may pay more when paying)
        return Decimal(payment.min_amount or 0)
    elif payment.type == 'LEVY':
        basis = (payment.levy_basis or 'GENDER').upper()
        if basis == 'GENDER':
            priority = ['male', 'female']
            allowed = {'male', 'female'}
        elif basis == 'AGE':
            priority = ['below_18', 'age_18_plus']
            allowed = {'below_18', 'age_18_plus'}
        else:
            priority = ['male', 'female', 'below_18', 'age_18_plus']
            allowed = {'male', 'female', 'below_18', 'age_18_plus'}

        cats = determine_member_category(user, basis)
        for p in priority:
            if p in cats:
                cat = payment.categories.filter(category=p, is_active=True).first()
                if cat:
                    return Decimal(cat.amount)

        active = payment.categories.filter(is_active=True, category__in=list(allowed)).first()
        if active:
            return Decimal(active.amount)
        return Decimal('0.00')
    else:
        return Decimal('0.00')


# Assign a payment to all current forum members (call after creating payment)
def assign_payment_to_members(payment: ForumPayment):
    from decimal import Decimal
    members = ForumMembership.objects.filter(forum=payment.forum, is_active=True)
    created = []
    for m in members:
        amount = assign_member_amount(payment, m.user)
        mp, _ = MemberPayment.objects.get_or_create(payment=payment, user=m.user, defaults={'amount_due': amount})
        if not _:
            mp.amount_due = amount
            mp.save()
        created.append(mp)
    return created
