from django.urls import path
from .views import (
    CreateForumPaymentView,
    ForumMemberPaymentsView,
    ForumPaymentsAdminView,
    ForumPaymentMatrixView,
    PayMemberPaymentView,
    CreateDisbursementView,
    ExecuteDisbursementView,
    GetDisbursementDetailsView,
    ForumDisbursementsView,
    ForumWalletBalanceView,
    WalletNumberIssueView,
    UserWalletView,
    UserWalletDepositView,
    UserWalletWithdrawView,
    UserBankAccountView,
    MemberDisbursementsView,
)

urlpatterns = [
    # Payments
    path("forums/<uuid:forum_id>/payments/create/", CreateForumPaymentView.as_view(), name="create-payment"),
    path("forums/<uuid:forum_id>/payments/", ForumMemberPaymentsView.as_view(), name="member-payments"),
    path("forums/<uuid:forum_id>/payments/admin/", ForumPaymentsAdminView.as_view(), name="admin-payments"),
    path("forums/<uuid:forum_id>/payments/matrix/", ForumPaymentMatrixView.as_view(), name="payment-matrix"),
    path("member-payments/<uuid:member_payment_id>/pay/", PayMemberPaymentView.as_view(), name="pay-payment"),
    
    # Disbursements
    path("forums/<uuid:forum_id>/disbursements/", ForumDisbursementsView.as_view(), name="list-disbursements"),
    path("forums/<uuid:forum_id>/disbursements/create/", CreateDisbursementView.as_view(), name="create-disbursement"),
    path("forums/<uuid:forum_id>/disbursements/<uuid:disbursement_id>/", GetDisbursementDetailsView.as_view(), name="get-disbursement-details"),
    path("forums/<uuid:forum_id>/disbursements/<uuid:disbursement_id>/execute/", ExecuteDisbursementView.as_view(), name="execute-disbursement"),
    path("forums/<uuid:forum_id>/my-disbursements/", MemberDisbursementsView.as_view(), name="member-disbursements"),
    
    # Wallet
    path("forums/<uuid:forum_id>/wallet/", ForumWalletBalanceView.as_view(), name="forum-wallet"),
    path("forums/<uuid:forum_id>/wallet/issue-number/", WalletNumberIssueView.as_view(), name="issue-wallet-number"),
    path("users/wallet/", UserWalletView.as_view(), name="user-wallet"),
    path("users/wallet/deposit/", UserWalletDepositView.as_view(), name="user-wallet-deposit"),
    path("users/wallet/withdraw/", UserWalletWithdrawView.as_view(), name="user-wallet-withdraw"),
    path("users/bank-account/", UserBankAccountView.as_view(), name="user-bank-account"),
]
