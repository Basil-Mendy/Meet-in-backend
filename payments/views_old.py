from django.shortcuts import render

# Create your views here.

from decimal import Decimal
import uuid
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import ForumPayment, MemberPayment, ForumWallet, ForumWalletTransaction
from wallet.models import WalletTransaction
from forums.models import ForumMembership, MemberActivity
from .serializers import ForumPaymentSerializer





class CreateForumPaymentView(generics.CreateAPIView):
    serializer_class = ForumPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        forum_id = self.request.data.get("forum_id")
        forum_membership = get_object_or_404(
            ForumMembership,
            forum_id=forum_id,
            user=self.request.user
        )

        if forum_membership.role not in ["SA", "CP", "VC", "SEC", "FSEC"]:
            raise PermissionError("Not authorized")

        payment = serializer.save(
            forum_id=forum_id,
            created_by=self.request.user
        )

        # create pending payment for all members
        members = ForumMembership.objects.filter(forum_id=forum_id)
        MemberPayment.objects.bulk_create([
            MemberPayment(payment=payment, user=m.user)
            for m in members
        ])



class MyForumPaymentsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ForumPaymentSerializer

    def get_queryset(self):
        forum_id = self.kwargs["forum_id"]
        return ForumPayment.objects.filter(forum_id=forum_id)



class PayForumDueView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, payment_id):
        payment = get_object_or_404(ForumPayment, id=payment_id)
        member_payment = get_object_or_404(
            MemberPayment,
            payment=payment,
            user=request.user
        )

        if member_payment.status == "PAID":
            return Response({"message": "Already paid"})

        wallet = request.user.wallet
        amount = payment.amount

        if wallet.balance < amount:
            return Response(
                {"error": "Insufficient wallet balance"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # deduct from user wallet
        wallet.balance -= amount
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            type="PAYMENT",
            status="SUCCESS",
            reference=str(uuid.uuid4())
        )

        # credit forum wallet
        forum_wallet = ForumWallet.objects.get(forum=payment.forum)
        forum_wallet.balance += amount
        forum_wallet.save()

        ForumWalletTransaction.objects.create(
            forum_wallet=forum_wallet,
            amount=amount,
            type="INCOME",
            reference=str(uuid.uuid4())
        )

        # mark payment paid
        member_payment.status = "PAID"
        member_payment.paid_at = timezone.now()
        member_payment.save()

        # update activity
        membership = ForumMembership.objects.get(
            forum=payment.forum,
            user=request.user
        )
        activity = membership.activity
        activity.payments_completed += 1
        activity.activity_score += 10
        activity.save()

        return Response({"message": "Payment successful"})

