from django.urls import path
from .views import WalletBalanceView, FundWalletView, WalletTransactionsView

urlpatterns = [
    path("balance/", WalletBalanceView.as_view(), name="wallet-balance"),
    path("fund/", FundWalletView.as_view(), name="fund-wallet"),
    path("transactions/", WalletTransactionsView.as_view(), name="wallet-transactions"),
]
