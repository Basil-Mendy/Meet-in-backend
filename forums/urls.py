from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateForumView,
    CompletForumView,
    SearchForumsView,
    MyForumsView,
    JoinForumView,
    ForumPreviewView,
    UserJoinRequestsView,
    GenerateInvitationCodeView,
    ForumInvitationCodesView,
    DeleteInvitationCodeView,
    ReviewJoinRequestView,
    PendingJoinRequestsView,
    ToggleForumSearchabilityView,
    VerifyForumView,
    ForumVerificationRequestView,
    ForumVerificationRequestListView,
    MyProfileRingsView,
    ForumDetailView,
    ForumMyRoleView,
    ForumPostViewSet,
    PostReactionViewSet,
    PostCommentViewSet,
    PostCommentReplyViewSet,
    MeetingViewSet,
    MeetingParticipantViewSet,
    ForumMeetingViewSet,
    MeetingAttendeeViewSet,
    ForumPaymentViewSet,
    ForumPaymentSubmissionViewSet,
    AnnouncementViewSet,
    AnnouncementAttachmentDownloadView,
    PollGroupViewSet,
    PollViewSet,
    NotificationViewSet,
    UserNotificationPreferenceView,
    ForumActivityHistoryView,
)
from alumni.views import AdminCommunityForumsView
from .membership_views import ForumMembersViewSet
from .about_views import (
    ForumAboutView,
    ForumInfoEditView,
    ForumSettingsEditView,
    ForumDocumentViewSet,
    BankAccountView,
)
from .wallet_views import forum_wallet_view

router = DefaultRouter()

