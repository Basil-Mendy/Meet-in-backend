from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ForumMembership, Forum
from .membership_serializers import ForumMembershipSerializer
from .notification_service import NotificationService


class ForumMembersViewSet(viewsets.ModelViewSet):
    """ViewSet for managing forum members"""
    serializer_class = ForumMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        forum_id = self.kwargs.get('forum_id')
        return ForumMembership.objects.filter(forum_id=forum_id, is_active=True)

    def list(self, request, *args, **kwargs):
        """Get all members of a forum"""
        forum_id = self.kwargs.get('forum_id')
        try:
            forum = Forum.objects.get(id=forum_id)
        except Forum.DoesNotExist:
            return Response({'error': 'Forum not found'}, status=status.HTTP_404_NOT_FOUND)
        
        memberships = self.get_queryset()
        serializer = self.get_serializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def assign_role(self, request, *args, **kwargs):
        """Assign a role to a forum member (admin only)"""
        membership = self.get_object()
        forum_id = self.kwargs.get('forum_id')
        
        # Check if user is admin of the forum
        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            role__in=['SA', 'CP']
        ).first()
        
        if not user_membership:
            return Response(
                {'error': 'You do not have permission to assign roles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_role = request.data.get('role')
        # Get list of valid role codes from ROLE_CHOICES
        valid_roles = [choice[0] for choice in ForumMembership.ROLE_CHOICES]
        
        if new_role and new_role in valid_roles:
            old_role = membership.role
            membership.role = new_role
            membership.save()
            # Notify the forum about the role change
            try:
                NotificationService.create_forum_notifications(
                    forum=membership.forum,
                    notification_type='MEMBER_ROLE_ASSIGNED',
                    title=f"Member role changed in {membership.forum.name}",
                    message=f"{membership.user.get_full_name() or membership.user.email} role changed from {old_role} to {new_role}",
                    tab='members',
                    object_id=str(membership.id),
                    send_push=True,
                    send_email=False,
                )
            except Exception as e:
                print(f"[Notification] Failed to create member role notification: {e}")
            return Response(self.get_serializer(membership).data)
        
        return Response(
            {'error': f'Invalid role. Valid roles are: {valid_roles}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        """Remove a member from the forum"""
        membership = self.get_object()
        forum_id = self.kwargs.get('forum_id')
        
        # Check if user is admin of the forum
        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            role__in=['SA', 'CP']
        ).first()
        
        if not user_membership:
            return Response(
                {'error': 'You do not have permission to remove members'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        removed_user_name = membership.user.get_full_name() or membership.user.email
        membership.is_active = False
        membership.save()
        # Notify the forum that a member was removed
        try:
            NotificationService.create_forum_notifications(
                forum=membership.forum,
                notification_type='MEMBER_REMOVED',
                title=f"Member removed from {membership.forum.name}",
                message=f"{removed_user_name} has been removed from the forum",
                tab='members',
                object_id=str(membership.id),
                send_push=True,
                send_email=False,
            )
        except Exception as e:
            print(f"[Notification] Failed to create member removal notification: {e}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='open')
    def open_forum(self, request, *args, **kwargs):
        """Mark forum as opened today by current user (daily open bonus)."""
        forum_id = self.kwargs.get('forum_id')
        try:
            forum = Forum.objects.get(id=forum_id)
        except Forum.DoesNotExist:
            return Response({'error': 'Forum not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            activity = record_daily_open(request.user, forum)
            return Response({'status': 'ok', 'activity_score': activity.activity_score if activity else None})
        except Exception as e:
            print(f"[Activity] Failed to record daily open: {e}")
            return Response({'error': 'Failed to record activity'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
