from rest_framework import serializers
from accounts.models import User
from .models import School, SchoolForum, SchoolMembership, IndependentForumRequest, AdminRole
from .models import SchoolJoinRequest, SchoolForumMessage, ForumRequest


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "is_staff",
            "is_superuser",
            "is_verified",
            "is_active",
            "is_admin",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_is_admin(self, obj):
        admin_role = getattr(obj, "admin_role", None)
        return bool(admin_role or obj.is_staff or obj.is_superuser)


class SchoolForumSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    school_id = serializers.UUIDField(source="school.id", read_only=True)

    class Meta:
        model = SchoolForum
        fields = ["id", "school", "school_id", "school_name", "year", "name", "is_general", "description", "created_at"]


class SchoolSerializer(serializers.ModelSerializer):
    forums = SchoolForumSerializer(many=True, read_only=True)

    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "address",
            "country",
            "state",
            "lga",
            "ward",
            "year_established",
            "school_type",
            "visibility",
            "primary_color",
            "secondary_color",
            "badge",
            "description",
            "main_contact_number",
            "is_approved",
            "is_verified",
            "created_at",
            "forums",
        ]


class SchoolForumAboutSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)
    address = serializers.CharField(source="school.address", read_only=True)
    email = serializers.SerializerMethodField()
    phone = serializers.CharField(source="school.main_contact_number", read_only=True)
    profile_picture = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    objectives_rules = serializers.CharField(source="school.description", read_only=True)
    is_verified = serializers.BooleanField(source="school.is_verified", read_only=True)
    is_searchable = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="school.created_by.id", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    forum_id = serializers.SerializerMethodField()
    visibility = serializers.CharField(source="school.visibility", read_only=True)
    settings = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    bank_account = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = SchoolForum
        fields = [
            "id",
            "forum_id",
            "name",
            "description",
            "school_id",
            "school_name",
            "year",
            "is_general",
            "address",
            "email",
            "phone",
            "profile_picture",
            "logo",
            "visibility",
            "objectives_rules",
            "is_verified",
            "is_completed",
            "is_searchable",
            "created_at",
            "created_by",
            "created_by_name",
            "settings",
            "documents",
            "bank_account",
        ]
        read_only_fields = [
            "id",
            "forum_id",
            "name",
            "description",
            "school_id",
            "school_name",
            "year",
            "is_general",
            "address",
            "email",
            "phone",
            "profile_picture",
            "logo",
            "objectives_rules",
            "is_verified",
            "is_completed",
            "is_searchable",
            "created_at",
            "created_by",
            "created_by_name",
            "settings",
            "documents",
            "bank_account",
        ]

    def get_email(self, obj):
        return obj.school.created_by.email if getattr(obj.school, "created_by", None) else ""

    def get_profile_picture(self, obj):
        try:
            url = obj.school.badge.url if obj.school.badge else None
            request = self.context.get("request")
            if url and request is not None and not str(url).startswith("http"):
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

    def get_logo(self, obj):
        return self.get_profile_picture(obj)

    def get_forum_id(self, obj):
        return str(obj.id)

    def get_is_searchable(self, obj):
        return True

    def get_created_by_name(self, obj):
        user = getattr(obj.school, "created_by", None)
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.email
        return "Unknown"

    def get_settings(self, obj):
        return None

    def get_documents(self, obj):
        return []

    def get_bank_account(self, obj):
        return None

    def get_is_completed(self, obj):
        return True


class SchoolForumMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="user.id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)
    profile = serializers.SerializerMethodField()
    activity = serializers.SerializerMethodField()
    ring_color = serializers.SerializerMethodField()

    class Meta:
        model = SchoolMembership
        fields = [
            "id", "user_id", "first_name", "last_name", "user_email", "user_phone",
            "is_verified", "status", "role", "created_at", "profile", "activity", "ring_color"
        ]

    def get_profile(self, obj):
        user = obj.user
        profile_photo = None
        try:
            if getattr(user, "profile", None) and user.profile.photo:
                profile_photo = user.profile.photo.url
                request = self.context.get("request")
                if profile_photo and request is not None and not str(profile_photo).startswith("http"):
                    profile_photo = request.build_absolute_uri(profile_photo)
        except Exception:
            profile_photo = None

        return {
            "id": str(user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_photo": profile_photo,
        }

    def get_activity(self, obj):
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
        return "GRAY"


class SchoolMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolMembership
        fields = ["id", "user", "school", "forum", "status", "role", "created_at"]


class IndependentForumRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndependentForumRequest
        fields = [
            "id",
            "name",
            "description",
            "contact_name",
            "contact_email",
            "contact_phone",
            "objectives",
            "status",
            "created_at",
            "reviewed_at",
        ]


class ForumRequestSerializer(serializers.ModelSerializer):
    submitted_by = UserSummarySerializer(read_only=True)
    reviewed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ForumRequest
        fields = [
            "id",
            "request_type",
            "status",
            "submitted_by",
            "created_at",
            "reviewed_by",
            "reviewed_at",
            "remarks",
            "school_name",
            "organization_name",
            "address",
            "lga",
            "state",
            "country",
            "phone",
            "website",
            "year_established",
            "school_type",
            "visibility",
            "organization_type",
            "join_policy",
            "contact_person",
            "contact_position",
            "contact_phone",
            "contact_email",
        ]


class SchoolJoinRequestSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    forum = SchoolForumSerializer(read_only=True)
    certificate = serializers.FileField(read_only=True)
    certificate_url = serializers.SerializerMethodField()
    is_first_request = serializers.SerializerMethodField()
    rejection_reason = serializers.CharField(read_only=True)

    class Meta:
        model = SchoolJoinRequest
        fields = ["id", "user", "forum", "graduation_year", "certificate", "certificate_url", "is_first_request", "rejection_reason", "status", "requested_at", "reviewed_at", "reviewed_by"]

    def get_certificate_url(self, obj):
        if not obj.certificate:
            return None
        try:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.certificate.url)
        except Exception:
            pass
        return obj.certificate.url

    def get_is_first_request(self, obj):
        if not obj.user_id or not obj.forum_id:
            return False
        return not SchoolJoinRequest.objects.filter(
            user=obj.user,
            forum=obj.forum,
            requested_at__lt=obj.requested_at,
        ).exists()


class SchoolForumMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    sender_id = serializers.UUIDField(source="sender.id", read_only=True)

    class Meta:
        model = SchoolForumMessage
        fields = ["id", "forum", "sender", "sender_id", "sender_name", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "sender", "forum", "created_at", "updated_at"]


class AdminRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminRole
        fields = ["id", "user", "is_super_admin", "can_manage_schools", "can_verify_users", "can_manage_forums", "created_at"]
