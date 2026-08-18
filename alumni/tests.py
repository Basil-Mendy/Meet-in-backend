from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, VerificationRequest
from forums.models import Forum
from .models import School, SchoolForum, SchoolMembership, IndependentForumRequest, AdminRole, SchoolJoinRequest, ForumRequest


class AlumniSchoolTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="secret123",
            phone="08000000000",
            first_name="Admin",
            last_name="User",
            is_staff=True,
        )

    def test_school_creates_class_forums_from_next_year(self):
        school = School.objects.create(
            name="Immaculate Conception College",
            address="Aba",
            year_established=1998,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )

        forums = SchoolForum.objects.filter(school=school)
        self.assertGreaterEqual(forums.count(), 2)
        self.assertTrue(forums.filter(is_general=True).exists())
        self.assertTrue(forums.filter(year=1999).exists())

    def test_existing_school_gets_missing_class_forums_when_refreshed(self):
        school = School.objects.create(
            name="Amara Laughing School",
            address="Aba",
            year_established=2023,
            school_type="SECONDARY",
            created_by=self.admin,
            is_approved=True,
        )
        SchoolForum.objects.filter(school=school).delete()

        school.ensure_default_forums()

        self.assertTrue(SchoolForum.objects.filter(school=school, is_general=True).exists())
        self.assertTrue(SchoolForum.objects.filter(school=school, year=2024).exists())
        self.assertTrue(SchoolForum.objects.filter(school=school, year=2025).exists())
        self.assertTrue(SchoolForum.objects.filter(school=school, year=2026).exists())

    def test_independent_forum_request_is_created(self):
        request = IndependentForumRequest.objects.create(
            user=self.admin,
            name="Old Girls Forum",
            description="Independent alumni forum for old girls",
            requested_by=self.admin,
        )

        self.assertEqual(request.status, "PENDING")
        self.assertEqual(request.name, "Old Girls Forum")

    def test_forum_request_school_duplicate_validation(self):
        ForumRequest.objects.create(
            request_type="SCHOOL",
            submitted_by=self.admin,
            school_name="Kings College",
            address="Lagos",
            lga="Eti Osa",
            state="Lagos",
            country="Nigeria",
            phone="08012345678",
            year_established=1999,
            school_type="SECONDARY",
            contact_person="Adaeze Okafor",
            contact_phone="08012345679",
            contact_email="adaeze@example.com",
            status="PENDING",
        )

        duplicate = ForumRequest.objects.filter(
            request_type="SCHOOL",
            school_name="Kings College",
            status__in=["PENDING", "UNDER_REVIEW", "APPROVED"],
        ).first()

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.request_type, "SCHOOL")

    def test_forum_request_organization_approval_creates_forum_record(self):
        request = ForumRequest.objects.create(
            request_type="ORGANIZATION",
            submitted_by=self.admin,
            organization_name="Nigeria Medical Association",
            address="Abuja",
            lga="Maitama",
            state="FCT",
            country="Nigeria",
            phone="08098765432",
            year_established=1987,
            organization_type="Professional Body",
            contact_person="Dr. Bala Musa",
            contact_position="Secretary",
            contact_phone="08011111111",
            contact_email="secretary@nma.org",
            status="PENDING",
        )

        self.assertEqual(request.request_type, "ORGANIZATION")
        self.assertEqual(request.status, "PENDING")

    def test_admin_can_list_community_forums_with_verification_filters(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save(update_fields=["is_staff", "is_superuser"])

        Forum.objects.create(
            name="NMA Abuja Forum",
            description="Verified community forum",
            created_by=self.admin,
            is_completed=True,
            is_verified=True,
            is_searchable=True,
        )
        Forum.objects.create(
            name="Old Girls Forum",
            description="Pending community forum",
            created_by=self.admin,
            is_completed=True,
            is_verified=False,
            is_searchable=True,
        )

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.get("/api/forums/admin/community-forums/", {"verified": "false"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "Old Girls Forum")

    def test_admin_can_approve_school_and_verification_request(self):
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_staff"])

        school = School.objects.create(
            name="Queens College",
            address="Lagos",
            year_established=2001,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=False,
        )

        verification_request = VerificationRequest.objects.create(
            user=self.admin,
            id_type="national_id",
        )

        client = APIClient()
        client.force_authenticate(user=self.admin)

        school_response = client.post(
            f"/api/alumni/schools/{school.id}/approve/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(school_response.status_code, 200)
        school.refresh_from_db()
        self.assertTrue(school.is_approved)
        self.assertTrue(school.is_verified)

        verification_response = client.post(
            f"/api/alumni/admin/verification-requests/{verification_request.id}/decision/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(verification_response.status_code, 200)
        verification_request.refresh_from_db()
        self.assertEqual(verification_request.status, "approved")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_verified)

    def test_join_mate_marks_membership_as_pending_by_default(self):
        school = School.objects.create(
            name="Mayflower School",
            address="Ikenne",
            year_established=1997,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        class_forum = SchoolForum.objects.filter(school=school, is_general=False).first()

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.post(
            "/api/alumni/join-mate/",
            {"forum_id": str(class_forum.id), "role": "MEMBER"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        membership = SchoolMembership.objects.get(user=self.admin, forum=class_forum)
        self.assertEqual(membership.status, "PENDING")
        self.assertEqual(membership.role, "MEMBER")

    def test_secretary_role_auto_joins_general_forum(self):
        school = School.objects.create(
            name="Model Secondary School",
            address="Abuja",
            year_established=2005,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        class_forum = SchoolForum.objects.filter(school=school, year=2006).first()
        general_forum = SchoolForum.objects.get(school=school, is_general=True)

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.post(
            "/api/alumni/join-mate/",
            {"forum_id": str(class_forum.id), "role": "SECRETARY"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "SECRETARY")
        self.assertTrue(response.json()["joined_general_forum"])
        self.assertTrue(
            SchoolMembership.objects.filter(user=self.admin, forum=general_forum, role="SECRETARY").exists()
        )

    def test_school_search_endpoint_returns_filterable_schools_with_forums(self):
        school = School.objects.create(
            name="Crown College",
            address="Alausa",
            country="Nigeria",
            state="Lagos",
            lga="Ikeja",
            ward="Alausa",
            year_established=2000,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.get(
            "/api/alumni/schools/",
            {"q": "Alausa", "state": "Lagos"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        school_payload = next(item for item in payload if item["id"] == str(school.id))
        self.assertTrue(school_payload["forums"])
        self.assertTrue(any(forum["name"].startswith(school.name) for forum in school_payload["forums"]))

    def test_school_forum_members_endpoint_returns_approved_members(self):
        school = School.objects.create(
            name="United Secondary School",
            address="Lagos",
            year_established=2001,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        class_forum = SchoolForum.objects.filter(school=school, is_general=False).first()
        SchoolMembership.objects.create(
            user=self.admin,
            school=school,
            forum=class_forum,
            status="APPROVED",
            role="MEMBER",
        )

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.get(f"/api/alumni/forums/{class_forum.id}/members/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["user_id"], str(self.admin.id))
        self.assertEqual(payload[0]["status"], "APPROVED")

    def test_school_forum_about_endpoint_requires_membership(self):
        school = School.objects.create(
            name="Saint Teresa School",
            address="Lagos",
            year_established=1999,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        class_forum = SchoolForum.objects.filter(school=school, is_general=False).first()

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.get(f"/api/alumni/forums/{class_forum.id}/about/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], str(class_forum.id))
        self.assertEqual(payload["school_id"], str(school.id))
        self.assertEqual(payload["name"], class_forum.name)

    def test_school_forum_my_role_endpoint_returns_role(self):
        school = School.objects.create(
            name="Saint Teresa School",
            address="Lagos",
            year_established=1999,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        class_forum = SchoolForum.objects.filter(school=school, is_general=False).first()
        SchoolMembership.objects.create(
            user=self.admin,
            school=school,
            forum=class_forum,
            status="APPROVED",
            role="MEMBER",
        )

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.get(f"/api/alumni/forums/{class_forum.id}/my-role/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "MEMBER")

    def test_admin_role_is_created_for_staff_users(self):
        staff_user = User.objects.create_user(
            email="staff@example.com",
            password="secret123",
            phone="08000000001",
            first_name="Staff",
            last_name="User",
            is_staff=True,
        )

        admin_role = AdminRole.objects.create(user=staff_user, is_super_admin=False)

        self.assertTrue(admin_role.can_manage_schools)
        self.assertTrue(admin_role.can_verify_users)
        self.assertTrue(admin_role.can_manage_forums)
        self.assertFalse(admin_role.is_super_admin)

    def test_super_admin_can_create_and_remove_other_admins(self):
        super_admin = User.objects.create_user(
            email="super@example.com",
            password="secret123",
            phone="08000000002",
            first_name="Super",
            last_name="Admin",
            is_staff=True,
            is_superuser=True,
            is_verified=True,
        )

        client = APIClient()
        client.force_authenticate(user=super_admin)

        create_response = client.post(
            "/api/alumni/admin/admins/",
            {
                "email": "newadmin@example.com",
                "password": "secret123",
                "first_name": "New",
                "last_name": "Admin",
                "phone": "08000000003",
                "is_super_admin": False,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        created_user = User.objects.get(email="newadmin@example.com")
        self.assertTrue(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)
        self.assertTrue(AdminRole.objects.filter(user=created_user).exists())

        delete_response = client.delete(f"/api/alumni/admin/admins/{created_user.id}/")
        self.assertEqual(delete_response.status_code, 200)
        created_user.refresh_from_db()
        self.assertFalse(created_user.is_staff)
        self.assertFalse(AdminRole.objects.filter(user=created_user).exists())

    def test_first_ten_approved_members_become_moderators_for_the_forum(self):
        school = School.objects.create(
            name="Great Oak College",
            address="Ibadan",
            year_established=2002,
            school_type="SECONDARY",
            primary_color="#0f172a",
            secondary_color="#f59e0b",
            created_by=self.admin,
            is_approved=True,
        )
        forum = SchoolForum.objects.filter(school=school, is_general=False).first()
        requester = User.objects.create_user(
            email="requester@example.com",
            password="secret123",
            phone="08000000004",
            first_name="Requester",
            last_name="User",
            is_verified=True,
        )
        join_request = SchoolJoinRequest.objects.create(user=requester, forum=forum)

        client = APIClient()
        client.force_authenticate(user=self.admin)

        response = client.post(
            f"/api/alumni/admin/join-requests/{join_request.id}/decision/",
            {"action": "approve"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        membership = SchoolMembership.objects.get(user=requester, forum=forum)
        self.assertEqual(membership.status, "APPROVED")
        self.assertEqual(membership.role, "MODERATOR")

        for index in range(2, 11):
            next_requester = User.objects.create_user(
                email=f"requester{index}@example.com",
                password="secret123",
                phone=f"080000010{index}",
                first_name="Requester",
                last_name=str(index),
                is_verified=True,
            )
            next_request = SchoolJoinRequest.objects.create(user=next_requester, forum=forum)
            next_response = client.post(
                f"/api/alumni/admin/join-requests/{next_request.id}/decision/",
                {"action": "approve"},
                format="json",
            )
            self.assertEqual(next_response.status_code, 200)

        tenth_membership = SchoolMembership.objects.get(user=requester, forum=forum)
        self.assertEqual(tenth_membership.role, "MODERATOR")

        latest_requester = User.objects.create_user(
            email="requester11@example.com",
            password="secret123",
            phone="0800000200",
            first_name="Requester",
            last_name="Eleven",
            is_verified=True,
        )
        latest_request = SchoolJoinRequest.objects.create(user=latest_requester, forum=forum)
        latest_response = client.post(
            f"/api/alumni/admin/join-requests/{latest_request.id}/decision/",
            {"action": "approve"},
            format="json",
        )

        self.assertEqual(latest_response.status_code, 200)
        latest_membership = SchoolMembership.objects.get(user=latest_requester, forum=forum)
        self.assertEqual(latest_membership.role, "MEMBER")
