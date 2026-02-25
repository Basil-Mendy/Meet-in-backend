"""Views for Forum About tab"""
from rest_framework import viewsets, views, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Forum, ForumDocument, ForumSettings, ForumMembership, BankAccount
from .about_serializers import (
    ForumAboutSerializer, ForumDocumentSerializer,
    ForumSettingsSerializer, BankAccountSerializer
)
from .notification_service import NotificationService


class IsForumAdmin(permissions.BasePermission):
    """Check if user is an admin of the forum"""
    def has_permission(self, request, view):
        forum_id = view.kwargs.get('forum_id')
        if not forum_id:
            return False
        
        return ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            role__in=["SA", "CP"],
            is_active=True
        ).exists()


class ForumAboutView(views.APIView):
    """Get complete Forum About information"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, forum_id):
        """Get forum about information"""
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check membership
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ForumAboutSerializer(forum)
        return Response(serializer.data)


class ForumInfoEditView(views.APIView):
    """Edit forum information (Admin only)"""
    permission_classes = [permissions.IsAuthenticated, IsForumAdmin]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def patch(self, request, forum_id):
        """Update forum information"""
        forum = get_object_or_404(Forum, id=forum_id)
        
        editable_fields = [
            'name', 'slogan', 'motto', 'description', 'address',
            'email', 'phone', 'profile_picture', 'objectives_rules'
        ]
        
        # Track which fields were updated
        updated_fields = []
        # Only allow editing specified fields
        for field in editable_fields:
            if field in request.data:
                current_value = getattr(forum, field, None)
                new_value = request.data[field]
                if current_value != new_value:
                    updated_fields.append(field)
                setattr(forum, field, request.data[field])
        
        forum.save()
        
        # Notify members if any fields were updated
        if updated_fields:
            try:
                NotificationService.create_forum_notifications(
                    forum=forum,
                    notification_type='FORUM_INFO_UPDATED',
                    title=f"Forum information updated in {forum.name}",
                    message=f"The following information was updated: {', '.join(updated_fields)}",
                    tab='about',
                    object_id=str(forum.id),
                    send_push=True,
                    send_email=False,
                )
            except Exception as e:
                print(f"[Notification] Failed to create forum info update notification: {e}")
        
        serializer = ForumAboutSerializer(forum)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ForumSettingsEditView(views.APIView):
    """Edit forum settings (Admin only)"""
    permission_classes = [permissions.IsAuthenticated, IsForumAdmin]

    def patch(self, request, forum_id):
        """Update forum settings"""
        forum = get_object_or_404(Forum, id=forum_id)
        settings, _ = ForumSettings.objects.get_or_create(forum=forum)
        
        serializer = ForumSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForumDocumentViewSet(viewsets.ModelViewSet):
    """Manage forum documents (upload / delete)"""
    serializer_class = ForumDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        forum_id = self.kwargs.get('forum_id')
        return ForumDocument.objects.filter(forum_id=forum_id)

    def list(self, request, *args, **kwargs):
        """List all documents in forum (visible to all members)"""
        forum_id = self.kwargs.get('forum_id')
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check membership
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, is_active=True
        ).exists():
            return Response(
                {'error': 'You are not a member of this forum'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        documents = self.get_queryset()
        serializer = self.get_serializer(documents, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Upload a document (Admin only)"""
        forum_id = self.kwargs.get('forum_id')
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is forum admin
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, role__in=["SA", "CP"], is_active=True
        ).exists():
            return Response(
                {'error': 'You do not have permission to upload documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(forum=forum, uploaded_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Delete a document (Admin only)"""
        forum_id = self.kwargs.get('forum_id')
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if user is forum admin
        if not ForumMembership.objects.filter(
            forum=forum, user=request.user, role__in=["SA", "CP"], is_active=True
        ).exists():
            return Response(
                {'error': 'You do not have permission to delete documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)


class BankAccountView(views.APIView):
    """Manage bank account for forum"""
    permission_classes = [permissions.IsAuthenticated, IsForumAdmin]

    def get(self, request, forum_id):
        """Get forum bank account"""
        forum = get_object_or_404(Forum, id=forum_id)
        
        try:
            bank_account = forum.bank_account
            serializer = BankAccountSerializer(bank_account)
            return Response(serializer.data)
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'No bank account configured'},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request, forum_id):
        """Create or update forum bank account"""
        forum = get_object_or_404(Forum, id=forum_id)
        
        # Check if account holder name matches forum name
        account_holder_name = request.data.get('account_holder_name', '').strip()
        if account_holder_name.lower() != forum.name.lower():
            return Response(
                {'error': 'Bank account holder name must match forum name'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bank_account, created = BankAccount.objects.update_or_create(
            forum=forum,
            account_type="FORUM",
            defaults={
                'account_holder_name': account_holder_name,
                'account_number': request.data.get('account_number'),
                'bank_name': request.data.get('bank_name'),
                'bank_code': request.data.get('bank_code', ''),
            }
        )
        
        # Notify members about bank account update
        try:
            if created:
                message = f"Bank account configured for {forum.name}"
            else:
                message = f"Bank account information updated for {forum.name}"
            
            NotificationService.create_forum_notifications(
                forum=forum,
                notification_type='FORUM_INFO_UPDATED',
                title="Bank account update",
                message=message,
                tab='about',
                object_id=str(forum.id),
                send_push=True,
                send_email=False,
            )
        except Exception as e:
            print(f"[Notification] Failed to create bank account notification: {e}")
        
        serializer = BankAccountSerializer(bank_account)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
