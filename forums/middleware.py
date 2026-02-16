"""
JWT WebSocket Authentication Middleware for Django Channels

Replaces AuthMiddlewareStack with JWT validation from query parameters.
Extracts JWT token from ?token=... and validates it using SimpleJWT.
"""

import logging
import sys
from pathlib import Path
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# Debug log file
DEBUG_LOG = Path(__file__).parent.parent / "middleware_debug.log"

def debug_log(msg):
    """Write to both stderr and debug file"""
    sys.stderr.write(f"{msg}\n")
    sys.stderr.flush()
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


def jwt_auth_middleware(inner):
    """
    Function-based ASGI middleware for JWT WebSocket authentication.
    
    Wraps an ASGI application and adds JWT authentication to WebSocket connections.
    Extracts JWT token from query string (?token=...) and validates it.
    Sets scope["user"] to authenticated user or AnonymousUser if invalid.
    """
    
    async def middleware(scope, receive, send):
        """
        Process incoming connections with JWT authentication.
        
        Args:
            scope: ASGI scope dict
            receive: ASGI receive callable
            send: ASGI send callable
        """
        try:
            # Debug output
            debug_log(f"[MIDDLEWARE] *** CALLED *** - type: {scope['type']}")
            
            # Only process WebSocket connections
            if scope["type"] == "websocket":
                debug_log(f"[MIDDLEWARE] *** WEBSOCKET *** on path: {scope.get('path', 'N/A')}")
                
                # Authenticate user via JWT token
                debug_log("[MIDDLEWARE] About to call get_user_from_token...")
                
                scope["user"] = await get_user_from_token(scope)
                
                debug_log(f"[MIDDLEWARE] User authenticated: {scope['user']}")
            else:
                debug_log(f"[MIDDLEWARE] Not a WebSocket, type={scope['type']}")
            
            # Pass to inner ASGI app (URLRouter or consumer)
            debug_log("[MIDDLEWARE] Calling inner app...")
            return await inner(scope, receive, send)
        
        except Exception as e:
            debug_log(f"[MIDDLEWARE] EXCEPTION: {e}")
            debug_log(f"[MIDDLEWARE] Exception type: {type(e).__name__}")
            import traceback
            debug_log(traceback.format_exc())
            raise
    
    return middleware


@database_sync_to_async
def get_user_from_token(scope):
    """
    Extract JWT token from query string and retrieve user.
    
    Args:
        scope: ASGI scope dict
        
    Returns:
        User model instance if valid, AnonymousUser if invalid
    """
    try:
        # Decode query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        debug_log(f"[MIDDLEWARE] Query string: {query_string[:100]}")
        logger.debug(f"[WS] Query string: {query_string}")
        
        # Extract token from ?token=...
        if "token=" not in query_string:
            debug_log("[MIDDLEWARE] No token in query string")
            logger.warning("[WS] No token in query string")
            return AnonymousUser()
        
        token_string = query_string.split("token=")[1].split("&")[0]
        debug_log(f"[MIDDLEWARE] Extracted token (first 50 chars): {token_string[:50]}...")
        logger.debug(f"[WS] Extracted token (first 50 chars): {token_string[:50]}...")
        
        # Validate JWT token
        try:
            access_token = AccessToken(token_string)
            user_id = access_token["user_id"]
            debug_log(f"[MIDDLEWARE] Token decoded, user_id: {user_id}")
            logger.debug(f"[WS] Token decoded, user_id: {user_id}")
        except (InvalidToken, TokenError) as e:
            debug_log(f"[MIDDLEWARE] Token validation failed: {e}")
            logger.error(f"[WS] Token validation failed: {e}")
            return AnonymousUser()
        
        # Retrieve user from database
        from accounts.models import User
        
        try:
            user = User.objects.get(id=user_id)
            debug_log(f"[MIDDLEWARE] User fetched: {user.username}")
            logger.debug(f"[WS] User fetched: {user.username}")
            return user
        except User.DoesNotExist:
            debug_log(f"[MIDDLEWARE] User not found: {user_id}")
            logger.error(f"[WS] User not found: {user_id}")
            return AnonymousUser()
        
    except Exception as e:
        debug_log(f"[MIDDLEWARE] Error: {e}")
        logger.error(f"[WS] Middleware error: {e}", exc_info=True)
        return AnonymousUser()


