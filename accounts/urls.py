from django.urls import path
from .views import (
    RegisterView,
    MyProfileView,
    PublicProfileView,
    CompleteProfileView,
    ProfileStatusView,
    VerificationRequestView,
    PasswordResetAccountHintView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetCompleteView,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("profile/", MyProfileView.as_view()),
    path("profile/<uuid:user_id>/", PublicProfileView.as_view()),
    path("profile/complete/", CompleteProfileView.as_view()),
    path("verify/", VerificationRequestView.as_view()),
    path("password-reset/", PasswordResetRequestView.as_view()),
    path("password-reset/account-hint/", PasswordResetAccountHintView.as_view()),
    path("password-reset/verify/", PasswordResetVerifyView.as_view()),
    path("password-reset/complete/", PasswordResetCompleteView.as_view()),
]
