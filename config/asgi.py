import os
import sys
import django

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# Direct stderr output - most reliable
sys.stderr.write("\n" + "="*60 + "\n")
sys.stderr.write("[ASGI] Starting application load\n")
sys.stderr.flush()

# 1. Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.stderr.write("[ASGI] DJANGO_SETTINGS_MODULE set\n")
sys.stderr.flush()

# 2. Initialize Django
sys.stderr.write("[ASGI] Running django.setup()...\n")
sys.stderr.flush()
django.setup()
sys.stderr.write("[ASGI] django.setup() complete\n")
sys.stderr.flush()

# 3. Get the HTTP ASGI application
django_asgi_app = get_asgi_application()
sys.stderr.write("[ASGI] HTTP ASGI app configured\n")
sys.stderr.flush()

# 4. Import local modules
sys.stderr.write("[ASGI] Importing websocket_urlpatterns...\n")
sys.stderr.flush()
from forums.routing import websocket_urlpatterns
sys.stderr.write("[ASGI] websocket_urlpatterns imported OK\n")
sys.stderr.flush()

# 5. Create the final application with error handling
sys.stderr.write("[ASGI] Creating ProtocolTypeRouter...\n")
sys.stderr.flush()

from channels.routing import URLRouter

# Wrap URLRouter to catch exceptions
def exception_handling_asgi(asgi_app):
    async def wrapped(scope, receive, send):
        try:
            sys.stderr.write(f"[ASGI-WRAPPED] scope type: {scope['type']}, path: {scope.get('path', 'N/A')}\n")
            sys.stderr.flush()
            return await asgi_app(scope, receive, send)
        except Exception as e:
            sys.stderr.write(f"[ASGI-ERROR] Exception in ASGI: {e}\n")
            import traceback
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            raise
    return wrapped

url_router = URLRouter(websocket_urlpatterns)
wrapped_router = exception_handling_asgi(url_router)

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': wrapped_router,
})
sys.stderr.write("="*60 + "\n")
sys.stderr.write("[ASGI] Application ready - listening for connections\n")
sys.stderr.write("="*60 + "\n")
sys.stderr.flush()