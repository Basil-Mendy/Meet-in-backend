from rest_framework import serializers
from .models import (
    ForumPayment,
    MemberPayment,
    PaymentCategory,
    WalletTransaction,
    PaymentUserWallet,
    ForumWallet,
)
from django.conf import settings


class PaymentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCategory
        fields = ["category", "amount", "is_active"]


class ForumPaymentSerializer(serializers.ModelSerializer):
    categories = PaymentCategorySerializer(many=True, required=False)

    class Meta:
        model = ForumPayment
        fields = ["id", "forum", "title", "type", "levy_basis", "amount", "min_amount", "max_amount", "deadline", "categories", "created_at"]
        read_only_fields = ["forum", "created_at"]

    def create(self, validated_data):
        categories_data = validated_data.pop("categories", [])
        payment = ForumPayment.objects.create(**validated_data)

        for category_data in categories_data:
            category_data = dict(category_data)
            PaymentCategory.objects.create(payment=payment, **category_data)

        return payment


class MemberPaymentSerializer(serializers.ModelSerializer):
    payment_title = serializers.CharField(source="payment.title", read_only=True)
    payment_type = serializers.CharField(source="payment.type", read_only=True)
    min_amount = serializers.SerializerMethodField()
    payment_created_at = serializers.DateTimeField(source="payment.created_at", read_only=True)

    class Meta:
        model = MemberPayment
        fields = ["id", "payment", "payment_title", "payment_type", "amount_due", "amount_paid", "min_amount", "status", "paid_at", "payment_created_at"]
        read_only_fields = ["status", "paid_at", "amount_paid"]

    def get_min_amount(self, obj):
        """Return minimum amount for CONTRIBUTION type, None otherwise"""
        if obj.payment.type == "CONTRIBUTION":
            return str(obj.payment.min_amount)
        return None


class WalletTransactionSerializer(serializers.ModelSerializer):
    transaction_type = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at")
    description = serializers.CharField(source="reason")
    status = serializers.SerializerMethodField()
    source_wallet = serializers.SerializerMethodField()
    destination_wallet = serializers.SerializerMethodField()
    counterparty = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = ["id", "date", "transaction_type", "amount", "description", "reference", "status", "source_wallet", "destination_wallet", "counterparty"]

    def get_transaction_type(self, obj):
        # Derive a semantic transaction type
        if obj.reason and obj.reason.startswith("Payment:"):
            return "Payment"
        if obj.reason and obj.reason.startswith("Disbursement:"):
            return "Disbursement"
        if obj.source_user_wallet and not obj.dest_user_wallet:
            return "Withdrawal"
        if obj.dest_user_wallet and not obj.source_user_wallet:
            return "Deposit"
        return "Transfer"

    def get_status(self, obj):
        # For now, default to COMPLETED. WithdrawalRequests may be linked later.
        return "COMPLETED"

    def get_source_wallet(self, obj):
        if obj.source_user_wallet:
            return {
                "type": "user",
                "id": str(obj.source_user_wallet.id),
                "user_id": str(obj.source_user_wallet.user_id),
                "wallet_number": obj.source_user_wallet.wallet_number,
            }
        if obj.source_forum_wallet:
            return {
                "type": "forum",
                "id": str(obj.source_forum_wallet.id),
                "forum_id": str(obj.source_forum_wallet.forum_id),
                "wallet_number": obj.source_forum_wallet.wallet_number,
            }
        return None

    def get_destination_wallet(self, obj):
        if obj.dest_user_wallet:
            return {
                "type": "user",
                "id": str(obj.dest_user_wallet.id),
                "user_id": str(obj.dest_user_wallet.user_id),
                "wallet_number": obj.dest_user_wallet.wallet_number,
            }
        if obj.dest_forum_wallet:
            return {
                "type": "forum",
                "id": str(obj.dest_forum_wallet.id),
                "forum_id": str(obj.dest_forum_wallet.forum_id),
                "wallet_number": obj.dest_forum_wallet.wallet_number,
            }
        return None

    def get_counterparty(self, obj):
        try:
            if obj.source_forum_wallet:
                return obj.source_forum_wallet.forum.name if obj.source_forum_wallet.forum else None
            if obj.dest_forum_wallet:
                return obj.dest_forum_wallet.forum.name if obj.dest_forum_wallet.forum else None
            if obj.source_user_wallet and getattr(obj.source_user_wallet, 'user', None):
                u = obj.source_user_wallet.user
                return f"{u.first_name} {u.last_name}".strip()
            if obj.dest_user_wallet and getattr(obj.dest_user_wallet, 'user', None):
                u = obj.dest_user_wallet.user
                return f"{u.first_name} {u.last_name}".strip()
        except Exception:
            return None
        return None


class UserToUserTransferSerializer(serializers.Serializer):
    dest_user_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)


class UserToForumTransferSerializer(serializers.Serializer):
    forum_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)


class ForumToForumTransferSerializer(serializers.Serializer):
    source_forum_id = serializers.UUIDField()
    dest_forum_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    method = serializers.ChoiceField(choices=[("CARD", "Card"), ("BANK", "Bank Transfer"), ("OTHER", "Other")], default="CARD")


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    # Optionally allow specifying bank_account id (must belong to user)
    bank_account_id = serializers.UUIDField(required=False)

