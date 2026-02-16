from django.shortcuts import render

# Create your views here.



from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer
import uuid
from decimal import Decimal




# Get Wallet Balance
class WalletBalanceView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.wallet


# Fund Wallet (Mock Funding)
class FundWalletView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")

        if not amount:
            return Response({"error": "Amount is required"}, status=400)

        try:
            amount = Decimal(amount)
        except:
            return Response({"error": "Invalid amount"}, status=400)

        wallet = request.user.wallet
        wallet.balance = wallet.balance + amount
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            type="FUND",
            status="SUCCESS",
            reference=str(uuid.uuid4())
        )

        return Response({"message": "Wallet funded successfully"})

# Transaction History
class WalletTransactionsView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WalletTransaction.objects.filter(wallet=self.request.user.wallet).order_by("-created_at")
