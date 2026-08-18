from decimal import Decimal
from rest_framework import generics, status, viewsets
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from django.http import FileResponse, Http404
import mimetypes

from .models import (
    Forum, ForumMembership, ProfileRing, ForumVerificationRequest,
    ForumJoinRequest, ForumInvitationCode,
    ForumPost, PostReaction, PostComment, PostCommentReply,
    Meeting, MeetingParticipant, MeetingMinute,
    ForumMeeting, MeetingAttendee,
    ForumPayment, ForumPaymentSubmission,
    Announcement, AnnouncementRead, AnnouncementRecipient, AnnouncementAttachment,
    Poll, PollGroup, PollOption, PollVote,
    Notification, UserNotificationPreference, ForumActivityHistory
)
from .serializers import (
    ForumSerializer, ForumCreateSerializer, ForumCompleteSerializer,
    ForumVerificationRequestSerializer,
    ProfileRingSerializer, ForumMembershipSerializer, ForumJoinRequestSerializer, ForumInvitationCodeSerializer,
    ForumPostSerializer, PostReactionSerializer, PostCommentSerializer, PostCommentReplySerializer,
    MeetingListSerializer, MeetingDetailSerializer, MeetingCreateSerializer,
    MeetingParticipantSerializer, MeetingMinuteSerializer,
    ForumMeetingSerializer, MeetingAttendeeSerializer,
    ForumPaymentSerializer, ForumPaymentSubmissionSerializer,
    AnnouncementSerializer,
    PollGroupSerializer, PollSerializer, PollOptionSerializer,
    NotificationSerializer, NotificationListSerializer, UserNotificationPreferenceSerializer,
    ForumActivityHistorySerializer
)
from accounts.permissions import IsProfileCompleted
from .notification_service import NotificationService
from accounts.models import User


class DuplicateForumError(Exception):
    def __init__(self, detail, existing_forum=None):
        self.detail = detail
        self.existing_forum = existing_forum
        super().__init__(detail)


def _is_forum_admin(user):
    admin_role = getattr(user, "admin_role", None)
    return bool(
        user.is_superuser
        or user.is_staff
        or (admin_role and getattr(admin_role, "can_manage_forums", False))
    )


# Create Forum (PROFILE MUST BE COMPLETED)
class CreateForumView(generics.CreateAPIView):
    serializer_class = ForumCreateSerializer
    permission_classes = [IsAuthenticated, IsProfileCompleted]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            created_forum = self.perform_create(serializer)
        except DuplicateForumError as exc:
            return Response(
                {
                    "detail": exc.detail,
                    "existing_forum": exc.existing_forum,
                },
                status=status.HTTP_409_CONFLICT,
            )

        headers = self.get_success_headers(serializer.data)
        response_data = created_forum if created_forum is not None else serializer.data
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        data = self.request.data
        forum_type = (data.get("forum_type") or "ORGANIZATION").upper()

        if forum_type == "ORGANIZATION" and not data.get("town"):
            raise serializers.ValidationError({"town": "Organization town is required."})

        # School-class forum flow
        if forum_type == "SCHOOL_CLASS":
            # Try to resolve existing school id
            school = None
            school_id = data.get("school") or data.get("school_id")
            if school_id:
                try:
                    from alumni.models import School
                    school = School.objects.get(id=school_id)
                except Exception:
                    school = None

            # Optionally create school inline when `create_school` is truthy
            if not school and data.get("create_school"):
                from alumni.models import School
                school_name = data.get("school_name") or data.get("name")
                if not school_name:
                    raise serializers.ValidationError({"school": "School name is required when creating a school."})
                school = School.objects.create(
                    name=school_name,
                    address=data.get("school_address") or data.get("address") or "",
                    country=data.get("school_country") or data.get("country") or "Nigeria",
                    state=data.get("school_state") or data.get("state") or "",
                    lga=data.get("school_lga") or data.get("lga") or "",
                    year_established=(data.get("school_year_established") or data.get("year_established") or 2000),
                    school_type=data.get("school_type") or "SECONDARY",
                    created_by=self.request.user,
                )

                # Create general alumni forum automatically
                from .models import Forum as ForumModel
                import random, string
                forum_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
                while ForumModel.objects.filter(forum_id=forum_id).exists():
                    forum_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))

                ForumModel.objects.create(
                    forum_id=forum_id,
                    name=f"{school.name} General Alumni Forum",
                    description=f"General alumni forum for {school.name}",
                    is_completed=True,
                    is_verified=False,
                    is_searchable=False,
                    created_by=self.request.user,
                    forum_type="SCHOOL_CLASS",
                    school=school,
                    is_general=True,
                )

            if not school:
                raise serializers.ValidationError({"school": "School not found. Provide `school` or set `create_school` to true with school data."})

            graduation_year = data.get("graduation_year") or data.get("year")
            nickname = (data.get("nickname") or "").strip()
            duplicate_filter = Forum.objects.filter(
                forum_type="SCHOOL_CLASS",
                school=school,
                is_general=False,
            )
            if graduation_year:
                duplicate_filter = duplicate_filter.filter(graduation_year=int(graduation_year))
            else:
                duplicate_filter = duplicate_filter.filter(graduation_year__isnull=True)

            if duplicate_filter.exists():
                existing_forum = duplicate_filter.order_by("created_at").first()
                existing_payload = {
                    "id": str(existing_forum.id),
                    "name": existing_forum.name,
                    "forum_id": existing_forum.forum_id,
                    "school_name": existing_forum.school.name if existing_forum.school else "",
                    "graduation_year": existing_forum.graduation_year,
                    "contact_person": existing_forum.contact_person or "",
                }
                raise DuplicateForumError(
                    "A school class forum already exists for this school and graduation year. Please join the existing forum instead.",
                    existing_payload,
                )

            # Create the class forum
            import random, string
            forum_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
            while Forum.objects.filter(forum_id=forum_id).exists():
                forum_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))

            name = data.get("name") or (f"Class of {graduation_year}" if graduation_year else f"{school.name} Class Forum")

            forum = Forum.objects.create(
                forum_id=forum_id,
                name=name,
                description=data.get("description") or "",
                address=data.get("address") or school.address or "",
                email=data.get("email") or "",
                phone=data.get("phone") or "",
                is_completed=True,
                is_verified=False,
                is_searchable=True,
                created_by=self.request.user,
                forum_type="SCHOOL_CLASS",
                school=school,
                graduation_year=(int(graduation_year) if graduation_year else None),
                nickname=nickname,
                is_general=False,
            )

            # Creator becomes a founding moderator of the class forum
            ForumMembership.objects.create(user=self.request.user, forum=forum, role="MOD1", is_active=True)

            # Create wallet for forum (payments app)
            try:
                from payments.models import ForumWallet
                ForumWallet.objects.create(forum=forum)
            except Exception:
                pass

            return ForumSerializer(forum, context={"request": self.request}).data

        # Fallback: organization forum creation uses serializer as before
        forum = serializer.save(created_by=self.request.user)

        # Creator automatically becomes a founding moderator (not president)
        ForumMembership.objects.create(
            user=self.request.user,
            forum=forum,
            role="MOD1",
            is_active=True,
        )

        # Create wallet for forum (payments app)
        try:
            from payments.models import ForumWallet
            ForumWallet.objects.create(forum=forum)
        except Exception:
            pass

        return ForumSerializer(forum, context={"request": self.request}).data


