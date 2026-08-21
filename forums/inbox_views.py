from django.db.models import Q
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.models import User
from .models import Forum, ForumMembership, InboxFavorite, InboxMessage, InboxMessageAttachment


def user_display_name(user):
    if not user:
        return ""
    return " ".join(filter(None, [user.first_name, user.last_name])).strip() or user.email


def active_forum_ids(user):
    return ForumMembership.objects.filter(user=user, is_active=True).values_list("forum_id", flat=True)


def shared_forum_exists(first_user, second_user):
    return ForumMembership.objects.filter(
        user=first_user,
        is_active=True,
        forum__memberships__user=second_user,
        forum__memberships__is_active=True,
    ).exists()


def user_inbox_queryset(user):
    member_forums = active_forum_ids(user)
    base = InboxMessage.objects.filter(
        Q(sender_user=user, sender_type="USER", recipient_type="USER") |
        Q(recipient_user=user, sender_forum__in=member_forums) |
        Q(sender_user=user, recipient_forum__in=member_forums)
    )
    core_roles = ForumMembership.CORE_EXECUTIVE_ROLES
    return base.filter(
        ~Q(message_type="OFFICIAL") |
        Q(message_type="OFFICIAL", sender_forum__memberships__user=user,
          sender_forum__memberships__is_active=True,
          sender_forum__memberships__role__in=list(core_roles))
    ).distinct()


class InboxOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = InboxFavorite.objects.filter(user=request.user).select_related("favorite_user", "favorite_forum")
        recent = user_inbox_queryset(request.user).order_by("-created_at")[:20]

        return Response({
            "favorites": [
                {
                    "id": item.id,
                    "type": item.favorite_type,
                    "username": item.favorite_user.profile.username if item.favorite_user and hasattr(item.favorite_user, "profile") else None,
                    "forum_id": item.favorite_forum.forum_id if item.favorite_forum else None,
                    "name": user_display_name(item.favorite_user) if item.favorite_user else item.favorite_forum.name,
                }
                for item in favorites
            ],
            "recent": [
                {
                    "id": msg.id,
                    "subject": msg.subject or "Message",
                    "body": msg.body,
                    "message_type": msg.message_type,
                    "sender_type": msg.sender_type,
                    "sender_user_id": str(msg.sender_user.id) if msg.sender_user else None,
                    "sender_forum_id": str(msg.sender_forum.id) if msg.sender_forum else None,
                    "recipient_user_id": str(msg.recipient_user.id) if msg.recipient_user else None,
                    "recipient_forum_id": str(msg.recipient_forum.id) if msg.recipient_forum else None,
                    "created_at": msg.created_at,
                    "is_read": msg.is_read,
                    "attachments": [
                        {"id": str(item.id), "filename": item.filename, "url": item.file.url}
                        for item in msg.attachments.all()
                    ],
                }
                for msg in recent
            ],
        })


class InboxFavoritesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = InboxFavorite.objects.filter(user=request.user).select_related("favorite_user", "favorite_forum")
        return Response([
            {
                "id": item.id,
                "type": item.favorite_type,
                "username": item.favorite_user.profile.username if item.favorite_user and hasattr(item.favorite_user, "profile") else None,
                "forum_id": item.favorite_forum.forum_id if item.favorite_forum else None,
                "name": user_display_name(item.favorite_user) if item.favorite_user else item.favorite_forum.name,
            }
            for item in rows
        ])

    def post(self, request):
        favorite_type = (request.data.get("type") or "USER").upper()
        username = (request.data.get("username") or "").strip()
        favorite_forum_id = request.data.get("forum_id")

        if favorite_type not in {"USER", "FORUM"}:
            return Response({"error": "Invalid favorite type."}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"user": request.user, "favorite_type": favorite_type}

        if favorite_type == "USER":
            if not username:
                return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)
            favorite_user = User.objects.filter(profile__username__iexact=username).first()
            if not favorite_user:
                return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)
            if not shared_forum_exists(request.user, favorite_user):
                return Response({"error": "You can only contact a user who shares a forum with you."}, status=status.HTTP_403_FORBIDDEN)
            payload["favorite_user"] = favorite_user
        else:
            if not favorite_forum_id:
                return Response({"error": "forum_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            favorite_forum = Forum.objects.filter(forum_id__iexact=favorite_forum_id).first()
            if not favorite_forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_400_BAD_REQUEST)
            if not ForumMembership.objects.filter(user=request.user, forum=favorite_forum, is_active=True).exists():
                return Response({"error": "You can only contact a forum you belong to."}, status=status.HTTP_403_FORBIDDEN)
            payload["favorite_forum"] = favorite_forum

        favorite, created = InboxFavorite.objects.get_or_create(**payload)
        return Response({
            "id": favorite.id,
            "type": favorite.favorite_type,
            "username": favorite.favorite_user.profile.username if favorite.favorite_user and hasattr(favorite.favorite_user, "profile") else None,
            "name": user_display_name(favorite.favorite_user) if favorite.favorite_user else favorite.favorite_forum.name,
            "created": created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        favorite_id = request.data.get("id")
        if not favorite_id:
            return Response({"error": "Favorite id is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = InboxFavorite.objects.filter(user=request.user, id=favorite_id).delete()
        return Response({"deleted": bool(deleted)})


class InboxRecipientLookupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recipient_type = (request.query_params.get("type") or "").upper()
        value = (request.query_params.get("value") or "").strip()

        if recipient_type not in {"USER", "FORUM"} or not value:
            return Response({"detail": "type and value are required."}, status=status.HTTP_400_BAD_REQUEST)

        if recipient_type == "USER":
            recipient = User.objects.filter(profile__username__iexact=value).select_related("profile").first()
            if recipient:
                if not shared_forum_exists(request.user, recipient):
                    return Response({"detail": "You can only contact a user who shares a forum with you."}, status=status.HTTP_403_FORBIDDEN)

                return Response({
                    "type": "USER",
                    "username": recipient.profile.username,
                    "name": " ".join(filter(None, [recipient.first_name, recipient.last_name])).strip(),
                })

            suggestions = []
            for candidate in User.objects.filter(
                profile__username__istartswith=value,
                profile__username__isnull=False,
            ).select_related("profile").order_by("profile__username")[:8]:
                if shared_forum_exists(request.user, candidate):
                    suggestions.append({
                        "type": "USER",
                        "username": candidate.profile.username,
                        "name": " ".join(filter(None, [candidate.first_name, candidate.last_name])).strip(),
                    })

            if suggestions:
                return Response({"type": "USER", "suggestions": suggestions})
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        forum = Forum.objects.filter(forum_id__iexact=value).first()
        if forum:
            if not ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).exists():
                return Response({"detail": "You can only contact a forum you belong to."}, status=status.HTTP_403_FORBIDDEN)

            return Response({
                "type": "FORUM",
                "forum_id": forum.forum_id,
                "name": forum.name,
            })

        suggestions = [
            {"type": "FORUM", "forum_id": item.forum_id, "name": item.name}
            for item in Forum.objects.filter(
                forum_id__istartswith=value,
                memberships__user=request.user,
                memberships__is_active=True,
            ).distinct().order_by("forum_id")[:8]
        ]
        if suggestions:
            return Response({"type": "FORUM", "suggestions": suggestions})
        return Response({"detail": "Forum not found."}, status=status.HTTP_404_NOT_FOUND)


class InboxMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        forum_id = request.query_params.get("forum_id")

        if forum_id:
            forum = Forum.objects.filter(forum_id__iexact=forum_id).first()
            if not forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_404_NOT_FOUND)

            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not membership:
                return Response({"error": "You can only access a forum inbox if you belong to that forum."}, status=status.HTTP_403_FORBIDDEN)

            qs = InboxMessage.objects.filter(
                Q(sender_forum=forum) | Q(recipient_forum=forum)
            ).order_by("-created_at")

            if not (membership and membership.is_core_executive):
                qs = qs.exclude(message_type="OFFICIAL")
        else:
            qs = user_inbox_queryset(request.user).order_by("-created_at")

        payload = []
        for msg in qs:
            payload.append({
                "id": msg.id,
                "subject": msg.subject or "Message",
                "body": msg.body,
                "message_type": msg.message_type,
                "sender_type": msg.sender_type,
                "sender_user_id": str(msg.sender_user.id) if msg.sender_user else None,
                "sender_forum_id": str(msg.sender_forum.id) if msg.sender_forum else None,
                "recipient_user_id": str(msg.recipient_user.id) if msg.recipient_user else None,
                "recipient_forum_id": str(msg.recipient_forum.id) if msg.recipient_forum else None,
                "created_at": msg.created_at,
                "is_read": msg.is_read,
                "attachments": [
                    {"id": str(item.id), "filename": item.filename, "url": item.file.url}
                    for item in msg.attachments.all()
                ],
            })
        return Response(payload)


class InboxSendView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        body = request.data.get("body", "").strip()
        subject = (request.data.get("subject") or "").strip()
        message_type = (request.data.get("message_type") or "UNOFFICIAL").upper()
        recipient_type = (request.data.get("recipient_type") or "USER").upper()

        if not body:
            return Response({"error": "Message body is required."}, status=status.HTTP_400_BAD_REQUEST)
        if message_type not in {"OFFICIAL", "UNOFFICIAL"}:
            return Response({"error": "message_type must be OFFICIAL or UNOFFICIAL."}, status=status.HTTP_400_BAD_REQUEST)
        if recipient_type not in {"USER", "FORUM"}:
            return Response({"error": "recipient_type must be USER or FORUM."}, status=status.HTTP_400_BAD_REQUEST)

        recipient_user = None
        recipient_forum = None

        if recipient_type == "USER":
            username = (request.data.get("username") or "").strip()
            if not username:
                return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)
            recipient_user = User.objects.filter(profile__username__iexact=username).first()
            if not recipient_user:
                return Response({"error": "Recipient user not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            forum_id = request.data.get("forum_id")
            if not forum_id:
                return Response({"error": "forum_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            recipient_forum = Forum.objects.filter(forum_id__iexact=forum_id).first()
            if not recipient_forum:
                return Response({"error": "Recipient forum not found."}, status=status.HTTP_400_BAD_REQUEST)

        sender_user = None
        sender_forum = None
        sender_type = "USER"

        from_forum_id = request.data.get("from_forum_id")
        if from_forum_id:
            sender_forum = Forum.objects.filter(forum_id__iexact=from_forum_id).first()
            if not sender_forum:
                return Response({"error": "Sender forum not found."}, status=status.HTTP_400_BAD_REQUEST)
            membership = ForumMembership.objects.filter(user=request.user, forum=sender_forum, is_active=True).first()
            if not membership or not membership.is_executive:
                return Response({"error": "Only forum executives can send messages on behalf of a forum."}, status=status.HTTP_403_FORBIDDEN)
            sender_type = "FORUM"
        else:
            sender_user = request.user

        if recipient_forum and not ForumMembership.objects.filter(user=request.user, forum=recipient_forum, is_active=True).exists():
            return Response({"error": "You can only send messages to a forum you belong to."}, status=status.HTTP_403_FORBIDDEN)

        if recipient_user:
            if sender_forum:
                allowed = ForumMembership.objects.filter(user=recipient_user, forum=sender_forum, is_active=True).exists()
            else:
                allowed = shared_forum_exists(request.user, recipient_user)
            if not allowed:
                return Response({"error": "You can only contact a user who shares a forum with you."}, status=status.HTTP_403_FORBIDDEN)

        msg = InboxMessage.objects.create(
            sender_user=sender_user,
            sender_forum=sender_forum,
            sender_type=sender_type,
            recipient_user=recipient_user,
            recipient_forum=recipient_forum,
            recipient_type=recipient_type,
            message_type=message_type,
            subject=subject or "New message",
            body=body,
        )

        for uploaded_file in request.FILES.getlist("attachments"):
            InboxMessageAttachment.objects.create(
                message=msg,
                file=uploaded_file,
                filename=uploaded_file.name,
                content_type=getattr(uploaded_file, "content_type", "") or "",
                size=uploaded_file.size,
            )

        return Response({
            "id": msg.id,
            "subject": msg.subject,
            "message_type": msg.message_type,
            "body": msg.body,
            "created_at": msg.created_at,
            "attachments": [
                {"id": str(item.id), "filename": item.filename, "url": item.file.url}
                for item in msg.attachments.all()
            ],
        }, status=status.HTTP_201_CREATED)


class InboxConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        peer_username = request.query_params.get("username")
        peer_forum_id = request.query_params.get("forum_id")
        peer_user = User.objects.filter(profile__username__iexact=peer_username).first() if peer_username else None

        if peer_username and not peer_user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if peer_user and not shared_forum_exists(request.user, peer_user):
            return Response({"error": "You can only contact a user who shares a forum with you."}, status=status.HTTP_403_FORBIDDEN)

        qs = InboxMessage.objects.filter(
            Q(sender_user=request.user, recipient_user=peer_user, sender_type="USER", recipient_type="USER") |
            Q(recipient_user=request.user, sender_user=peer_user, sender_type="USER", recipient_type="USER")
        ).order_by("created_at")

        if peer_forum_id:
            forum = Forum.objects.filter(forum_id__iexact=peer_forum_id).first()
            if not forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_404_NOT_FOUND)
            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not membership:
                return Response({"error": "You can only contact a forum you belong to."}, status=status.HTTP_403_FORBIDDEN)

            qs = InboxMessage.objects.filter(Q(sender_forum=forum) | Q(recipient_forum=forum)).order_by("created_at")
            if not (membership and membership.is_core_executive):
                qs = qs.exclude(message_type="OFFICIAL")

        return Response([
            {
                "id": msg.id,
                "subject": msg.subject or "Message",
                "body": msg.body,
                "message_type": msg.message_type,
                "sender_type": msg.sender_type,
                "sender_user_id": str(msg.sender_user.id) if msg.sender_user else None,
                "sender_forum_id": str(msg.sender_forum.id) if msg.sender_forum else None,
                "recipient_user_id": str(msg.recipient_user.id) if msg.recipient_user else None,
                "recipient_forum_id": str(msg.recipient_forum.id) if msg.recipient_forum else None,
                "created_at": msg.created_at,
                "is_read": msg.is_read,
                "attachments": [
                    {"id": str(item.id), "filename": item.filename, "url": item.file.url}
                    for item in msg.attachments.all()
                ],
            }
            for msg in qs
        ])
