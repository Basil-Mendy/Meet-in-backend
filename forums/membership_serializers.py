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
    activity = serializers.SerializerMethodField()
    ring_color = serializers.SerializerMethodField()

    class Meta:
        model = ForumMembership
        fields = [
            "id", "user_id", "first_name", "last_name", "user_email", "user_phone",
            "is_verified", "role", "joined_at", "is_active", "profile", "activity", "ring_color"
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

    def get_activity(self, obj):
        """Get member activity data"""
        try:
            if hasattr(obj, 'activity'):
                activity = obj.activity
                return {
                    "meetings_attended": activity.meetings_attended,
                    "payments_completed": activity.payments_completed,
                    "chats_sent": activity.chats_sent,
                    "activity_score": activity.activity_score,
                    "last_active": activity.last_active.isoformat() if activity.last_active else None,
                }
        except:
            pass
        return {
            "meetings_attended": 0,
            "payments_completed": 0,
            "chats_sent": 0,
            "activity_score": 0,
            "last_active": None,
        }

    def get_ring_color(self, obj):
        """Get member ring color based on activity"""
        try:
            if hasattr(obj, 'ring'):
                return obj.ring.ring_color
        except:
            pass
        return "GRAY"
