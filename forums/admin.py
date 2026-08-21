from django.contrib import admin
from .models import Forum, ForumMembership, MemberActivity, ProfileRing, Notification, UserNotificationPreference, ForumVerificationPlan, ForumVerificationRequest


@admin.register(Forum)
class ForumAdmin(admin.ModelAdmin):
    list_display = ("name", "is_verified", "created_by", "created_at")


@admin.register(ForumVerificationPlan)
class ForumVerificationPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "fee_amount", "duration_days", "is_active")
    list_filter = ("is_active",)


@admin.register(ForumVerificationRequest)
class ForumVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("forum", "plan", "fee_amount", "status", "created_at")
    list_filter = ("status", "plan")


@admin.register(ForumMembership)
class ForumMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "forum", "role", "joined_at", "is_active")


@admin.register(MemberActivity)
class MemberActivityAdmin(admin.ModelAdmin):
    list_display = ("membership", "meetings_attended", "payments_paid", "activity_score")


@admin.register(ProfileRing)
class ProfileRingAdmin(admin.ModelAdmin):
    list_display = ("membership", "ring_color", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "forum", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("user__email", "forum__name", "message")
    readonly_fields = ("created_at", "id")


@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    readonly_fields = ("created_at", "updated_at", "id")
