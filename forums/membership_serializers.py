from rest_framework import serializers
from .models import ForumMembership


class ForumMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_id = serializers.CharField(source="user.id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = ForumMembership
        fields = [
            "id", "user_id", "first_name", "last_name", "user_email", "user_phone",
            "is_verified", "role", "joined_at", "is_active", "profile"
        ]
        read_only_fields = ["id", "user_id", "first_name", "last_name", "user_email", "user_phone", "is_verified", "joined_at"]

    def get_profile(self, obj):
        """Get user profile information"""
        user = obj.user
        profile_data = {
            "id": str(user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_photo": getattr(user, "profile_picture", None)
        }
        return profile_data
