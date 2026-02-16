from rest_framework.permissions import BasePermission


class IsProfileCompleted(BasePermission):
    message = "Complete your profile to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return hasattr(user, "profile") and user.profile.is_completed


class IsVerifiedUser(BasePermission):
    message = "Your account must be verified to perform this action."

    def has_permission(self, request, view):
        return request.user.is_verified
