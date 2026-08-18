from rest_framework.permissions import BasePermission

from .models import Profile


class IsProfileCompleted(BasePermission):
    message = "Complete your profile to perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False

        profile = Profile.objects.filter(user=user).only("is_completed").first()
        if profile is None:
            return False

        return bool(profile.is_completed)


class IsVerifiedUser(BasePermission):
    message = "Your account must be verified to perform this action."

    def has_permission(self, request, view):
        return request.user.is_verified
