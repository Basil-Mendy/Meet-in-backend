from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from forums.models import Forum, ForumMembership
from payments.models import PaymentUserWallet, ForumWallet, WalletService


class WalletTransferTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user1 = User.objects.create_user(
            email="user1@test.com",
            password="password",
            phone="08000000001",
            first_name="User",
            last_name="One",
        )
        self.user2 = User.objects.create_user(
            email="user2@test.com",
            password="password",
            phone="08000000002",
            first_name="User",
            last_name="Two",
        )
        self.forum1 = Forum.objects.create(name="Forum One", description="First forum", created_by=self.user1)
        self.forum2 = Forum.objects.create(name="Forum Two", description="Second forum", created_by=self.user1)
        self.user1_wallet = PaymentUserWallet.objects.create(user=self.user1, balance=Decimal("1000.00"))
        self.user2_wallet = PaymentUserWallet.objects.create(user=self.user2, balance=Decimal("100.00"))
        self.forum1_wallet = ForumWallet.objects.create(forum=self.forum1, balance=Decimal("500.00"))
        self.forum2_wallet = ForumWallet.objects.create(forum=self.forum2, balance=Decimal("250.00"))

    def test_user_to_user_transfer(self):
        tx = WalletService.transfer_user_to_user(
            source_wallet=self.user1_wallet,
            dest_wallet=self.user2_wallet,
            amount=Decimal("200.00"),
            reason="User transfer",
            reference="TX1",
        )

        self.user1_wallet.refresh_from_db()
        self.user2_wallet.refresh_from_db()

        self.assertEqual(self.user1_wallet.balance, Decimal("800.00"))
        self.assertEqual(self.user2_wallet.balance, Decimal("300.00"))
        self.assertEqual(tx.source_user_wallet_id, self.user1_wallet.id)
        self.assertEqual(tx.dest_user_wallet_id, self.user2_wallet.id)
        self.assertEqual(tx.amount, Decimal("200.00"))

    def test_user_to_forum_transfer(self):
        tx = WalletService.transfer_user_to_forum(
            user_wallet=self.user1_wallet,
            forum_wallet=self.forum1_wallet,
            amount=Decimal("150.00"),
            reason="User to forum transfer",
            reference="TX2",
        )

        self.user1_wallet.refresh_from_db()
        self.forum1_wallet.refresh_from_db()

        self.assertEqual(self.user1_wallet.balance, Decimal("850.00"))
        self.assertEqual(self.forum1_wallet.balance, Decimal("650.00"))
        self.assertEqual(tx.source_user_wallet_id, self.user1_wallet.id)
        self.assertEqual(tx.dest_forum_wallet_id, self.forum1_wallet.id)

    def test_forum_to_forum_transfer(self):
        tx = WalletService.transfer_forum_to_forum(
            source_forum_wallet=self.forum1_wallet,
            dest_forum_wallet=self.forum2_wallet,
            amount=Decimal("100.00"),
            reason="Forum transfer",
            reference="TX3",
        )

        self.forum1_wallet.refresh_from_db()
        self.forum2_wallet.refresh_from_db()

        self.assertEqual(self.forum1_wallet.balance, Decimal("400.00"))
        self.assertEqual(self.forum2_wallet.balance, Decimal("350.00"))
        self.assertEqual(tx.source_forum_wallet_id, self.forum1_wallet.id)
        self.assertEqual(tx.dest_forum_wallet_id, self.forum2_wallet.id)


class WalletTransferApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user1 = User.objects.create_user(
            email="apiuser1@test.com",
            password="password",
            phone="08000000003",
            first_name="Api",
            last_name="User1",
        )
        self.user2 = User.objects.create_user(
            email="apiuser2@test.com",
            password="password",
            phone="08000000004",
            first_name="Api",
            last_name="User2",
        )
        self.forum1 = Forum.objects.create(name="Forum A", description="A forum", created_by=self.user1)
        self.forum2 = Forum.objects.create(name="Forum B", description="B forum", created_by=self.user1)
        self.user1_wallet = PaymentUserWallet.objects.create(user=self.user1, balance=Decimal("1000.00"))
        self.user2_wallet = PaymentUserWallet.objects.create(user=self.user2, balance=Decimal("100.00"))
        self.forum1_wallet = ForumWallet.objects.create(forum=self.forum1, balance=Decimal("500.00"))
        self.forum2_wallet = ForumWallet.objects.create(forum=self.forum2, balance=Decimal("250.00"))
        self.membership = ForumMembership.objects.create(forum=self.forum1, user=self.user1, role="P")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

    def test_user_to_user_transfer_endpoint(self):
        response = self.client.post(
            "/api/payments/transfers/user-to-user/",
            {"dest_user_id": str(self.user2.id), "amount": "120.00", "reason": "gift"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.user1_wallet.refresh_from_db()
        self.user2_wallet.refresh_from_db()
        self.assertEqual(self.user1_wallet.balance, Decimal("880.00"))
        self.assertEqual(self.user2_wallet.balance, Decimal("220.00"))

    def test_user_to_forum_transfer_endpoint(self):
        response = self.client.post(
            "/api/payments/transfers/user-to-forum/",
            {"forum_id": str(self.forum1.id), "amount": "80.00", "reason": "support"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.user1_wallet.refresh_from_db()
        self.forum1_wallet.refresh_from_db()
        self.assertEqual(self.user1_wallet.balance, Decimal("920.00"))
        self.assertEqual(self.forum1_wallet.balance, Decimal("580.00"))

    def test_forum_to_forum_transfer_endpoint(self):
        response = self.client.post(
            "/api/payments/transfers/forum-to-forum/",
            {"source_forum_id": str(self.forum1.id), "dest_forum_id": str(self.forum2.id), "amount": "100.00", "reason": "rebalancing"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.forum1_wallet.refresh_from_db()
        self.forum2_wallet.refresh_from_db()
        self.assertEqual(self.forum1_wallet.balance, Decimal("400.00"))
        self.assertEqual(self.forum2_wallet.balance, Decimal("350.00"))


class DisbursementApprovalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password="password",
            phone="08000000005",
            first_name="Admin",
            last_name="User",
        )
        self.president = User.objects.create_user(
            email="president@test.com",
            password="password",
            phone="08000000006",
            first_name="President",
            last_name="User",
        )
        self.secretary = User.objects.create_user(
            email="secretary@test.com",
            password="password",
            phone="08000000007",
            first_name="Secretary",
            last_name="User",
        )
        self.member = User.objects.create_user(
            email="member@test.com",
            password="password",
            phone="08000000008",
            first_name="Member",
            last_name="User",
        )

        self.forum = Forum.objects.create(name="Approval Forum", description="Test forum", created_by=self.admin_user)
        self.forum_wallet = ForumWallet.objects.create(forum=self.forum, balance=Decimal("10000.00"))
        ForumMembership.objects.create(forum=self.forum, user=self.president, role="P")
        ForumMembership.objects.create(forum=self.forum, user=self.secretary, role="SEC")
        ForumMembership.objects.create(forum=self.forum, user=self.member, role="MEMBER")

        self.member_wallet = PaymentUserWallet.objects.create(user=self.member, balance=Decimal("0.00"))
        self.client = APIClient()
        self.client.force_authenticate(user=self.president)

    def test_disbursement_requires_secretary_approval_before_execution(self):
        response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/create/",
            {
                "title": "Secret Bonus",
                "type": "PAY_SELECTED",
                "disbursement_date": "2026-09-01",
                "selected_member_ids": [str(self.member.id)],
                "amount": "500.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        disbursement_id = response.data["id"]

        # President approval should be accepted
        approve_response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/{disbursement_id}/approve/",
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertIn("Secretary", approve_response.data["pending_approvals"])
        self.assertFalse(approve_response.data["ready_for_execution"])

        # Secretary approves next
        self.client.force_authenticate(user=self.secretary)
        approve_response_2 = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/{disbursement_id}/approve/",
            format="json",
        )
        self.assertEqual(approve_response_2.status_code, 200)
        self.assertEqual(approve_response_2.data["pending_approvals"], [])
        self.assertTrue(approve_response_2.data["ready_for_execution"])

        # Execute the disbursement
        execute_response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/{disbursement_id}/execute/",
            format="json",
        )
        self.assertEqual(execute_response.status_code, 200)
        self.forum_wallet.refresh_from_db()
        self.member_wallet.refresh_from_db()
        self.assertEqual(self.forum_wallet.balance, Decimal("9500.00"))
        self.assertEqual(self.member_wallet.balance, Decimal("500.00"))

    def test_disbursement_can_execute_if_role_missing(self):
        # Remove secretary role from the forum, leaving only president role
        ForumMembership.objects.filter(forum=self.forum, role="SEC", user=self.secretary).delete()

        response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/create/",
            {
                "title": "President Only Bonus",
                "type": "PAY_SELECTED",
                "disbursement_date": "2026-09-01",
                "selected_member_ids": [str(self.member.id)],
                "amount": "250.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        disbursement_id = response.data["id"]

        # President should be able to approve and execute without secretary approval
        approve_response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/{disbursement_id}/approve/",
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["pending_approvals"], [])
        self.assertTrue(approve_response.data["ready_for_execution"])

        execute_response = self.client.post(
            f"/api/payments/forums/{self.forum.id}/disbursements/{disbursement_id}/execute/",
            format="json",
        )
        self.assertEqual(execute_response.status_code, 200)
        self.forum_wallet.refresh_from_db()
        self.member_wallet.refresh_from_db()
        self.assertEqual(self.forum_wallet.balance, Decimal("9750.00"))
        self.assertEqual(self.member_wallet.balance, Decimal("250.00"))
