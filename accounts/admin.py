from django.contrib import admin
from .models import User, Profile, VerificationRequest


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "phone",
        "is_verified",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_verified", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-created_at",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_completed",
        "nationality",
        "state",
        "updated_at",
    )
    list_filter = ("is_completed",)
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "nationality",
        "state",
    )


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "fee_amount", "submitted_at", "reviewed_at")
    list_filter = ("status", "submitted_at")
