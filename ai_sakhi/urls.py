import sys

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('women_app.urls')),
]

# Local `runserver` should always render with CSS/JS even if a stray DEBUG=False
# environment variable is present on the machine.
if settings.DEBUG or "runserver" in sys.argv:
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            serve,
            {"document_root": settings.BASE_DIR / "women_app" / "static"},
        )
    ]