# Complete Forum Profile
class CompletForumView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Allow forum creator or any executive (non-MEMBER active role) to complete profile
        if forum.created_by != request.user:
            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not membership or not membership.is_executive:
                return Response(
                    {"error": "Only forum creator or executives can complete profile"},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = ForumCompleteSerializer(forum, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForumVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)
        membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
        if forum.created_by != request.user and (not membership or not membership.is_executive):
            return Response(
                {"error": "Only forum creator or executives can request verification."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ForumVerificationRequest.objects.filter(forum=forum, status="PENDING").exists():
            return Response(
                {"error": "A verification request is already pending for this forum."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ForumVerificationRequestSerializer(data=request.data)
        if serializer.is_valid():
            verification_request = serializer.save(
                forum=forum,
                requested_by=request.user,
                fee_amount=forum.verification_fee_amount,
            )
            return Response(ForumVerificationRequestSerializer(verification_request).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForumVerificationRequestListView(generics.ListAPIView):
    serializer_class = ForumVerificationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)

        if _is_forum_admin(self.request.user):
            return ForumVerificationRequest.objects.filter(forum=forum).order_by("-created_at")

        membership = ForumMembership.objects.filter(user=self.request.user, forum=forum, is_active=True).first()
        if forum.created_by == self.request.user or (membership and membership.is_executive):
            return ForumVerificationRequest.objects.filter(forum=forum).order_by("-created_at")

        return ForumVerificationRequest.objects.none()


class VerifyForumView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)

        if not _is_forum_admin(request.user):
            return Response({"error": "Only platform administrators can verify forums."}, status=status.HTTP_403_FORBIDDEN)

        action = (request.data.get("action") or "verify").lower()
        request_id = request.data.get("verification_request_id")

        if action == "verify":
            if not request_id:
                return Response({"error": "verification_request_id is required for approval."}, status=status.HTTP_400_BAD_REQUEST)

            verification_request = get_object_or_404(ForumVerificationRequest, id=request_id, forum=forum)
            if verification_request.status != "PENDING":
                return Response(
                    {"error": "Verification request must be pending to approve."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            fee_amount = verification_request.fee_amount or forum.verification_fee_amount or Decimal("0.00")
            if fee_amount > Decimal("0.00"):
                try:
                    from payments.models import ForumWallet, PaymentUserWallet
                    from payments.models import WalletService

                    forum_wallet = ForumWallet.objects.select_for_update().get(forum=forum)
                    if forum_wallet.balance < fee_amount:
                        return Response(
                            {"error": "Insufficient forum wallet balance to pay verification fee."},
                            status=status.HTTP_402_PAYMENT_REQUIRED,
                        )

                    admin_wallet, _ = PaymentUserWallet.objects.get_or_create(user=request.user)
                    WalletService.transfer_forum_to_user(
                        forum_wallet,
                        admin_wallet,
                        fee_amount,
                        reason="Forum verification fee",
                        reference=f"VERIF-{forum.id}-{verification_request.id}",
                    )
                except ForumWallet.DoesNotExist:
                    return Response(
                        {"error": "Forum wallet not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                except Exception as exc:
                    return Response(
                        {"error": str(exc)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            forum.is_verified = True
            forum.verification_expires_at = timezone.now() + timedelta(days=365)
            forum.save(update_fields=["is_verified", "verification_expires_at"])

            verification_request.status = "APPROVED"
            verification_request.reviewed_by = request.user
            verification_request.reviewed_at = timezone.now()
            verification_request.review_notes = request.data.get("review_notes", "")
            verification_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

            return Response({
                "id": str(forum.id),
                "is_verified": forum.is_verified,
                "verification_expires_at": forum.verification_expires_at,
            })

        if action in ("reject", "deny"):
            if not request_id:
                return Response({"error": "verification_request_id is required for rejection."}, status=status.HTTP_400_BAD_REQUEST)

            verification_request = get_object_or_404(ForumVerificationRequest, id=request_id, forum=forum)
            verification_request.status = "REJECTED"
            verification_request.reviewed_by = request.user
            verification_request.reviewed_at = timezone.now()
            verification_request.review_notes = request.data.get("review_notes", "")
            verification_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

            return Response({"id": str(verification_request.id), "status": verification_request.status})

        if action in ("unverify", "revoke"):
            forum.is_verified = False
            forum.verification_expires_at = None
            forum.save(update_fields=["is_verified", "verification_expires_at"])
            return Response({"id": str(forum.id), "is_verified": forum.is_verified})

        return Response({"error": "Invalid action. Use 'verify', 'reject', or 'unverify'."}, status=status.HTTP_400_BAD_REQUEST)


# Search Forums by Forum ID or Name
class SearchForumsView(generics.ListAPIView):
    serializer_class = ForumSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        state = self.request.query_params.get("state", "").strip()
        lga = self.request.query_params.get("lga", "").strip()
        town = self.request.query_params.get("town", "").strip()
        country = self.request.query_params.get("country", "").strip()

        if not (query or state or lga or town or country):
            return Forum.objects.none()

        queryset = Forum.objects.filter(is_searchable=True)

        if query:
            queryset = queryset.filter(
                Q(forum_id__iexact=query)
                | Q(forum_id__icontains=query)
                | Q(name__icontains=query)
                | Q(nickname__icontains=query)
                | Q(school__name__icontains=query)
                | Q(school__id__iexact=query)
            )

            # Also include all class forums linked to matching schools
            try:
                from alumni.models import School
                school_qs = School.objects.filter(Q(name__icontains=query) | Q(id__iexact=query))
                if school_qs.exists():
                    school_forums = Forum.objects.filter(school__in=school_qs, is_searchable=True)
                    queryset = queryset | school_forums
            except Exception:
                pass

        if state:
            queryset = queryset.filter(state__icontains=state)

        if lga:
            queryset = queryset.filter(lga__icontains=lga)

        if town:
            queryset = queryset.filter(town__icontains=town)

        if country:
            queryset = queryset.filter(country__icontains=country)

        return queryset.order_by('-created_at')


# List My Forums (ANY LOGGED-IN USER CAN VIEW)
class MyForumsView(generics.ListAPIView):
    serializer_class = ForumSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_ids = ForumMembership.objects.filter(
            user=self.request.user
        ).values_list("forum_id", flat=True)

        return Forum.objects.filter(id__in=forum_ids)


# Get Forum by Forum ID (Preview)
class ForumPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, forum_id):
        """Get forum preview by public forum_id"""
        forum = get_object_or_404(Forum, forum_id=forum_id)
        serializer = ForumSerializer(forum, context={"request": request})
        return Response(serializer.data)


# Request to Join Forum with Invitation Code
class JoinForumView(APIView):
    permission_classes = [IsAuthenticated, IsProfileCompleted]

    def post(self, request):
        forum_id = request.data.get("forum_id")  # Public forum ID
        invitation_code = request.data.get("invitation_code")
        
        if not forum_id:
            return Response(
                {"error": "forum_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find forum by public forum_id
        forum = get_object_or_404(Forum, forum_id=forum_id)

        # Check if already a member
        if ForumMembership.objects.filter(user=request.user, forum=forum).exists():
            return Response(
                {"message": "Already a member of this forum"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already requested
        existing_request = ForumJoinRequest.objects.filter(
            user=request.user,
            forum=forum,
            status="PENDING"
        ).first()

        if existing_request:
            return Response(
                {"message": "Join request already pending for this forum"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            settings = forum.settings
        except Exception:
            settings = None

        join_mode = getattr(settings, "join_mode", "REQUEST") if settings else "REQUEST"

        invitation_code = request.data.get("invitation_code")

        if join_mode == "OPEN":
            membership = ForumMembership.objects.create(
                user=request.user,
                forum=forum,
                role="MEMBER",
            )
            serializer = ForumMembershipSerializer(membership, context={"request": request})
            return Response({"status": "APPROVED", "membership": serializer.data}, status=status.HTTP_201_CREATED)

        if join_mode == "INVITE":
            if not invitation_code:
                return Response(
                    {"error": "This forum requires an invitation code to join."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            inv_code = get_object_or_404(ForumInvitationCode, code=invitation_code, forum=forum)
            if not inv_code.can_be_used():
                return Response(
                    {"error": "Invitation code is invalid, expired, or has reached its usage limit"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            inv_code.current_usage_count += 1
            inv_code.save()

            membership = ForumMembership.objects.create(
                user=request.user,
                forum=forum,
                role="MEMBER",
            )
            serializer = ForumMembershipSerializer(membership, context={"request": request})
            return Response({"status": "APPROVED", "membership": serializer.data}, status=status.HTTP_201_CREATED)

        # Default to REQUEST if join_mode is REQUEST or missing.
        join_request = ForumJoinRequest.objects.create(
            user=request.user,
            forum=forum,
            invitation_code=invitation_code or "",
            status="PENDING"
        )

        serializer = ForumJoinRequestSerializer(join_request, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
# Approve/Reject Join Request (Admin only)
class ReviewJoinRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        join_request = get_object_or_404(ForumJoinRequest, id=request_id)
        action = request.data.get("action")  # "approve" or "reject"

        # Check if user is a forum moderator or admin
        membership = get_object_or_404(
            ForumMembership,
            user=request.user,
            forum=join_request.forum,
            is_active=True
        )

        if not membership.is_executive:
            return Response(
                {"error": "Only forum moderators or admins can review requests"},
                status=status.HTTP_403_FORBIDDEN
            )

        if action == "approve":
            membership, created = ForumMembership.objects.get_or_create(
                user=join_request.user,
                forum=join_request.forum,
                defaults={"role": "MEMBER", "is_active": True}
            )

            if not created:
                if not membership.is_active:
                    membership.is_active = True
                    membership.role = "MEMBER"
                    membership.save(update_fields=["is_active", "role"])
                else:
                    return Response(
                        {"error": "User is already a member of this forum."},
                        status=status.HTTP_409_CONFLICT,
                    )

            join_request.status = "APPROVED"
            message = "Join request approved"
        elif action == "reject":
            join_request.status = "REJECTED"
            message = "Join request rejected"
        else:
            return Response(
                {"error": "action must be 'approve' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()

        serializer = ForumJoinRequestSerializer(join_request, context={"request": request})
        return Response({"message": message, "request": serializer.data})


# List pending join requests for a forum (everyone in forum can see, admins can approve/reject)
class PendingJoinRequestsView(generics.ListAPIView):
    serializer_class = ForumJoinRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)

        # Check if user is a member of the forum
        membership = ForumMembership.objects.filter(
            user=self.request.user,
            forum=forum
        ).first()

        # Only forum members can view join requests
        if not membership:
            return ForumJoinRequest.objects.none()

        return ForumJoinRequest.objects.filter(forum=forum, status="PENDING")


# Toggle Forum Searchability (Creator only)
class ToggleForumSearchabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)

        if forum.created_by != request.user:
            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not membership or not membership.is_executive:
                return Response(
                    {"error": "Only forum creator or executives can change searchability"},
                    status=status.HTTP_403_FORBIDDEN
                )

        forum.is_searchable = not forum.is_searchable
        forum.save()

        return Response({
            "message": f"Forum is now {'searchable' if forum.is_searchable else 'hidden'}",
            "is_searchable": forum.is_searchable
        })


# List User's Pending Join Requests
class UserJoinRequestsView(generics.ListAPIView):
    serializer_class = ForumJoinRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Show pending requests made by the current user
        return ForumJoinRequest.objects.filter(user=self.request.user).order_by('-requested_at')


# Generate Invitation Code (Forum Admin Only)
class GenerateInvitationCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, forum_id):
        """
        Generate invitation code for a forum
        Required fields: usage_type, max_usage_count (if LIMITED), validity_days
        usage_type: SINGLE, MULTIPLE, or LIMITED
        """
        forum = get_object_or_404(Forum, id=forum_id)

        # Check if user is a core executive of the forum
        membership = get_object_or_404(
            ForumMembership,
            user=request.user,
            forum=forum,
            is_active=True
        )

        if not membership.is_core_executive:
            return Response(
                {"error": "Only forum admins can generate invitation codes"},
                status=status.HTTP_403_FORBIDDEN
            )

        usage_type = request.data.get("usage_type", "MULTIPLE")  # SINGLE, MULTIPLE, LIMITED
        max_usage = request.data.get("max_usage_count")
        validity_days = request.data.get("validity_days", 30)

        if usage_type not in ["SINGLE", "MULTIPLE", "LIMITED"]:
            return Response(
                {"error": "Invalid usage_type"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if usage_type == "LIMITED" and not max_usage:
            return Response(
                {"error": "max_usage_count is required for LIMITED type"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique code
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not ForumInvitationCode.objects.filter(code=code).exists():
                break

        # Create invitation code
        inv_code = ForumInvitationCode.objects.create(
            forum=forum,
            code=code,
            usage_type=usage_type,
            max_usage_count=max_usage if usage_type == "LIMITED" else None,
            valid_until=timezone.now() + timedelta(days=validity_days),
            created_by=request.user
        )

        serializer = ForumInvitationCodeSerializer(inv_code)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# List Forum's Invitation Codes (Forum Admin Only)
class ForumInvitationCodesView(generics.ListAPIView):
    serializer_class = ForumInvitationCodeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)

        # Check if user is a core executive or legacy admin of the forum
        membership = ForumMembership.objects.filter(
            user=self.request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return ForumInvitationCode.objects.none()

        return ForumInvitationCode.objects.filter(forum=forum).order_by('-created_at')


# Delete Invitation Code (Forum Admin Only)
class DeleteInvitationCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, forum_id, code_id):
        """Delete a specific invitation code"""
        forum = get_object_or_404(Forum, id=forum_id)
        code = get_object_or_404(ForumInvitationCode, id=code_id, forum=forum)

        # Check if user is a core executive o
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {"error": "Only forum admins can delete invitation codes"},
                status=status.HTTP_403_FORBIDDEN
            )

        code.delete()
        return Response(
            {"message": "Invitation code deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


# List My Profile Rings (ANY LOGGED-IN USER)
class MyProfileRingsView(generics.ListAPIView):
    serializer_class = ProfileRingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProfileRing.objects.filter(
            membership__user=self.request.user
        )


class VerifyForumView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)
        # Allow creator or any executive to verify/unverify forum
        if forum.created_by != request.user:
            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not membership or not membership.is_executive:
                return Response({"error": "Only forum creator or executives can verify forums."}, status=status.HTTP_403_FORBIDDEN)

        action = (request.data.get("action") or "verify").lower()
        if action == "verify":
            forum.is_verified = True
        elif action in ("unverify", "revoke"):
            forum.is_verified = False
        else:
            return Response({"error": "Invalid action. Use 'verify' or 'unverify'."}, status=status.HTTP_400_BAD_REQUEST)

        forum.save(update_fields=["is_verified"])
        return Response({"id": str(forum.id), "is_verified": forum.is_verified})

# ==================== FORUM DETAIL WITH ROLE ====================
class ForumDetailView(generics.RetrieveAPIView):
    queryset = Forum.objects.all()
    serializer_class = ForumSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "forum_id"


class ForumMyRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum
        ).first()

        if not membership:
            return Response(
                {"error": "You are not a member of this forum"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({"role": membership.role})


# ==================== FORUM POSTS ====================
class ForumPostViewSet(viewsets.ModelViewSet):
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        return ForumPost.objects.filter(forum_id=forum_id)

    def perform_create(self, serializer):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        serializer.save(author=self.request.user, forum=forum)

    def perform_update(self, serializer):
        # Only author or admin can edit
        post = self.get_object()
        if post.author != self.request.user:
            raise PermissionError("You can only edit your own posts")
        serializer.save()

    def perform_destroy(self, instance):
        # Only author or admin can delete
        if instance.author != self.request.user:
            raise PermissionError("You can only delete your own posts")
        instance.delete()

    @action(detail=True, methods=["post"])
    def pin(self, request, forum_id=None, pk=None):
        post = self.get_object()
        # Check if user is admin
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum_id=forum_id
        ).first()
        # Allow core executives or the post author to pin/unpin
        is_admin = membership and membership.is_core_executive
        if not is_admin and post.author != request.user:
            return Response(
                {"error": "Only admins or the post author can pin posts"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Toggle pinned state
        post.is_pinned = not post.is_pinned

        try:
            post.save()

            # Send notification to forum members about the pin action
            actor_name = getattr(request.user, 'get_full_name', None)
            if callable(actor_name):
                actor_name = request.user.get_full_name() or request.user.username
            else:
                actor_name = request.user.username

            NotificationService.create_forum_notifications(
                forum=post.forum,
                notification_type='FEED_POST_PINNED',
                title=f"Post pinned in {post.forum.name}",
                message=f"{actor_name} pinned a post from {post.author.username}: \"{post.content[:50]}...\"",
                tab='feed',
                object_id=str(post.id),
                excluded_users=[request.user],
                send_push=True,
                send_email=True,
            )

            return Response({"is_pinned": post.is_pinned})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PostReactionViewSet(viewsets.ModelViewSet):
    serializer_class = PostReactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        return PostReaction.objects.filter(post_id=post_id)

    def perform_create(self, serializer):
        post_id = self.kwargs.get("post_id")
        post = get_object_or_404(ForumPost, id=post_id)
        # Remove existing reaction if any
        PostReaction.objects.filter(post=post, user=self.request.user).delete()
        serializer.save(user=self.request.user, post=post)


class PostCommentViewSet(viewsets.ModelViewSet):
    serializer_class = PostCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        return PostComment.objects.filter(post_id=post_id)

    def perform_create(self, serializer):
        post_id = self.kwargs.get("post_id")
        post = get_object_or_404(ForumPost, id=post_id)
        serializer.save(author=self.request.user, post=post)


class PostCommentReplyViewSet(viewsets.ModelViewSet):
    serializer_class = PostCommentReplySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        comment_id = self.kwargs.get("comment_id")
        return PostCommentReply.objects.filter(comment_id=comment_id, comment__post_id=post_id)

    def perform_create(self, serializer):
        post_id = self.kwargs.get("post_id")
        comment_id = self.kwargs.get("comment_id")
        comment = get_object_or_404(PostComment, id=comment_id, post_id=post_id)
        serializer.save(author=self.request.user, comment=comment)

    def perform_update(self, serializer):
        reply = self.get_object()
        if reply.author != self.request.user:
            raise PermissionError("You can only edit your own replies")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            raise PermissionError("You can only delete your own replies")
        instance.delete()


# ==================== FORUM MEETINGS ====================
class ForumMeetingViewSet(viewsets.ModelViewSet):
    serializer_class = ForumMeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        return ForumMeeting.objects.filter(forum_id=forum_id)

    def perform_create(self, serializer):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=self.request.user,
            forum=forum,
            is_active=True
        ).first()
        if not membership or not membership.is_core_executive:
            raise PermissionError("Only admins can create meetings")
        serializer.save(created_by=self.request.user, forum=forum)

    @action(detail=True, methods=["post"])
    def join(self, request, forum_id=None, pk=None):
        meeting = self.get_object()
        MeetingAttendee.objects.get_or_create(
            meeting=meeting,
            user=request.user
        )
        return Response({"message": "Joined meeting"})


class MeetingAttendeeViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingAttendeeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs.get("meeting_id")
        return MeetingAttendee.objects.filter(meeting_id=meeting_id)


# ==================== FORUM PAYMENTS ====================
class ForumPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = ForumPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        return ForumPayment.objects.filter(forum_id=forum_id)

    def perform_create(self, serializer):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        # Check if user is admin
        membership = ForumMembership.objects.filter(
            user=self.request.user,
            forum=forum
        ).first()
        if not membership or not membership.is_core_executive:
            raise PermissionError("Only admins can create payments")
        serializer.save(created_by=self.request.user, forum=forum)


class ForumPaymentSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = ForumPaymentSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        payment_id = self.kwargs.get("payment_id")
        return ForumPaymentSubmission.objects.filter(payment_id=payment_id)

    def perform_create(self, serializer):
        payment_id = self.kwargs.get("payment_id")
        payment = get_object_or_404(ForumPayment, id=payment_id)
        serializer.save(user=self.request.user, payment=payment)


# ==================== FORUM ANNOUNCEMENTS ====================
class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        show_archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        # Only return announcements that the requesting user is allowed to see.
        # GENERAL announcements are visible to all forum members.
        # TARGETED announcements are visible only to their recipients and admins.
        base_qs = Announcement.objects.filter(forum_id=forum_id, is_archived=show_archived)
        user = self.request.user

        # If user is admin of the forum, return all announcements
        try:
            membership = ForumMembership.objects.filter(user=user, forum_id=forum_id, is_active=True).first()
            if membership and membership.is_core_executive:
                return base_qs.order_by('-created_at')
        except Exception:
            pass

        # Non-admin: GENERAL announcements plus TARGETED announcements where user is a recipient
        return base_qs.filter(
            Q(announcement_type='GENERAL') | Q(announcement_type='TARGETED', recipients__user=user)
        ).distinct().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check membership
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        from django.core.mail import send_mail
        from django.conf import settings
        from .models import AnnouncementRecipient

        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only admins can create announcements'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        announcement = serializer.save(created_by=request.user, forum=forum)

        # If TARGETED announcement, process recipients and attachments and deliver in-app notifications
        if announcement.announcement_type == 'TARGETED':
            recipient_ids = request.data.get('recipient_ids', [])
            all_members = request.data.get('all_members', False)

            if all_members:
                recipient_ids = list(ForumMembership.objects.filter(forum=forum, is_active=True).values_list('user_id', flat=True))

            # Create recipient records
            recipients = User.objects.filter(id__in=recipient_ids)
            created_recips = []
            for u in recipients:
                try:
                    rec_obj, created = AnnouncementRecipient.objects.get_or_create(announcement=announcement, user=u)
                    if created:
                        created_recips.append(rec_obj)
                except Exception:
                    continue

            # Create in-app notifications for recipients
            notif_service = NotificationService()
            for rec in created_recips:
                try:
                    Notification.objects.create(
                        user=rec.user,
                        forum=forum,
                        notification_type='ANNOUNCEMENT_CREATED',
                        title=announcement.title,
                        message=(announcement.message[:200] + '...') if len(announcement.message) > 200 else announcement.message,
                        tab='announcements',
                        object_id=str(announcement.id)
                    )

                    # Trigger push (best-effort) using notification service if available
                    try:
                        NotificationService.create_notification(
                            forum=forum,
                            user=rec.user,
                            notification_type='ANNOUNCEMENT_CREATED',
                            title=announcement.title,
                            message=(announcement.message[:200] + '...') if len(announcement.message) > 200 else announcement.message,
                            tab='announcements',
                            object_id=str(announcement.id),
                            send_push=True,
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

        # Handle attachments (multipart file uploads)
        try:
            files = request.FILES.getlist('attachments')
            for f in files:
                AnnouncementAttachment.objects.create(
                    announcement=announcement,
                    file=f,
                    filename=f.name,
                    size=f.size,
                    uploaded_by=request.user
                )
        except Exception:
            # ignore attachment save errors but log in real deployments
            pass

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # This is now handled in the create method
        pass

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, forum_id=None, pk=None):
        announcement = self.get_object()
        AnnouncementRead.objects.get_or_create(
            announcement=announcement,
            user=request.user
        )
        return Response({"message": "Marked as read"})

    @action(detail=True, methods=["patch"])
    def archive(self, request, forum_id=None, pk=None):
        from .models import Announcement
        
        announcement = self.get_object()
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)

        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only admins can archive announcements'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Toggle archive
        announcement.is_archived = not announcement.is_archived
        if announcement.is_archived:
            announcement.archived_at = timezone.now()
        else:
            announcement.archived_at = None

        announcement.save()

        serializer = self.get_serializer(announcement)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recipients(self, request, forum_id=None):
        """Get list of forum members for recipient selection (admin only)"""
        from .models import ForumMembership

        forum = get_object_or_404(Forum, id=forum_id)

        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only admins can view recipients list'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all active members
        members = ForumMembership.objects.filter(
            forum=forum, is_active=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')

        members_data = [
            {
                'id': str(m.user.id),
                'name': f"{m.user.first_name} {m.user.last_name}",
                'email': m.user.email,
                'role': m.role
            }
            for m in members
        ]

        return Response({'members': members_data})


class AnnouncementAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, forum_id=None, attachment_id=None):
        # Serve attachment only if requester is allowed to view the parent announcement
        attachment = get_object_or_404(AnnouncementAttachment, id=attachment_id)
        announcement = attachment.announcement

        # Ensure attachment belongs to the requested forum
        if str(announcement.forum.id) != str(forum_id):
            raise Http404('Attachment not found')

        # Verify membership
        membership = ForumMembership.objects.filter(user=request.user, forum=announcement.forum, is_active=True).first()
        if not membership:
            return Response({'error': 'You are not a member of this forum'}, status=status.HTTP_403_FORBIDDEN)

        # Core executives can access all attachments
        if membership.is_core_executive:
            allowed = True
        else:
            # GENERAL announcements visible to all members
            if announcement.announcement_type == 'GENERAL':
                allowed = True
            else:
                # TARGETED -> only recipients can access
                allowed = AnnouncementRecipient.objects.filter(announcement=announcement, user=request.user).exists()

        if not allowed:
            return Response({'error': 'You are not authorized to access this attachment'}, status=status.HTTP_403_FORBIDDEN)

        # Stream file. Use ?download=true to force attachment download; otherwise prefer inline display when possible.
        try:
            file_handle = attachment.file.open('rb')
            # determine content type
            content_type = None
            try:
                # try to get from stored file (if available)
                if hasattr(attachment.file, 'file') and hasattr(attachment.file.file, 'content_type'):
                    content_type = attachment.file.file.content_type
            except Exception:
                content_type = None

            if not content_type:
                content_type, _ = mimetypes.guess_type(attachment.filename)

            download = str(request.query_params.get('download', 'false')).lower() == 'true'

            # Return FileResponse with content_type and attachment disposition based on download flag
            response = FileResponse(file_handle, as_attachment=download, filename=attachment.filename)
            if content_type:
                response['Content-Type'] = content_type
            return response
        except Exception as e:
            return Response({'error': 'Failed to open attachment'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request, forum_id=None):
        """Mark all active announcements as read for the current user"""
        from .models import AnnouncementRead
        
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Verify user is a forum member
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all active (non-archived) announcements for this forum
        active_announcements = Announcement.objects.filter(
            forum=forum,
            is_archived=False
        )
        
        # Mark all as read for current user
        read_count = 0
        for announcement in active_announcements:
            obj, created = AnnouncementRead.objects.get_or_create(
                announcement=announcement,
                user=request.user
            )
            if created:
                read_count += 1
        
        return Response({
            'message': f'Marked {read_count} announcements as read',
            'total_marked': active_announcements.count()
        })


# ==================== FORUM POLLS ====================
class PollGroupViewSet(viewsets.ModelViewSet):
    """Handle poll groups (collections of related polls)"""
    serializer_class = PollGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        show_archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        queryset = PollGroup.objects.filter(forum_id=forum_id, is_archived=show_archived)
        return queryset

    def list(self, request, *args, **kwargs):
        """List poll groups - members can only see groups for their forum"""
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check membership
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create poll group - admin only"""
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only forum admins can create poll groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, forum=forum)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"])
    def archive(self, request, forum_id=None, pk=None):
        """Archive/unarchive poll group - admin only"""
        group = self.get_object()
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only admins can archive poll groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        group.is_archived = not group.is_archived
        group.save()
        
        # Also archive/unarchive all polls in the group
        group.polls.all().update(is_archived=group.is_archived)
        
        serializer = self.get_serializer(group)
        return Response(serializer.data)


class PollViewSet(viewsets.ModelViewSet):
    serializer_class = PollSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        # Exclude archived polls by default unless explicitly requested
        show_archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        queryset = Poll.objects.filter(
            forum_id=forum_id, is_archived=show_archived
        ).prefetch_related(
            'options__votes__voter',  # Prefetch votes with voter info
            'votes__voter'  # Prefetch poll votes with voter
        ).select_related('created_by', 'group')  # Select related for creators and groups
        return queryset

    def list(self, request, *args, **kwargs):
        """List polls - members can only see polls for their forum"""
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check membership
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create poll - admin only"""
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only forum admins can create polls'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate poll data
        title = request.data.get('title', '').strip()
        options = request.data.get('options', [])
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        
        if not title:
            return Response(
                {'error': 'Poll title is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(options) < 2:
            return Response(
                {'error': 'At least 2 options are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(options) > 20:
            return Response(
                {'error': 'Maximum 20 options allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not start_time or not end_time:
            return Response(
                {'error': 'Start time and end time are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse times
        try:
            from datetime import datetime
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            if end <= start:
                return Response(
                    {'error': 'End time must be after start time'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, AttributeError):
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create poll
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        poll = serializer.save(created_by=request.user, forum=forum)
        
        # Create options
        for option in options:
            # Handle both dict format {"option_text": "..."} and string format
            if isinstance(option, dict):
                option_text = option.get('option_text', '').strip()
            else:
                option_text = str(option).strip()
            
            if option_text:
                PollOption.objects.create(poll=poll, option_text=option_text)
        
        # Send notifications to all forum members
        self.send_poll_notifications(forum, poll, request.user)
        
        # Refresh poll with options
        poll.refresh_from_db()
        serializer = self.get_serializer(poll)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def send_poll_notifications(self, forum, poll, creator):
        """Send email and push notifications to all forum members about new poll"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        members = ForumMembership.objects.filter(
            forum=forum, is_active=True
        ).select_related('user')
        
        email_subject = f"[{forum.name}] New Poll: {poll.title}"
        email_body = f"""
A new poll has been created in forum: {forum.name}

Poll: {poll.title}
Description: {poll.description or 'N/A'}

Vote now to participate in this important decision!

Start time: {poll.start_time}
End time: {poll.end_time}
"""
        
        from_email = forum.email if forum.email else settings.DEFAULT_FROM_EMAIL
        
        for membership in members:
            # Skip the creator
            if membership.user == creator:
                continue
            
            try:
                send_mail(
                    email_subject,
                    email_body,
                    from_email,
                    [membership.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log but don't fail the poll creation
                print(f"Failed to send poll notification to {membership.user.email}: {str(e)}")
        # Create in-app notifications for forum members (exclude creator)
        try:
            NotificationService.create_forum_notifications(
                forum=forum,
                notification_type='POLL_CREATED',
                title=f"New poll in {forum.name}",
                message=f"{creator.get_full_name() or creator.email} created poll \"{poll.title}\"",
                tab='polls',
                object_id=str(poll.id),
                excluded_users=[creator],
                send_push=True,
                send_email=False,
            )
        except Exception as e:
            print(f"Failed to create in-app poll notifications: {e}")

    @action(detail=True, methods=["post"])
    def vote(self, request, forum_id=None, pk=None):
        """Vote on poll - with proper validation"""
        from django.utils import timezone
        
        poll = self.get_object()
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Verify user is forum member
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check poll status
        if poll.status == "UPCOMING":
            return Response(
                {'error': 'This poll has not started yet'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if poll.status == "CLOSED":
            return Response(
                {'error': 'This poll has ended'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get option IDs
        option_ids = request.data.get('option_ids', [])
        if not option_ids:
            option_id = request.data.get('option_id')
            option_ids = [option_id] if option_id else []
        
        if not option_ids:
            return Response(
                {'error': 'At least one option must be selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check vote frequency
        if poll.vote_type == "SINGLE":
            # Remove any existing vote for this user
            existing_votes = PollVote.objects.filter(poll=poll, voter=request.user)
            if existing_votes.exists():
                return Response(
                    {'error': 'You have already voted on this poll'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(option_ids) > 1:
                return Response(
                    {'error': 'This poll allows only one vote'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:  # MULTIPLE
            if len(option_ids) > len(poll.options.all()):
                return Response(
                    {'error': 'Invalid number of options selected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate and create votes
        votes_created = 0
        errors = []
        
        for option_id in option_ids:
            try:
                option = PollOption.objects.get(id=option_id, poll=poll)
                
                # Check for duplicate vote on this option
                if PollVote.objects.filter(
                    poll=poll, option=option, voter=request.user
                ).exists():
                    continue
                
                PollVote.objects.create(
                    poll=poll,
                    option=option,
                    voter=request.user
                )
                votes_created += 1
            except PollOption.DoesNotExist:
                errors.append(f"Option {option_id} not found")
        
        if votes_created == 0 and errors:
            return Response(
                {'error': 'Failed to record votes: ' + ', '.join(errors)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(poll)
        return Response({
            'message': f'{votes_created} vote(s) recorded',
            'poll': serializer.data
        })

    @action(detail=True, methods=["patch"])
    def archive(self, request, forum_id=None, pk=None):
        """Archive poll - admin only"""
        from django.utils import timezone
        
        poll = self.get_object()
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is a core executive
        membership = ForumMembership.objects.filter(
            user=request.user,
            forum=forum,
            is_active=True
        ).first()

        if not membership or not membership.is_core_executive:
            return Response(
                {'error': 'Only admins can archive polls'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        poll.is_archived = not poll.is_archived
        if poll.is_archived:
            poll.archived_at = timezone.now()
        else:
            poll.archived_at = None
        
        poll.save()
        
        serializer = self.get_serializer(poll)
        return Response(serializer.data)



# ==================== FORUM MEETINGS ====================
class MeetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing forum meetings.
    - List and detail: All authenticated members can view
    - Create, update, delete: Forum admins only
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        forum_id = self.kwargs.get("forum_id")
        return Meeting.objects.filter(forum_id=forum_id).prefetch_related("participants")

    def get_serializer_class(self):
        if self.action == "create":
            return MeetingCreateSerializer
        elif self.action == "retrieve":
            return MeetingDetailSerializer
        return MeetingListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["forum_id"] = self.kwargs.get("forum_id")
        return context

    def check_admin_permission(self):
        """Check if user is forum admin"""
        forum_id = self.kwargs.get("forum_id")
        forum = get_object_or_404(Forum, id=forum_id)
        
        membership = ForumMembership.objects.filter(
            user=self.request.user,
            forum=forum,
            is_active=True
        ).first()
        
        if not membership or not membership.is_core_executive:
            return False
        return True

    def create(self, request, *args, **kwargs):
        if not self.check_admin_permission():
            return Response(
                {"error": "Only forum admins can create meetings"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.check_admin_permission():
            return Response(
                {"error": "Only forum admins can edit meetings"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.check_admin_permission():
            return Response(
                {"error": "Only forum admins can delete meetings"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def join(self, request, forum_id=None, pk=None):
        """Join a live meeting - with access control"""
        meeting = self.get_object()
        
        # Check if meeting is live
        if meeting.status != "LIVE":
            return Response(
                {"error": "Can only join live meetings"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is forum member
        try:
            ForumMembership.objects.get(
                user=request.user,
                forum=meeting.forum,
                is_active=True
            )
        except ForumMembership.DoesNotExist:
            return Response(
                {"error": "Only forum members can join meetings"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check participant access control
        if not meeting.is_all_members_allowed:
            # User must be in allowed_participants list
            if not meeting.allowed_participants.filter(id=request.user.id).exists():
                return Response(
                    {"error": "You are not invited to this meeting"},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Add participant
        participant, created = MeetingParticipant.objects.get_or_create(
            meeting=meeting,
            user=request.user,
            defaults={"is_currently_active": True}
        )
        
        if not created and not participant.is_currently_active:
            participant.is_currently_active = True
            participant.joined_at = timezone.now()
            participant.save()
        
        serializer = MeetingParticipantSerializer(participant)
        return Response({
            "message": "Joined meeting successfully",
            "participant": serializer.data,
            "room_id": meeting.room_id
        })

    @action(detail=True, methods=["post"])
    def leave(self, request, forum_id=None, pk=None):
        """Leave a meeting and calculate attendance"""
        meeting = self.get_object()
        
        try:
            participant = MeetingParticipant.objects.get(
                meeting=meeting,
                user=request.user
            )
            participant.is_currently_active = False
            participant.left_at = timezone.now()
            
            # Calculate duration
            if participant.joined_at:
                duration = (participant.left_at - participant.joined_at).total_seconds()
                participant.duration_seconds = int(duration)
            
            # Calculate meeting duration for attendance threshold
            meeting_start = meeting.scheduled_start
            meeting_end = meeting.get_current_end_time()
            
            if meeting_start and meeting_end:
                meeting_duration = (meeting_end - meeting_start).total_seconds()
                participant.calculate_attendance(meeting_duration)
            
            participant.save()
            
            return Response({
                "message": "Left meeting successfully",
                "is_marked_present": participant.is_marked_present,
                "presence_percentage": participant.presence_percentage
            })
        except MeetingParticipant.DoesNotExist:
            return Response(
                {"error": "You are not a participant in this meeting"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def extend_meeting(self, request, forum_id=None, pk=None):
        """Extend meeting duration (admin only)"""
        if not self.check_admin_permission():
            return Response(
                {"error": "Only forum admins can extend meetings"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        meeting = self.get_object()
        
        # Check if meeting is live
        if meeting.status != "LIVE":
            return Response(
                {"error": "Can only extend live meetings"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        duration_minutes = request.data.get("duration_minutes")
        
        # Validate duration
        if duration_minutes not in [15, 30, 60]:
            return Response(
                {"error": "Duration must be 15, 30, or 60 minutes"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from datetime import timedelta
        current_end = meeting.get_current_end_time()
        meeting.actual_end = current_end + timedelta(minutes=int(duration_minutes))
        meeting.save()
        
        serializer = MeetingDetailSerializer(meeting, context=self.get_serializer_context())
        return Response({
            "message": f"Meeting extended by {duration_minutes} minutes",
            "meeting": serializer.data
        })

    @action(detail=True, methods=["get"])
    def participants(self, request, forum_id=None, pk=None):
        """Get all participants in a meeting"""
        meeting = self.get_object()
        participants = meeting.participants.all()
        serializer = MeetingParticipantSerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def upload_minutes(self, request, forum_id=None, pk=None):
        """Upload meeting minutes (admin only)"""
        if not self.check_admin_permission():
            return Response(
                {"error": "Only forum admins can upload minutes"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        meeting = self.get_object()
        pdf_file = request.FILES.get("pdf_file")
        
        if not pdf_file:
            return Response(
                {"error": "PDF file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file type
        if not pdf_file.name.lower().endswith(".pdf"):
            return Response(
                {"error": "Only PDF files are allowed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update minutes
        minute, created = MeetingMinute.objects.get_or_create(
            meeting=meeting,
            defaults={
                "pdf_file": pdf_file,
                "uploaded_by": request.user
            }
        )
        
        if not created:
            minute.pdf_file = pdf_file
            minute.uploaded_by = request.user
            minute.save()
        
        serializer = MeetingMinuteSerializer(minute, context={"request": request})
        return Response({
            "message": "Minutes uploaded successfully",
            "minute": serializer.data
        })


class MeetingParticipantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing meeting participants.
    All authenticated members can view participants of meetings they have access to.
    """
    serializer_class = MeetingParticipantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs.get("meeting_id")
        return MeetingParticipant.objects.filter(
            meeting_id=meeting_id,
            is_currently_active=True
        ).order_by("-joined_at")


# ==================== NOTIFICATIONS ====================

class NotificationViewSet(viewsets.ViewSet):
    """API endpoints for notifications"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get all notifications for user (across all forums), ordered by newest first"""
        # Show all notifications by default, can filter with ?status=unread
        status = request.query_params.get('status', 'all')
        
        query = Notification.objects.filter(user=request.user)
        
        if status == 'unread':
            query = query.filter(is_read=False)
        elif status == 'read':
            query = query.filter(is_read=True)
        
        notifications = query.order_by("-created_at")
        
        serializer = NotificationListSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="forum/(?P<forum_id>[^/.]+)")
    def forum_notifications(self, request, forum_id=None):
        """Get all unread notifications for a specific forum"""
        forum = get_object_or_404(Forum, id=forum_id)
        notifications = Notification.objects.filter(
            user=request.user,
            forum=forum,
            is_read=False
        ).order_by("-created_at")
        
        serializer = NotificationListSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="counts")
    def unread_counts(self, request):
        """Get unread notification counts per forum and globally"""
        forums = Forum.objects.filter(
            memberships__user=request.user,
            memberships__is_active=True
        ).distinct()

        forum_counts = {}
        tab_counts = {}
        global_count = 0
        timestamp = timezone.now().isoformat()

        for forum in forums:
            forum_id_str = str(forum.id)
            
            # Get total count per forum
            forum_notifs = Notification.objects.filter(
                user=request.user,
                forum=forum,
                is_read=False
            )
            count = forum_notifs.count()
            forum_counts[forum_id_str] = count
            global_count += count
            
            # Get per-tab counts for this forum
            tab_counts[forum_id_str] = {}
            tab_breakdown = forum_notifs.values('tab').annotate(count=Count('id')).order_by('tab')
            
            for notif in tab_breakdown:
                if notif['tab']:
                    tab_counts[forum_id_str][notif['tab']] = notif['count']
            
            # Debug logging
            print(f"[{timestamp}] Counting for forum {forum.name} ({forum_id_str})")
            print(f"  Total unread: {count}")
            print(f"  By tab: {dict(tab_counts[forum_id_str])}")

        print(f"[{timestamp}] Final counts - Global: {global_count}, Forums: {len(forum_counts)}")
        return Response({
            "global_count": global_count,
            "forum_counts": forum_counts,
            "tab_counts": tab_counts
        })

    @action(detail=False, methods=["get"], url_path="tab")
    def tab_notifications(self, request):
        """Get all unread notifications for a specific tab in a forum"""
        forum_id = request.query_params.get("forum_id")
        tab = request.query_params.get("tab")
        limit = int(request.query_params.get("limit", 10))
        
        if not forum_id or not tab:
            return Response({
                "error": "forum_id and tab parameters required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        notifications = Notification.objects.filter(
            user=request.user,
            forum_id=forum_id,
            tab=tab,
            is_read=False
        ).order_by("-created_at")[:limit]
        
        serializer = NotificationListSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="mark-as-read")
    def mark_as_read(self, request):
        """Mark specific notifications as read"""
        notification_ids = request.data.get("notification_ids", [])
        
        if notification_ids:
            Notification.objects.filter(
                id__in=notification_ids,
                user=request.user
            ).update(is_read=True)

        return Response({"status": "notifications marked as read"})

    @action(detail=False, methods=["post"], url_path="clear-forum")
    def clear_forum_notifications(self, request):
        """Mark all notifications for a forum as read"""
        forum_id = request.data.get("forum_id")
        
        if forum_id:
            Notification.objects.filter(
                user=request.user,
                forum_id=forum_id,
                is_read=False
            ).update(is_read=True)

        return Response({"status": "forum notifications cleared"})

    @action(detail=False, methods=["post"], url_path="clear-tab")
    def clear_tab_notifications(self, request):
        """Mark all notifications for a specific tab in a forum as read"""
        forum_id = request.data.get("forum_id")
        tab = request.data.get("tab")
        
        print(f"[API-CLEAR-TAB] Clearing tab={tab} for forum={forum_id}, user={request.user.id}")
        
        if forum_id and tab:
            # Get count before clearing (for logging)
            before_count = Notification.objects.filter(
                user=request.user,
                forum_id=forum_id,
                tab=tab,
                is_read=False
            ).count()
            
            # Clear notifications
            updated = Notification.objects.filter(
                user=request.user,
                forum_id=forum_id,
                tab=tab,
                is_read=False
            ).update(is_read=True)
            
            print(f"[API-CLEAR-TAB] Marked {updated} notifications as read (was {before_count} unread)")
            
            return Response({
                "status": f"{tab} notifications cleared",
                "cleared_count": updated
            })
        
        return Response({"status": "no forum_id or tab provided"})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_single_as_read(self, request, pk=None):
        """Mark a single notification as read"""
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            serializer = NotificationListSerializer(notification)
            return Response(serializer.data)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["delete"])
    def destroy(self, request, pk=None):
        """Delete a single notification"""
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
            notification.delete()
            return Response({"status": "notification deleted"})
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class UserNotificationPreferenceView(APIView):
    """API endpoint for user notification preferences"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's notification preferences"""
        prefs, created = UserNotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = UserNotificationPreferenceSerializer(prefs)
        return Response(serializer.data)

    def put(self, request):
        """Update user's notification preferences"""
        prefs, created = UserNotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = UserNotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== ANNOUNCEMENTS (HANDLED BY VIEWSET ABOVE) ====================

# ==================== FORUM ACTIVITY HISTORY / GENERAL RECORDS ====================
class ForumActivityHistoryView(APIView):
    """API endpoint to fetch forum activity history for general records"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, forum_id):
        """Fetch activity history filtered by date range and tabs"""
        try:
            forum = Forum.objects.get(id=forum_id)
        except Forum.DoesNotExist:
            return Response({"error": "Forum not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is admin of this forum
        membership = ForumMembership.objects.filter(
            forum=forum,
            user=request.user
        ).first()
        
        if not membership:
            return Response(
                {"error": "You are not a member of this forum"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not membership.is_core_executive:
            return Response(
                {"error": "Only forum admins can access general records"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get query parameters
        date_from = request.query_params.get("date_from")  # YYYY-MM-DD
        date_to = request.query_params.get("date_to")      # YYYY-MM-DD
        tabs = request.query_params.getlist("tabs")        # e.g. ['feed', 'meetings']
        activity_type = request.query_params.get("activity_type")  # Optional filter by activity type
        search = request.query_params.get("search")        # Optional search in title/description
        
        # Build queryset
        queryset = ForumActivityHistory.objects.filter(forum=forum)
        
        # Filter by date range
        if date_from:
            from datetime import datetime
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(created_at__gte=date_from_obj)
            except ValueError:
                return Response(
                    {"error": "Invalid date_from format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if date_to:
            from datetime import datetime, timedelta
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                # Include the entire day
                date_to_obj = date_to_obj + timedelta(days=1)
                queryset = queryset.filter(created_at__lt=date_to_obj)
            except ValueError:
                return Response(
                    {"error": "Invalid date_to format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Filter by tabs (if specified)
        if tabs:
            queryset = queryset.filter(tab__in=tabs)
        
        # Filter by activity type (if specified)
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # Search in title and description
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        
        # Order by date (newest first by default, can be changed)
        order_by = request.query_params.get("order_by", "-created_at")
        if order_by in ["created_at", "-created_at"]:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by("-created_at")
        
        # Serialize and return
        serializer = ForumActivityHistorySerializer(queryset, many=True)
        
        return Response({
            "count": queryset.count(),
            "results": serializer.data,
            "forum": {
                "id": forum.id,
                "name": forum.name
            }
        })
