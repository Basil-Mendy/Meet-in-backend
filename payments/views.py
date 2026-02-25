from decimal import Decimal
import uuid
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import (
    ForumPayment,
    MemberPayment,
    ForumWallet,
    PaymentUserWallet,
    WalletTransaction,
    WalletService,
    assign_payment_to_members,
)
from .serializers import (
    ForumPaymentSerializer,
    MemberPaymentSerializer,
)
from forums.models import ForumMembership


ADMIN_ROLES = ["SA", "CP", "VC", "SEC", "FSEC"]


class CreateForumPaymentView(generics.CreateAPIView):
    serializer_class = ForumPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        forum_id = self.kwargs.get("forum_id")
        forum_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=self.request.user
        ).first()

        if not forum_membership or forum_membership.role not in ADMIN_ROLES:
            raise PermissionError("Not authorized to create payments")

        payment = serializer.save(created_by=self.request.user, forum_id=forum_id)

        # assign to current members
        assign_payment_to_members(payment)


class ForumMemberPaymentsView(generics.ListAPIView):
    """Return member payments for the current user within a forum"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MemberPaymentSerializer

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        return MemberPayment.objects.filter(
            payment__forum_id=forum_id,
            user=self.request.user
        ).order_by("-payment__created_at")


class MemberDisbursementsView(views.APIView):
    """Return disbursements received by the logged-in member in a forum"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id):
        from .models import Disbursement, DisbursementCategory, WalletTransaction
        
        disbursements = []
        
        try:
            # Fetch via DisbursementCategory M2M (for PAY_ALL type)
            categories = DisbursementCategory.objects.filter(
                disbursement__forum_id=forum_id,
                members=request.user
            ).select_related("disbursement")
            
            processed_disbursements = set()
            for category in categories:
                if category.disbursement.id not in processed_disbursements:
                    processed_disbursements.add(category.disbursement.id)
                    # Find actual transaction to get received amount
                    tx = WalletTransaction.objects.filter(
                        dest_user_wallet__user=request.user,
                        reason__icontains=f"Disbursement:{category.disbursement.id}"
                    ).first()
                    
                    # Handle None values for dates
                    disbursement_date = category.disbursement.disbursement_date
                    received_date = None
                    if tx:
                        received_date = tx.created_at.isoformat()
                    elif disbursement_date:
                        received_date = disbursement_date.isoformat()
                    
                    disbursements.append({
                        "id": str(category.disbursement.id),
                        "title": category.disbursement.title,
                        "forum_id": str(category.disbursement.forum_id),
                        "amount_received": str(tx.amount) if tx else str(category.amount),
                        "received_date": received_date,
                        "status": "Received",
                        "type": category.disbursement.type,
                    })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(disbursements)


class ForumPaymentMatrixView(views.APIView):
    """
    Admin endpoint to get payment status in matrix format.
    Returns: {
        "members": [{"id": "...", "name": "...", "joined_date": "..."}],
        "payments": [{"id": "...", "title": "...", "type": "...", "created_at": "..."}],
        "matrix": [
            {
                "member_id": "...",
                "member_name": "...",
                "payments": {
                    "payment_id": {"status": "PAID"|"PENDING"|"N/A", "amount_due": "...", "amount_paid": "..."}
                }
            }
        ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id):
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Q
        
        # Get all forum members
        members = ForumMembership.objects.filter(forum_id=forum_id, is_active=True).select_related('user')
        
        # Get all payments for this forum
        payments = ForumPayment.objects.filter(forum_id=forum_id).order_by('created_at')
        
        # Build response
        members_list = [
            {
                "id": str(m.user.id),
                "name": f"{m.user.first_name} {m.user.last_name}",
                "joined_date": m.created_at.isoformat() if hasattr(m, 'created_at') else None,
            }
            for m in members
        ]
        
        payments_list = [
            {
                "id": str(p.id),
                "title": p.title,
                "type": p.type,
                "created_at": p.created_at.isoformat(),
                "amount": str(p.amount) if p.amount else None,
                "min_amount": str(p.min_amount) if p.min_amount else None,
            }
            for p in payments
        ]
        
        # Build matrix
        matrix = []
        for member in members:
            member_payments = {}
            for payment in payments:
                # Check if member joined before payment was created
                member_joined_before = member.created_at <= payment.created_at if hasattr(member, 'created_at') else True
                
                if not member_joined_before:
                    # Member joined after payment was created -> N/A
                    member_payments[str(payment.id)] = {
                        "status": "N/A",
                        "amount_due": None,
                        "amount_paid": None,
                    }
                else:
                    # Try to find MemberPayment record
                    mp = MemberPayment.objects.filter(payment=payment, user=member.user).first()
                    if mp:
                        member_payments[str(payment.id)] = {
                            "status": mp.status,
                            "amount_due": str(mp.amount_due),
                            "amount_paid": str(mp.amount_paid),
                        }
                    else:
                        # No record (shouldn't happen if auto-assignment works)
                        member_payments[str(payment.id)] = {
                            "status": "N/A",
                            "amount_due": None,
                            "amount_paid": None,
                        }
            
            matrix.append({
                "member_id": str(member.user.id),
                "member_name": f"{member.user.first_name} {member.user.last_name}",
                "payments": member_payments,
            })
        
        return Response({
            "members": members_list,
            "payments": payments_list,
            "matrix": matrix,
        })


class ForumPaymentsAdminView(views.APIView):
    """Admin endpoint to list all member payments for a forum"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id):
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        member_payments = MemberPayment.objects.filter(payment__forum_id=forum_id).select_related('user', 'payment')
        serializer = MemberPaymentSerializer(member_payments, many=True)
        return Response(serializer.data)