# Nested routers for forum-specific resources
urlpatterns = [
    path("create/", CreateForumView.as_view(), name="create-forum"),
    path("<uuid:forum_id>/", ForumDetailView.as_view(), name="forum-detail"),
    path("<uuid:forum_id>/my-role/", ForumMyRoleView.as_view(), name="forum-my-role"),
    path("<uuid:forum_id>/complete/", CompletForumView.as_view(), name="complete-forum"),
    path("search/", SearchForumsView.as_view(), name="search-forums"),
    path("preview/<str:forum_id>/", ForumPreviewView.as_view(), name="forum-preview"),
    path("my-forums/", MyForumsView.as_view(), name="my-forums"),
    path("my-join-requests/", UserJoinRequestsView.as_view(), name="user-join-requests"),
    path("join/", JoinForumView.as_view(), name="join-forum"),
    path("join-requests/<uuid:request_id>/review/", ReviewJoinRequestView.as_view(), name="review-join-request"),
    path("<uuid:forum_id>/join-requests/", PendingJoinRequestsView.as_view(), name="pending-join-requests"),
    path("<uuid:forum_id>/toggle-searchability/", ToggleForumSearchabilityView.as_view(), name="toggle-searchability"),
    path("<uuid:forum_id>/verify/", VerifyForumView.as_view(), name="verify-forum"),
    path("<uuid:forum_id>/verification-request/", ForumVerificationRequestView.as_view(), name="forum-verification-request"),
    path("<uuid:forum_id>/verification-requests/", ForumVerificationRequestListView.as_view(), name="forum-verification-requests"),
    path("<uuid:forum_id>/invitation-codes/", ForumInvitationCodesView.as_view(), name="forum-invitation-codes"),
    path("<uuid:forum_id>/invitation-codes/generate/", GenerateInvitationCodeView.as_view(), name="generate-invitation-code"),
    path("<uuid:forum_id>/invitation-codes/<uuid:code_id>/", DeleteInvitationCodeView.as_view(), name="delete-invitation-code"),
    path("my-rings/", MyProfileRingsView.as_view(), name="my-profile-rings"),
    path("admin/community-forums/", AdminCommunityForumsView.as_view(), name="admin-community-forums"),

    # About Tab
    path("<uuid:forum_id>/about/", ForumAboutView.as_view(), name="forum-about"),
    path("<uuid:forum_id>/about/info/", ForumInfoEditView.as_view(), name="forum-info-edit"),
    path("<uuid:forum_id>/about/settings/", ForumSettingsEditView.as_view(), name="forum-settings-edit"),
    path("<uuid:forum_id>/about/documents/", ForumDocumentViewSet.as_view({"get": "list", "post": "create"}), name="forum-documents"),
    path("<uuid:forum_id>/about/documents/<uuid:pk>/", ForumDocumentViewSet.as_view({"delete": "destroy"}), name="forum-document-detail"),
    path("<uuid:forum_id>/about/bank-account/", BankAccountView.as_view(), name="forum-bank-account"),
    path("<uuid:forum_id>/about/general-records/", ForumActivityHistoryView.as_view(), name="forum-general-records"),

    # Forum Posts
    path("<uuid:forum_id>/posts/", ForumPostViewSet.as_view({"get": "list", "post": "create"}), name="forum-posts"),
    path("<uuid:forum_id>/posts/<uuid:pk>/", ForumPostViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="forum-post-detail"),
    path("<uuid:forum_id>/posts/<uuid:pk>/pin/", ForumPostViewSet.as_view({"post": "pin"}), name="forum-post-pin"),
    
    # Post Reactions
    path("<uuid:forum_id>/posts/<uuid:post_id>/reactions/", PostReactionViewSet.as_view({"get": "list", "post": "create"}), name="post-reactions"),
    
    # Post Comments
    path("<uuid:forum_id>/posts/<uuid:post_id>/comments/", PostCommentViewSet.as_view({"get": "list", "post": "create"}), name="post-comments"),
    path("<uuid:forum_id>/posts/<uuid:post_id>/comments/<uuid:pk>/", PostCommentViewSet.as_view({"put": "update", "delete": "destroy"}), name="post-comment-detail"),

    # Post Comment Replies
    path("<uuid:forum_id>/posts/<uuid:post_id>/comments/<uuid:comment_id>/replies/", PostCommentReplyViewSet.as_view({"get": "list", "post": "create"}), name="post-comment-replies"),
    path("<uuid:forum_id>/posts/<uuid:post_id>/comments/<uuid:comment_id>/replies/<uuid:pk>/", PostCommentReplyViewSet.as_view({"put": "update", "delete": "destroy"}), name="post-comment-reply-detail"),

    # Meetings
    path("<uuid:forum_id>/meetings/", MeetingViewSet.as_view({"get": "list", "post": "create"}), name="forum-meetings"),
    path("<uuid:forum_id>/meetings/<uuid:pk>/", MeetingViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}), name="forum-meeting-detail"),
    path("<uuid:forum_id>/meetings/<uuid:pk>/join/", MeetingViewSet.as_view({"post": "join"}), name="forum-meeting-join"),
    path("<uuid:forum_id>/meetings/<uuid:pk>/leave/", MeetingViewSet.as_view({"post": "leave"}), name="forum-meeting-leave"),
    path("<uuid:forum_id>/meetings/<uuid:pk>/participants/", MeetingViewSet.as_view({"get": "participants"}), name="forum-meeting-participants"),
    path("<uuid:forum_id>/meetings/<uuid:pk>/upload-minutes/", MeetingViewSet.as_view({"post": "upload_minutes"}), name="forum-meeting-upload-minutes"),

    # Announcements
    path("<uuid:forum_id>/announcements/", AnnouncementViewSet.as_view({"get": "list", "post": "create"}), name="forum-announcements"),
    path("<uuid:forum_id>/announcements/<uuid:pk>/", AnnouncementViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}), name="forum-announcement-detail"),
    path("<uuid:forum_id>/announcements/<uuid:pk>/mark-as-read/", AnnouncementViewSet.as_view({"post": "mark_as_read"}), name="announcement-mark-read"),
    path("<uuid:forum_id>/announcements/<uuid:pk>/archive/", AnnouncementViewSet.as_view({"patch": "archive"}), name="announcement-archive"),
    path("<uuid:forum_id>/announcements/recipients/", AnnouncementViewSet.as_view({"get": "recipients"}), name="announcement-recipients"),
    path("<uuid:forum_id>/announcements/attachments/<uuid:attachment_id>/", AnnouncementAttachmentDownloadView.as_view(), name="announcement-attachment-download"),

    # Poll Groups
    path("<uuid:forum_id>/poll-groups/", PollGroupViewSet.as_view({"get": "list", "post": "create"}), name="forum-poll-groups"),
    path("<uuid:forum_id>/poll-groups/<uuid:pk>/", PollGroupViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}), name="forum-poll-group-detail"),
    path("<uuid:forum_id>/poll-groups/<uuid:pk>/archive/", PollGroupViewSet.as_view({"patch": "archive"}), name="poll-group-archive"),

    # Polls
    path("<uuid:forum_id>/polls/", PollViewSet.as_view({"get": "list", "post": "create"}), name="forum-polls"),
    path("<uuid:forum_id>/polls/<uuid:pk>/", PollViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}), name="forum-poll-detail"),
    path("<uuid:forum_id>/polls/<uuid:pk>/vote/", PollViewSet.as_view({"post": "vote"}), name="poll-vote"),
    path("<uuid:forum_id>/polls/<uuid:pk>/archive/", PollViewSet.as_view({"patch": "archive"}), name="poll-archive"),

    # Members
    path("<uuid:forum_id>/members/", ForumMembersViewSet.as_view({"get": "list"}), name="forum-members"),
    path("<uuid:forum_id>/members/<uuid:pk>/", ForumMembersViewSet.as_view({"delete": "destroy"}), name="forum-member-detail"),
    path("<uuid:forum_id>/members/<uuid:pk>/assign-role/", ForumMembersViewSet.as_view({"post": "assign_role"}), name="forum-member-assign-role"),
    path("<uuid:forum_id>/members/custom-roles/", ForumMembersViewSet.as_view({"post": "custom_roles"}), name="forum-member-custom-roles"),
    path("<uuid:forum_id>/members/create-custom-role/", ForumMembersViewSet.as_view({"post": "create_custom_role"}), name="forum-member-create-custom-role"),

    # Notifications
    path("notifications/", NotificationViewSet.as_view({"get": "list"}), name="user-notifications"),
    path("notifications/counts/", NotificationViewSet.as_view({"get": "unread_counts"}), name="notification-counts"),
    path("notifications/mark-as-read/", NotificationViewSet.as_view({"post": "mark_as_read"}), name="mark-notifications-read"),
    path("notifications/clear-forum/", NotificationViewSet.as_view({"post": "clear_forum_notifications"}), name="clear-forum-notifications"),
    path("notifications/clear-tab/", NotificationViewSet.as_view({"post": "clear_tab_notifications"}), name="clear-tab-notifications"),
    path("notifications/<uuid:pk>/mark-read/", NotificationViewSet.as_view({"post": "mark_single_as_read"}), name="mark-notification-read"),
    path("notifications/<uuid:pk>/", NotificationViewSet.as_view({"delete": "destroy"}), name="delete-notification"),
    path("<uuid:forum_id>/notifications/", NotificationViewSet.as_view({"get": "forum_notifications"}), name="forum-notifications"),
    path("notification-preferences/", UserNotificationPreferenceView.as_view(), name="user-notification-preferences"),

    # Wallet
    path("<uuid:forum_id>/wallet/", forum_wallet_view, name="forum-wallet"),
]
