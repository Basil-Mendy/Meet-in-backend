from django.db.models import Q
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import Forum, ForumMembership, InboxFavorite, InboxMessage


class InboxOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = InboxFavorite.objects.filter(user=request.user).select_related("favorite_user", "favorite_forum")
        recent = InboxMessage.objects.filter(
            Q(recipient_user=request.user) | Q(sender_user=request.user)
        ).order_by("-created_at")[:20]

        return Response({
            "favorites": [
                {
                    "id": item.id,
                    "type": item.favorite_type,
                    "user_id": str(item.favorite_user.id) if item.favorite_user else None,
                    "forum_id": str(item.favorite_forum.id) if item.favorite_forum else None,
                    "name": (
                        item.favorite_user.get_full_name() or item.favorite_user.email
                        if item.favorite_user else item.favorite_forum.name
                    ),
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
                "user_id": str(item.favorite_user.id) if item.favorite_user else None,
                "forum_id": str(item.favorite_forum.id) if item.favorite_forum else None,
                "name": (item.favorite_user.get_full_name() or item.favorite_user.email) if item.favorite_user else item.favorite_forum.name,
            }
            for item in rows
        ])

    def post(self, request):
        favorite_type = (request.data.get("type") or "USER").upper()
        favorite_user_id = request.data.get("user_id")
        favorite_forum_id = request.data.get("forum_id")

        if favorite_type not in {"USER", "FORUM"}:
            return Response({"error": "Invalid favorite type."}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"user": request.user, "favorite_type": favorite_type}

        if favorite_type == "USER":
            if not favorite_user_id:
                return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            favorite_user = User.objects.filter(id=favorite_user_id).first()
            if not favorite_user:
                return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)
            payload["favorite_user"] = favorite_user
        else:
            if not favorite_forum_id:
                return Response({"error": "forum_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            favorite_forum = Forum.objects.filter(id=favorite_forum_id).first()
            if not favorite_forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_400_BAD_REQUEST)
            payload["favorite_forum"] = favorite_forum

        favorite, created = InboxFavorite.objects.get_or_create(**payload)
        return Response({
            "id": favorite.id,
            "type": favorite.favorite_type,
            "name": (favorite.favorite_user.get_full_name() or favorite.favorite_user.email) if favorite.favorite_user else favorite.favorite_forum.name,
            "created": created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        favorite_id = request.data.get("id")
        if not favorite_id:
            return Response({"error": "Favorite id is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = InboxFavorite.objects.filter(user=request.user, id=favorite_id).delete()
        return Response({"deleted": bool(deleted)})


class InboxMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        forum_id = request.query_params.get("forum_id")

        if forum_id:
            forum = Forum.objects.filter(id=forum_id).first()
            if not forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_404_NOT_FOUND)

            qs = InboxMessage.objects.filter(
                Q(sender_forum=forum) | Q(recipient_forum=forum)
            ).order_by("-created_at")

            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
            if not (membership and membership.is_core_executive):
                qs = qs.exclude(message_type="OFFICIAL")
        else:
            qs = InboxMessage.objects.filter(
                (
                    Q(sender_user=request.user, sender_type="USER", recipient_type="USER") |
                    Q(recipient_user=request.user, sender_type="USER", recipient_type="USER")
                ) &
                Q(sender_forum__isnull=True) &
                Q(recipient_forum__isnull=True)
            ).order_by("-created_at")

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
            })
        return Response(payload)


class InboxSendView(APIView):
    permission_classes = [IsAuthenticated]

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
            user_id = request.data.get("user_id")
            if not user_id:
                return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            recipient_user = User.objects.filter(id=user_id).first()
            if not recipient_user:
                return Response({"error": "Recipient user not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            forum_id = request.data.get("forum_id")
            if not forum_id:
                return Response({"error": "forum_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            recipient_forum = Forum.objects.filter(id=forum_id).first()
            if not recipient_forum:
                return Response({"error": "Recipient forum not found."}, status=status.HTTP_400_BAD_REQUEST)

        sender_user = None
        sender_forum = None
        sender_type = "USER"

        from_forum_id = request.data.get("from_forum_id")
        if from_forum_id:
            sender_forum = Forum.objects.filter(id=from_forum_id).first()
            if not sender_forum:
                return Response({"error": "Sender forum not found."}, status=status.HTTP_400_BAD_REQUEST)
            membership = ForumMembership.objects.filter(user=request.user, forum=sender_forum, is_active=True).first()
            if not membership or not membership.is_executive:
                return Response({"error": "Only forum executives can send messages on behalf of a forum."}, status=status.HTTP_403_FORBIDDEN)
            sender_type = "FORUM"
        else:
            sender_user = request.user

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

        return Response({
            "id": msg.id,
            "subject": msg.subject,
            "message_type": msg.message_type,
            "body": msg.body,
            "created_at": msg.created_at,
        }, status=status.HTTP_201_CREATED)


class InboxConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        peer_user_id = request.query_params.get("user_id")
        peer_forum_id = request.query_params.get("forum_id")

        qs = InboxMessage.objects.filter(
            Q(sender_user=request.user, recipient_user_id=peer_user_id, sender_type="USER", recipient_type="USER") |
            Q(recipient_user=request.user, sender_user_id=peer_user_id, sender_type="USER", recipient_type="USER")
        ).order_by("created_at")

        if peer_forum_id:
            forum = Forum.objects.filter(id=peer_forum_id).first()
            if not forum:
                return Response({"error": "Forum not found."}, status=status.HTTP_404_NOT_FOUND)

            qs = InboxMessage.objects.filter(Q(sender_forum=forum) | Q(recipient_forum=forum)).order_by("created_at")
            membership = ForumMembership.objects.filter(user=request.user, forum=forum, is_active=True).first()
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
            }
            for msg in qs
        ])