class PayMemberPaymentView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, member_payment_id):
        try:
            mp = get_object_or_404(MemberPayment, id=member_payment_id)
            if mp.user != request.user:
                return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
            if mp.status == 'PAID':
                return Response({"detail": "Already paid"})

            # ensure wallets exist
            user_wallet, _ = PaymentUserWallet.objects.get_or_create(user=request.user)
            forum_wallet, _ = ForumWallet.objects.get_or_create(forum=mp.payment.forum)

            # For CONTRIBUTION: accept optional amount from request; validate min/max
            # For DUES/LEVY: use amount_due from MemberPayment
            amount_to_pay = mp.amount_due

            if mp.payment.type == "CONTRIBUTION":
                request_amount = request.data.get("amount")
                if request_amount:
                    amount_to_pay = Decimal(str(request_amount))
                    # Validate min/max
                    if amount_to_pay < Decimal(mp.payment.min_amount or 0):
                        return Response(
                            {"error": f"Amount must be at least {mp.payment.min_amount}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    if mp.payment.max_amount and amount_to_pay > Decimal(mp.payment.max_amount):
                        return Response(
                            {"error": f"Amount cannot exceed {mp.payment.max_amount}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )

            try:
                tx = WalletService.transfer_user_to_forum(
                    user_wallet, forum_wallet, Decimal(amount_to_pay), 
                    reason=f"Payment:{mp.payment.id}", reference=str(uuid.uuid4())
                )
            except Exception as e:
                # Return a clear 400 with error message for known issues (insufficient funds, validation)
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            # mark payment as paid
            mp.amount_paid = mp.amount_paid + Decimal(amount_to_pay)
            mp.status = 'PAID'
            mp.paid_at = timezone.now()
            mp.save()

            # Return success immediately (payment is already saved to DB)
            # Activity update is best-effort and won't block the response
            response_data = {
                "message": "Payment completed successfully",
                "transaction_id": str(tx.id),
                "status": "success"
            }

            # Attempt activity update (best-effort, non-blocking)
            try:
                membership = ForumMembership.objects.filter(forum=mp.payment.forum, user=request.user).first()
                if membership:
                    # Check if activity relation exists
                    if hasattr(membership, 'activity') and membership.activity:
                        activity = membership.activity
                        activity.payments_completed = (activity.payments_completed or 0) + 1
                        activity.activity_score = (activity.activity_score or 0) + 10
                        activity.save()
            except Exception as activity_error:
                # Log but don't fail the response - payment already succeeded
                import sys
                sys.stderr.write(f"[ACTIVITY-UPDATE] Warning: failed to update activity: {activity_error}\n")

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback, sys
            tb = traceback.format_exc()
            sys.stderr.write(f"[PAYMENT-ERROR] {e}\n{tb}\n")
            return Response({"error": "Internal server error", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ForumWalletBalanceView(views.APIView):
    """Get forum wallet balance"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id):
        try:
            from .models import ForumWallet
            wallet = ForumWallet.objects.get(forum_id=forum_id)
            return Response({
                "balance": str(wallet.balance),
                "wallet_number": wallet.wallet_number if getattr(wallet, 'wallet_number', None) else None,
            })
        except:
            return Response({"balance": "0.00", "wallet_number": None})


class WalletNumberIssueView(views.APIView):
    """Issue a wallet number for a forum via configured external provider (admin only)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, forum_id):
        # Only forum admins allowed
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        from .models import ForumWallet
        from .wallet_providers import get_provider

        try:
            wallet = ForumWallet.objects.get(forum_id=forum_id)
        except ForumWallet.DoesNotExist:
            return Response({"error": "Forum wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        provider_name = request.data.get("provider") or None
        provider = get_provider(provider_name)

        try:
            result = provider.create_virtual_account(wallet.forum, wallet)
            wallet.wallet_number = result.get("wallet_number")
            wallet.save(update_fields=["wallet_number"])
            return Response({"wallet_number": wallet.wallet_number}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserWalletView(views.APIView):
    """Return the logged-in user's payment wallet and recent transactions."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import PaymentUserWallet, WalletTransaction, WithdrawalRequest
        from forums.models import BankAccount

        user_wallet, _ = PaymentUserWallet.objects.get_or_create(user=request.user)

        # Recent transactions involving this user's wallet (incoming and outgoing)
        txs = WalletTransaction.objects.filter(
            (Q(source_user_wallet=user_wallet) | Q(dest_user_wallet=user_wallet))
        ).order_by('-created_at')[:50]

        transactions = []
        for tx in txs:
            # Determine transaction status from any linked withdrawal request
            status_text = "COMPLETED"
            try:
                wr = WithdrawalRequest.objects.filter(reference=str(tx.id)).first()
                if wr:
                    status_text = wr.status
            except Exception:
                status_text = "COMPLETED"

            # Determine transaction type
            if tx.reason and tx.reason.startswith("Payment:"):
                tx_type = "Payment"
            elif tx.reason and tx.reason.startswith("Disbursement:"):
                tx_type = "Disbursement"
            elif tx.source_user_wallet_id and not tx.dest_user_wallet_id:
                tx_type = "Withdrawal"
            elif tx.dest_user_wallet_id and not tx.source_user_wallet_id:
                tx_type = "Deposit"
            else:
                tx_type = "Transfer"

            transactions.append({
                'id': str(tx.id),
                'date': tx.created_at,
                'transaction_type': tx_type,
                'amount': str(tx.amount),
                'description': tx.reason,
                'status': status_text,
            })

        return Response({
            'wallet': {
                'id': str(user_wallet.id),
                'name': f"{request.user.first_name} {request.user.last_name}",
                'wallet_number': user_wallet.wallet_number if getattr(user_wallet, 'wallet_number', None) else None,
                'wallet_type': 'User Wallet',
                'balance': str(user_wallet.balance),
            },
            'transactions': transactions,
        })


class UserWalletDepositView(views.APIView):
    """Deposit into the logged-in user's wallet. Records a WalletTransaction immediately."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .serializers import DepositSerializer
        from .models import PaymentUserWallet, WalletTransaction

        serializer = DepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        method = serializer.validated_data.get('method', 'CARD')

        user_wallet, _ = PaymentUserWallet.objects.get_or_create(user=request.user)

        # For MVP: credit immediately and record transaction. Integrate payment gateway later.
        user_wallet.balance += Decimal(str(amount))
        user_wallet.save()

        tx = WalletTransaction.objects.create(
            dest_user_wallet=user_wallet,
            amount=Decimal(str(amount)),
            reason=f"Deposit:{method}",
            reference=str(uuid.uuid4()),
            forum=None
        )

        return Response({
            'message': 'Deposit recorded',
            'transaction_id': str(tx.id),
            'balance': str(user_wallet.balance)
        }, status=status.HTTP_201_CREATED)


class UserWalletWithdrawView(views.APIView):
    """Request a withdrawal from the logged-in user's wallet to their linked bank account.
    Validates bank account ownership and creates an audit record (WithdrawalRequest).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .serializers import WithdrawSerializer
        from .models import PaymentUserWallet, WalletTransaction, WithdrawalRequest
        from forums.models import BankAccount

        serializer = WithdrawSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(serializer.validated_data['amount']))
        bank_account_id = serializer.validated_data.get('bank_account_id')

        user_wallet, _ = PaymentUserWallet.objects.get_or_create(user=request.user)

        # Find user's linked bank account
        try:
            if bank_account_id:
                bank_account = BankAccount.objects.get(id=bank_account_id, user=request.user)
            else:
                bank_account = BankAccount.objects.get(user=request.user)
        except BankAccount.DoesNotExist:
            return Response({'error': 'No linked bank account found'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate account holder name matches user's name
        acc_name = (bank_account.account_holder_name or '').strip().lower()
        user_name = f"{request.user.first_name} {request.user.last_name}".strip().lower()
        if acc_name != user_name:
            return Response({'error': 'Bank account holder name does not match user name'}, status=status.HTTP_400_BAD_REQUEST)

        # Check sufficient funds
        if user_wallet.balance < amount:
            return Response({'error': 'Insufficient wallet balance'}, status=status.HTTP_400_BAD_REQUEST)

        # Debit wallet immediately and create transaction + withdrawal audit record
        user_wallet.balance -= amount
        user_wallet.save()

        tx = WalletTransaction.objects.create(
            source_user_wallet=user_wallet,
            amount=amount,
            reason='Withdrawal',
            reference=str(uuid.uuid4()),
            forum=None
        )

        wr = WithdrawalRequest.objects.create(
            user=request.user,
            wallet=user_wallet,
            amount=amount,
            bank_account=bank_account,
            reference=str(tx.id),
            status='PENDING'
        )

        return Response({
            'message': 'Withdrawal requested',
            'withdrawal_id': str(wr.id),
            'transaction_id': str(tx.id),
            'balance': str(user_wallet.balance)
        }, status=status.HTTP_201_CREATED)


class ForumDisbursementsView(generics.ListAPIView):
    """List disbursements for a forum (admin only)"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=self.request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return []
        
        from .models import Disbursement
        return Disbursement.objects.filter(forum_id=forum_id).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        from .models import Disbursement, DisbursementCategory
        
        forum_id = self.kwargs.get("forum_id")
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        disbursements = Disbursement.objects.filter(forum_id=forum_id).order_by("-created_at")
        result = []
        for disb in disbursements:
            data = {
                "id": str(disb.id),
                "title": disb.title,
                "type": disb.type,
                "status": disb.status,
                "disbursement_date": disb.disbursement_date,
                "created_at": disb.created_at,
                "created_by": disb.created_by.first_name if disb.created_by else "Unknown",
                "categories": []
            }
            
            # Add categories if PAY_ALL
            if disb.type == "PAY_ALL":
                categories = DisbursementCategory.objects.filter(disbursement=disb)
                for cat in categories:
                    data["categories"].append({
                        "id": str(cat.id),
                        "category_name": cat.category_name,
                        "amount": str(cat.amount),
                        "member_count": cat.members.count()
                    })
            
            result.append(data)

        return Response(result)


class CreateDisbursementView(views.APIView):
    """
    Create a disbursement record.
    Endpoint: POST /api/payments/forums/<forum_id>/disbursements/
    
    Payload for PAY_ALL:
    {
        "title": "Monthly Allowance",
        "type": "PAY_ALL",
        "disbursement_date": "2026-02-10",
        "categories": [
            {"category_name": "Senior", "amount": "5000.00", "member_ids": [...]},
            ...
        ]
    }
    
    Payload for PAY_SELECTED:
    {
        "title": "Special Bonus",
        "type": "PAY_SELECTED",
        "disbursement_date": "2026-02-10",
        "selected_member_ids": [...]
        "amount": "2000.00"
    }
    
    Payload for PAY_TO_ALL:
    {
        "title": "Monthly Stipend",
        "type": "PAY_TO_ALL",
        "disbursement_date": "2026-02-10",
        "amount": "1000.00"
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, forum_id):
        # Only admins
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        from .models import Disbursement, DisbursementCategory
        
        title = request.data.get("title", "Disbursement")
        disb_type = request.data.get("type", "PAY_ALL")
        disb_date = request.data.get("disbursement_date")
        amount = request.data.get("amount")

        if disb_type not in ["PAY_ALL", "PAY_SELECTED", "PAY_TO_ALL"]:
            return Response({"error": "Invalid disbursement type"}, status=status.HTTP_400_BAD_REQUEST)

        # Create disbursement record
        disbursement = Disbursement.objects.create(
            forum_id=forum_id,
            created_by=request.user,
            title=title,
            type=disb_type,
            disbursement_date=disb_date,
            status="PENDING",
            amount=Decimal(str(amount)) if amount else None
        )

        # Add categories if provided (for PAY_ALL)
        if disb_type == "PAY_ALL":
            categories_data = request.data.get("categories", [])
            for cat_data in categories_data:
                category = DisbursementCategory.objects.create(
                    disbursement=disbursement,
                    category_name=cat_data.get("category_name"),
                    amount=Decimal(str(cat_data.get("amount", "0")))
                )
                member_ids = cat_data.get("member_ids", [])
                if member_ids:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    users = User.objects.filter(id__in=member_ids)
                    category.members.set(users)

        return Response({
            "message": "Disbursement created",
            "id": str(disbursement.id),
            "status": disbursement.status
        }, status=status.HTTP_201_CREATED)


class ExecuteDisbursementView(views.APIView):
    """
    Execute a disbursement: transfer funds from forum wallet to members.
    Endpoint: POST /api/payments/forums/<forum_id>/disbursements/<disbursement_id>/execute/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, forum_id, disbursement_id):
        # Import all dependencies upfront
        from .models import Disbursement, DisbursementCategory, DisbursementTransaction, ForumWallet, PaymentUserWallet, WalletTransaction
        from forums.models import ForumMembership
        from django.contrib.auth import get_user_model
        from django.db import transaction
        User = get_user_model()
        
        # Only admins
        membership = ForumMembership.objects.filter(forum_id=forum_id, user=request.user).first()
        if not membership or membership.role not in ADMIN_ROLES:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            disbursement = Disbursement.objects.get(id=disbursement_id, forum_id=forum_id)
            
            # Lock the forum wallet during the entire transaction
            with transaction.atomic():
                forum_wallet = ForumWallet.objects.select_for_update().get(forum_id=forum_id)

                if disbursement.status != "PENDING":
                    return Response({"error": "Disbursement already executed"}, status=status.HTTP_400_BAD_REQUEST)

                # Collect members and amounts to disburse
                distributions = []  # List of (user, amount) tuples

                if disbursement.type == "PAY_ALL":
                    # Get all members from categories
                    categories = DisbursementCategory.objects.filter(disbursement=disbursement)
                    for category in categories:
                        for user in category.members.all():
                            distributions.append((user, category.amount))

                elif disbursement.type == "PAY_SELECTED":
                    # Get selected members (from request)
                    selected_member_ids = request.data.get("selected_member_ids", [])
                    amount = Decimal(str(disbursement.amount))
                    for member_id in selected_member_ids:
                        user = User.objects.get(id=member_id)
                        distributions.append((user, amount))

                elif disbursement.type == "PAY_TO_ALL":
                    # Get all forum members
                    forum_members = ForumMembership.objects.filter(forum_id=forum_id).values_list('user', flat=True)
                    amount = Decimal(str(disbursement.amount))
                    for member_id in forum_members:
                        user = User.objects.get(id=member_id)
                        distributions.append((user, amount))

                # Execute the transfer
                total_amount = sum([amt for (_, amt) in distributions], Decimal("0.00"))

                if forum_wallet.balance < total_amount:
                    return Response({
                        "error": "Insufficient forum wallet balance",
                        "required": str(total_amount),
                        "available": str(forum_wallet.balance)
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Debit forum wallet and credit members atomically
                forum_wallet.balance -= total_amount
                forum_wallet.save()

                # Create individual wallet transactions for each member
                for user, amount in distributions:
                    user_wallet, _ = PaymentUserWallet.objects.get_or_create(user=user)
                    user_wallet.balance += amount
                    user_wallet.save()

                    # Create wallet transaction
                    wallet_tx = WalletTransaction.objects.create(
                        source_forum_wallet=forum_wallet,
                        dest_user_wallet=user_wallet,
                        amount=amount,
                        reason=f"Disbursement: {disbursement.title}",
                        reference=str(disbursement.id),
                        forum_id=forum_id
                    )

                    # Create disbursement transaction record
                    DisbursementTransaction.objects.create(
                        disbursement=disbursement,
                        user=user,
                        amount=amount,
                        wallet_transaction=wallet_tx
                    )

                # Update disbursement status
                disbursement.status = "SUCCESSFUL"
                disbursement.executed_at = timezone.now()
                disbursement.save()

            return Response({
                "message": "Disbursement executed successfully",
                "id": str(disbursement.id),
                "status": disbursement.status,
                "total_amount": str(total_amount),
                "members_count": len(distributions)
            }, status=status.HTTP_200_OK)

        except Disbursement.DoesNotExist:
            return Response({"error": "Disbursement not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            try:
                disbursement.status = "FAILED"
                disbursement.save()
            except:
                pass
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetDisbursementDetailsView(views.APIView):
    """
    Get detailed information about a disbursement including member distributions.
    Endpoint: GET /api/payments/forums/<forum_id>/disbursements/<disbursement_id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id, disbursement_id):
        from .models import Disbursement, DisbursementCategory, DisbursementTransaction

        try:
            disbursement = Disbursement.objects.get(id=disbursement_id, forum_id=forum_id)

            data = {
                "id": str(disbursement.id),
                "title": disbursement.title,
                "type": disbursement.type,
                "status": disbursement.status,
                "amount": str(disbursement.amount) if disbursement.amount else None,
                "disbursement_date": disbursement.disbursement_date,
                "created_at": disbursement.created_at,
                "executed_at": disbursement.executed_at,
                "created_by": {
                    "id": str(disbursement.created_by.id),
                    "name": f"{disbursement.created_by.first_name} {disbursement.created_by.last_name}"
                },
                "categories": [],
                "transactions": [],
                "total_amount_disbursed": "0.00"
            }

            # Add categories if PAY_ALL
            if disbursement.type == "PAY_ALL":
                categories = DisbursementCategory.objects.filter(disbursement=disbursement)
                for cat in categories:
                    data["categories"].append({
                        "id": str(cat.id),
                        "category_name": cat.category_name,
                        "amount": str(cat.amount),
                        "member_count": cat.members.count()
                    })

            # Add transactions (members who received disbursement)
            transactions = DisbursementTransaction.objects.filter(disbursement=disbursement).select_related('user')
            total_disbursed = Decimal("0.00")
            for tx in transactions:
                data["transactions"].append({
                    "user_id": str(tx.user.id),
                    "user_name": f"{tx.user.first_name} {tx.user.last_name}",
                    "amount": str(tx.amount),
                    "created_at": tx.created_at
                })
                total_disbursed += tx.amount

            data["total_amount_disbursed"] = str(total_disbursed)

            return Response(data, status=status.HTTP_200_OK)

        except Disbursement.DoesNotExist:
            return Response({"error": "Disbursement not found"}, status=status.HTTP_404_NOT_FOUND)


class UserBankAccountView(views.APIView):
    """Get, create, or update user's linked bank account for withdrawals."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get user's linked bank account"""
        from forums.models import BankAccount

        try:
            bank_account = BankAccount.objects.get(user=request.user, account_type="PERSONAL")
            from forums.about_serializers import BankAccountSerializer
            serializer = BankAccountSerializer(bank_account)
            return Response(serializer.data)
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'No bank account linked'},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Create or update user's bank account (validates name matches)"""
        from forums.models import BankAccount
        from forums.about_serializers import BankAccountSerializer

        account_holder_name = request.data.get('account_holder_name', '').strip()
        account_number = request.data.get('account_number', '').strip()
        bank_name = request.data.get('bank_name', '').strip()
        bank_code = request.data.get('bank_code', '').strip()

        # Validate that account holder name matches user's full name
        user_name = f"{request.user.first_name} {request.user.last_name}".strip().lower()
        if account_holder_name.lower() != user_name:
            return Response(
                {'error': f'Account holder name must match your name ({request.user.first_name} {request.user.last_name})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        bank_account, created = BankAccount.objects.update_or_create(
            user=request.user,
            account_type="PERSONAL",
            defaults={
                'account_holder_name': account_holder_name,
                'account_number': account_number,
                'bank_name': bank_name,
                'bank_code': bank_code,
            }
        )

        serializer = BankAccountSerializer(bank_account)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        """Remove user's linked bank account"""
        from forums.models import BankAccount

        try:
            bank_account = BankAccount.objects.get(user=request.user, account_type="PERSONAL")
            bank_account.delete()
            return Response(
                {'message': 'Bank account unlinked'},
                status=status.HTTP_200_OK
            )
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'No bank account linked'},
                status=status.HTTP_404_NOT_FOUND
            )