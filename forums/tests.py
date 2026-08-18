from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Profile, User
from alumni.models import School
from forums.models import Forum, ForumMembership, InboxMessage


class ForumCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="creator@example.com",
            password="secret123",
            phone="08000000001",
            first_name="Creator",
            last_name="User",
        )
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_completed = True
        profile.save(update_fields=["is_completed"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_duplicate_school_class_forum_is_rejected_for_same_year_and_nickname(self):
        school = School.objects.create(
            name="St. Thomas High School",
            address="Ikeja",
            country="Nigeria",
            state="Lagos",
            lga="Ikeja",
            year_established=1990,
            school_type="SECONDARY",
            created_by=self.user,
            is_approved=True,
        )

        payload = {
            "forum_type": "SCHOOL_CLASS",
            "school": str(school.id),
            "graduation_year": 2025,
            "nickname": "Alpha Class",
            "name": "Alpha Class of 2025",
            "description": "A class forum",
        }

        first_response = self.client.post("/api/forums/create/", payload, format="json")
        self.assertEqual(first_response.status_code, 201)
        self.assertTrue(Forum.objects.filter(school=school, graduation_year=2025, nickname="Alpha Class").exists())

        duplicate_response = self.client.post("/api/forums/create/", payload, format="json")
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("detail", duplicate_response.json())
        self.assertIn("already exists", duplicate_response.json()["detail"])
        existing_forum = duplicate_response.json()["existing_forum"]
        self.assertEqual(existing_forum["school_name"], school.name)
        self.assertEqual(existing_forum["graduation_year"], 2025)
        self.assertEqual(existing_forum["contact_person"], "")

    def test_duplicate_school_class_forum_is_rejected_for_same_year_without_nickname(self):
        school = School.objects.create(
            name="Holy Trinity Grammar School",
            address="Abuja",
            country="Nigeria",
            state="FCT",
            lga="Maitama",
            year_established=1985,
            school_type="SECONDARY",
            created_by=self.user,
            is_approved=True,
        )

        payload = {
            "forum_type": "SCHOOL_CLASS",
            "school": str(school.id),
            "graduation_year": 2026,
            "nickname": "",
            "name": "Class of 2026",
            "description": "A class forum",
        }

        first_response = self.client.post("/api/forums/create/", payload, format="json")
        self.assertEqual(first_response.status_code, 201)
        self.assertTrue(Forum.objects.filter(school=school, graduation_year=2026, nickname="").exists())

        duplicate_response = self.client.post("/api/forums/create/", payload, format="json")
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("detail", duplicate_response.json())
        self.assertIn("already exists", duplicate_response.json()["detail"])
        existing_forum = duplicate_response.json()["existing_forum"]
        self.assertEqual(existing_forum["school_name"], school.name)
        self.assertEqual(existing_forum["graduation_year"], 2026)
        self.assertEqual(existing_forum["contact_person"], "")


class InboxAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="executive@example.com",
            password="secret123",
            phone="08011111111",
            first_name="Forum",
            last_name="Exec",
        )
        self.other_user = User.objects.create_user(
            email="member@example.com",
            password="secret123",
            phone="08022222222",
            first_name="Another",
            last_name="User",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.forum = Forum.objects.create(
            name="Alpha Alumni Forum",
            description="Forum for testing",
            created_by=self.user,
            is_completed=True,
        )
        ForumMembership.objects.create(user=self.user, forum=self.forum, role="SEC", is_active=True)

    def test_forum_box_returns_only_forum_related_messages(self):
        private_message = InboxMessage.objects.create(
            sender_user=self.user,
            recipient_user=self.other_user,
            sender_type="USER",
            recipient_type="USER",
            message_type="UNOFFICIAL",
            subject="Private",
            body="Only for me",
        )
        forum_message = InboxMessage.objects.create(
            sender_forum=self.forum,
            sender_type="FORUM",
            recipient_user=self.other_user,
            recipient_type="USER",
            message_type="OFFICIAL",
            subject="Forum alert",
            body="This belongs to the forum",
        )

        response = self.client.get(f"/api/inbox/messages/?forum_id={self.forum.id}")

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()}
        self.assertIn(str(forum_message.id), ids)
        self.assertNotIn(str(private_message.id), ids)

    def test_forum_executive_can_send_forum_message_on_behalf_of_forum(self):
        response = self.client.post(
            "/api/inbox/send/",
            {
                "subject": "Forum update",
                "body": "This is sent by the forum",
                "message_type": "OFFICIAL",
                "recipient_type": "USER",
                "user_id": str(self.other_user.id),
                "from_forum_id": str(self.forum.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        message = InboxMessage.objects.get(id=response.json()["id"])
        self.assertEqual(message.sender_type, "FORUM")
        self.assertEqual(str(message.sender_forum_id), str(self.forum.id))
        self.assertEqual(message.recipient_user, self.other_user)
