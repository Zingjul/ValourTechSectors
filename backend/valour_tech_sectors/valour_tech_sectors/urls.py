from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ValourTech Sectors · Staff"
admin.site.site_title = "ValourTech administration"
admin.site.index_title = "Course and site management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("valour.urls")),
]
