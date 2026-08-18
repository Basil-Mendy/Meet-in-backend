# """
# URL configuration for config project.

# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/6.0/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """


from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import CustomTokenObtainPairView

FRONTEND_BUILD_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def serve_frontend(request, path=""):
    if path.startswith(("api/", "admin/", "static/", "media/")):
        raise Http404

    target_path = FRONTEND_BUILD_DIR / path
    if path and target_path.exists() and target_path.is_file():
        return serve(request, path, document_root=str(FRONTEND_BUILD_DIR))

    index_file = FRONTEND_BUILD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file.open("rb"), content_type="text/html")

    return HttpResponseNotFound("Frontend build not found. Run npm run build inside the frontend folder.")


urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/auth/', include('accounts.urls')),
    path('api/forums/', include('forums.urls')),
    path('api/inbox/', include('forums.inbox_urls')),
    path('api/alumni/', include('alumni.urls')),
    path('api/wallet/', include('wallet.urls')),
    path('api/payments/', include('payments.urls')),
    re_path(r'^(?!api/|admin/|static/|media/)(?P<path>.*)$', serve_frontend, name='frontend'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

