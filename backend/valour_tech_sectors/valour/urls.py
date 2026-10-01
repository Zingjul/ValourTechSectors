from django.urls import path

from . import views

app_name = "valour"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("ready/", views.ready, name="ready"),
    path("courses/", views.course_list, name="course-list"),
    path("courses/<slug:slug>/", views.course_detail, name="course-detail"),
    path("lessons/<slug:slug>/", views.lesson_detail, name="lesson-detail"),
    path("materials/<int:pk>/download/", views.material_download, name="material-download"),
    path("site-profile/", views.site_profile, name="site-profile"),
]
