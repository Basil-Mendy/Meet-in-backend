from django.contrib import admin
from .models import (
    ForumWallet,
    PaymentUserWallet,
    WalletTransaction,
    ForumPayment,
    PaymentCategory,
    MemberPayment,
    Disbursement,
)


@admin.register(ForumWallet)
class ForumWalletAdmin(admin.ModelAdmin):
    list_display = ("forum", "balance", "updated_at")


@admin.register(PaymentUserWallet)
class PaymentUserWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("source_user_wallet", "source_forum_wallet", "dest_user_wallet", "dest_forum_wallet", "amount", "reason", "created_at")
    readonly_fields = ("created_at",)


@admin.register(ForumPayment)
class ForumPaymentAdmin(admin.ModelAdmin):
    list_display = ("forum", "title", "type", "created_by", "created_at")


@admin.register(PaymentCategory)
class PaymentCategoryAdmin(admin.ModelAdmin):
    list_display = ("payment", "category", "amount", "is_active")


@admin.register(MemberPayment)
class MemberPaymentAdmin(admin.ModelAdmin):
    list_display = ("payment", "user", "amount_due", "amount_paid", "status", "paid_at")


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = ("forum", "type", "created_by", "created_at")

