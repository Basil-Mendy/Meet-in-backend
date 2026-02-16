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
    categories = PaymentCategorySerializer(many=True, read_only=True)

    class Meta:
        model = ForumPayment
        fields = ["id", "forum", "title", "type", "amount", "min_amount", "max_amount", "deadline", "categories", "created_at"]
        read_only_fields = ["forum", "created_at"]


class MemberPaymentSerializer(serializers.ModelSerializer):
    payment_title = serializers.CharField(source="payment.title", read_only=True)
    payment_type = serializers.CharField(source="payment.type", read_only=True)
    min_amount = serializers.SerializerMethodField()

    class Meta:
        model = MemberPayment
        fields = ["id", "payment", "payment_title", "payment_type", "amount_due", "amount_paid", "min_amount", "status", "paid_at"]
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

    class Meta:
        model = WalletTransaction
        fields = ["id", "date", "transaction_type", "amount", "description", "reference", "status"]

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


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    method = serializers.ChoiceField(choices=[("CARD", "Card"), ("BANK", "Bank Transfer"), ("OTHER", "Other")], default="CARD")


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    # Optionally allow specifying bank_account id (must belong to user)
    bank_account_id = serializers.UUIDField(required=False)

