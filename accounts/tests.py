from django.test import TestCase

from .models import Profile, User
from .serializers import ProfileSerializer

class UsernameTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="username@example.com",
			password="secret123",
			phone="08033333333",
			first_name="Profile",
			last_name="Owner",
		)
		self.profile = Profile.objects.get(user=self.user)

	def test_username_cannot_be_changed_within_thirty_days(self):
		serializer = ProfileSerializer(self.profile, data={"username": "first_name"}, partial=True)
		self.assertTrue(serializer.is_valid(), serializer.errors)
		serializer.save()

		blocked = ProfileSerializer(self.profile, data={"username": "second_name"}, partial=True)
		self.assertFalse(blocked.is_valid())
		self.assertIn("username", blocked.errors)
