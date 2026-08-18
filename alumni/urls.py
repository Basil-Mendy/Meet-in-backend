from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SchoolViewSet,
    SchoolForumViewSet,
    JoinSchoolForumView,
    JoinMateView,
    IndependentForumRequestView,
    SchoolApprovalView,
    IndependentForumDecisionView,
    VerificationRequestListView,
    VerificationRequestDecisionView,
    AdminDashboardView,
    AdminManagementView,
    AdminCommunityForumsView,
    AdminUserListView,
    AdminUserVerificationView,
    AdminSchoolJoinRequestsView,
    AdminSchoolJoinRequestDecisionView,
    SchoolForumMessageView,
    SchoolForumAboutView,
    SchoolForumMyRoleView,
    AdminRoleViewSet,
    MyJoinRequestsView,
    MySchoolForumsView,
    MyOwnedSchoolsView,
    MyOwnedSchoolJoinRequestsView,
    ForumRequestView,
    ForumRequestDecisionView,
    AdminSchoolManagementView,
    AdminSchoolBulkUploadView,
)

router = DefaultRouter()
router.register(r"schools", SchoolViewSet, basename="school")
router.register(r"forums", SchoolForumViewSet, basename="school-forum")
router.register(r"admin-roles", AdminRoleViewSet, basename="admin-role")

urlpatterns = [
    path("join-forum/<uuid:forum_id>/", JoinSchoolForumView.as_view(), name="join-school-forum"),
    path("join-mate/", JoinMateView.as_view(), name="join-mate"),
    path("requests/independent-forum/", IndependentForumRequestView.as_view(), name="independent-forum-request"),
    path("requests/forum/", ForumRequestView.as_view(), name="forum-request"),
    path("requests/forum/<uuid:request_id>/decision/", ForumRequestDecisionView.as_view(), name="forum-request-decision"),
    path("schools/<uuid:school_id>/approve/", SchoolApprovalView.as_view(), name="school-approval"),
    path("requests/independent-forum/<uuid:request_id>/decision/", IndependentForumDecisionView.as_view(), name="independent-forum-decision"),
    path("admin/verification-requests/", VerificationRequestListView.as_view(), name="verification-request-list"),
    path("admin/verification-requests/<uuid:request_id>/decision/", VerificationRequestDecisionView.as_view(), name="verification-request-decision"),
    path("admin/users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<uuid:user_id>/verify/", AdminUserVerificationView.as_view(), name="admin-user-verification"),
    path("admin/schools/", AdminSchoolManagementView.as_view(), name="admin-school-create"),
    path("admin/schools/bulk-upload/", AdminSchoolBulkUploadView.as_view(), name="admin-school-bulk-upload"),
    path("admin/join-requests/", AdminSchoolJoinRequestsView.as_view(), name="admin-school-join-requests"),
    path("admin/join-requests/<uuid:request_id>/decision/", AdminSchoolJoinRequestDecisionView.as_view(), name="admin-school-join-request-decision"),
    path("join-requests/me/", MyJoinRequestsView.as_view(), name="my-join-requests"),
    path("owned-schools/", MyOwnedSchoolsView.as_view(), name="my-owned-schools"),
    path("owned-schools/join-requests/", MyOwnedSchoolJoinRequestsView.as_view(), name="my-owned-school-join-requests"),
    path("school-forums/<uuid:forum_id>/messages/", SchoolForumMessageView.as_view(), name="school-forum-messages"),
    path("forums/<uuid:forum_id>/about/", SchoolForumAboutView.as_view(), name="school-forum-about"),
    path("forums/<uuid:forum_id>/my-role/", SchoolForumMyRoleView.as_view(), name="school-forum-my-role"),
    path("my-school-forums/", MySchoolForumsView.as_view(), name="my-school-forums"),
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/community-forums/", AdminCommunityForumsView.as_view(), name="admin-community-forums"),
    path("admin/admins/", AdminManagementView.as_view(), name="admin-management"),
    path("admin/admins/<uuid:admin_id>/", AdminManagementView.as_view(), name="admin-management-delete"),
] + router.urls
