from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from valour import site

admin.site.site_header = "ValourTech Sectors · Staff"
admin.site.site_title = "ValourTech administration"
admin.site.index_title = "Course and site management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("valour.urls")),
    path("robots.txt", site.robots, name="robots"),
    path("", site.frontend, name="frontend"),
    re_path(r"^(?:courses(?:/[-\w]+)?|lessons/[-\w]+|contact|signin|signup)/?$", site.frontend),
]

# Development only. Production never exposes local media paths.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "valour.site.not_found"
handler500 = "valour.site.server_error"
