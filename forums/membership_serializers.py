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
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = ForumMembership
        fields = [
            "id", "user_id", "first_name", "last_name", "user_email", "user_phone",
            "is_verified", "role", "role_label", "custom_office", "joined_at", "is_active", "profile", "activity", "ring_color"
        ]
        read_only_fields = ["id", "user_id", "first_name", "last_name", "user_email", "user_phone", "is_verified", "joined_at"]

    def get_role_label(self, obj):
        try:
            return obj.effective_role_label
        except Exception:
            return obj.role

    def get_profile(self, obj):
        """Get user profile information"""
        user = obj.user
        profile = getattr(user, "profile", None)
        profile_photo = None
        try:
            if profile and profile.photo:
                profile_photo = profile.photo.url
                request = self.context.get("request")
                if profile_photo and request is not None and not str(profile_photo).startswith("http"):
                    profile_photo = request.build_absolute_uri(profile_photo)
        except Exception:
            profile_photo = None

        profile_data = {
            "id": str(user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_photo": profile_photo,
            "nickname": profile.nickname if profile else "",
            "middle_name": profile.middle_name if profile else "",
            "occupation": profile.occupation if profile else "",
        }
        return profile_data

    def get_activity(self, obj):
        """Get member activity data"""
        try:
            if hasattr(obj, 'activity'):
                activity = obj.activity
                return {
                    "meetings_attended": getattr(activity, "meetings_attended", 0),
                    "posts_count": getattr(activity, "posts_count", 0),
                    "comments_count": getattr(activity, "comments_count", 0),
                    "reactions_count": getattr(activity, "reactions_count", 0),
                    "payments_paid": getattr(activity, "payments_paid", 0),
                    "polls_participated": getattr(activity, "polls_participated", 0),
                    "forum_open_days": getattr(activity, "forum_open_days", 0),
                    "activity_score": getattr(activity, "activity_score", 0),
                    "last_activity_at": getattr(activity, "last_activity_at", None).isoformat() if getattr(activity, "last_activity_at", None) else None,
                }
        except Exception:
            pass
        return {
            "meetings_attended": 0,
            "posts_count": 0,
            "comments_count": 0,
            "reactions_count": 0,
            "payments_paid": 0,
            "polls_participated": 0,
            "forum_open_days": 0,
            "activity_score": 0,
            "last_activity_at": None,
        }

    def get_ring_color(self, obj):
        """Get member ring color based on activity"""
        try:
            if hasattr(obj, 'ring'):
                return obj.ring.ring_color
        except:
            pass
        return "GRAY"
