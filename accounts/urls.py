from django.urls import path
from .views import (
    RegisterView,
    MyProfileView,
    CompleteProfileView,
    ProfileStatusView,
    VerificationRequestView,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("profile/", MyProfileView.as_view()),
    path("profile/complete/", CompleteProfileView.as_view()),
    path("verify/", VerificationRequestView.as_view()),
]
