from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ForumMembership, Forum, ForumRoleDefinition
from .membership_serializers import ForumMembershipSerializer
from .notification_service import NotificationService
from .activity_service import record_daily_open


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
        serializer = self.get_serializer(memberships, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def assign_role(self, request, *args, **kwargs):
        """Assign a role to a forum member (admin only)"""
        membership = self.get_object()
        forum_id = self.kwargs.get('forum_id')
        
        # Check if user is an executive or moderator
        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            is_active=True,
        ).first()
        if not user_membership or not user_membership.is_executive:
            return Response(
                {'error': 'You do not have permission to assign roles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_role = request.data.get('role')
        valid_roles = []
        try:
            valid_roles = ForumMembership.valid_roles()
        except AttributeError:
            valid_roles = [choice[0] for choice in ForumMembership.ROLE_CHOICES]

        custom_role_exists = False
        if new_role:
            role_code = str(new_role).strip().upper()
            custom_role_exists = ForumRoleDefinition.objects.filter(
                forum_id=forum_id,
                code=role_code,
                is_active=True,
            ).exists()

        role_is_valid = bool(new_role) and (
            ForumMembership.is_valid_role(str(new_role).upper()) or custom_role_exists
        )

        if role_is_valid:
            old_role = membership.role
            if new_role != "MEMBER" and old_role == "MEMBER":
                executive_count = ForumMembership.objects.filter(
                    forum_id=forum_id,
                    is_active=True
                ).exclude(role="MEMBER").count()
                if executive_count >= 10:
                    return Response(
                        {'error': 'A forum can have at most 10 executives.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            membership.role = new_role.upper()
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
        
        # Check if user is an executive or moderator
        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            is_active=True,
        ).first()
        if not user_membership or not user_membership.is_executive:
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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='custom-roles')
    def custom_roles(self, request, *args, **kwargs):
        """List available custom roles for the forum."""
        forum_id = self.kwargs.get('forum_id')
        try:
            forum = Forum.objects.get(id=forum_id)
        except Forum.DoesNotExist:
            return Response({'error': 'Forum not found'}, status=status.HTTP_404_NOT_FOUND)

        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            is_active=True,
        ).first()
        if not user_membership or not user_membership.is_executive:
            return Response({'error': 'You do not have permission to view custom roles'}, status=status.HTTP_403_FORBIDDEN)

        roles = ForumRoleDefinition.objects.filter(forum=forum, is_active=True)
        payload = [
            {
                'id': str(role.id),
                'name': role.name,
                'code': role.code,
                'role_type': role.role_type,
                'permissions': role.permissions,
            }
            for role in roles
        ]
        return Response(payload)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='create-custom-role')
    def create_custom_role(self, request, *args, **kwargs):
        """Create a new custom role definition for the forum."""
        forum_id = self.kwargs.get('forum_id')
        try:
            forum = Forum.objects.get(id=forum_id)
        except Forum.DoesNotExist:
            return Response({'error': 'Forum not found'}, status=status.HTTP_404_NOT_FOUND)

        user_membership = ForumMembership.objects.filter(
            forum_id=forum_id,
            user=request.user,
            is_active=True,
        ).first()
        if not user_membership or not user_membership.is_executive:
            return Response({'error': 'You do not have permission to create custom roles'}, status=status.HTTP_403_FORBIDDEN)

        name = (request.data.get('name') or '').strip()
        role_type = (request.data.get('role_type') or 'EXECUTIVE').strip().upper()
        permissions = request.data.get('permissions') or []
        if not name:
            return Response({'error': 'Role name is required'}, status=status.HTTP_400_BAD_REQUEST)
        if role_type not in {'CORE_EXECUTIVE', 'EXECUTIVE'}:
            return Response({'error': 'Invalid role type'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(permissions, list):
            return Response({'error': 'Permissions must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        code = (request.data.get('code') or name.replace(' ', '_').upper()).strip()
        if len(code) > 20:
            code = code[:20]

        role = ForumRoleDefinition.objects.create(
            forum=forum,
            name=name,
            code=code,
            role_type=role_type,
            permissions=permissions,
            created_by=request.user,
        )
        return Response({
            'id': str(role.id),
            'name': role.name,
            'code': role.code,
            'role_type': role.role_type,
            'permissions': role.permissions,
        })

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
