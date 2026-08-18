from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Forum
from wallet.models import Wallet


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def forum_wallet_view(request, forum_id):
    """Get wallet information for a forum (admin only)"""
    try:
        forum = Forum.objects.get(id=forum_id)
    except Forum.DoesNotExist:
        return Response({'error': 'Forum not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user is admin of the forum
    from .models import ForumMembership
    user_membership = ForumMembership.objects.filter(
        forum=forum,
        user=request.user,
        is_active=True
    ).first()
    if user_membership and not user_membership.is_core_executive:
        user_membership = None
    
    if not user_membership:
        return Response(
            {'error': 'You do not have permission to view wallet information'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        wallet = Wallet.objects.get(forum=forum)
        return Response({
            'id': str(wallet.id),
            'forum_id': str(wallet.forum.id),
            'balance': wallet.balance,
            'currency': 'NGN'
        })
    except Wallet.DoesNotExist:
        # Return zero balance if wallet doesn't exist
        return Response({
            'id': None,
            'forum_id': str(forum.id),
            'balance': 0,
            'currency': 'NGN'
        })
