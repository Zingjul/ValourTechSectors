from django.urls import path

from . import auth_views, views

app_name = "valour"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("ready/", views.ready, name="ready"),
    path("auth/signup/", auth_views.signup, name="auth-signup"),
    path("auth/signin/", auth_views.signin, name="auth-signin"),
    path("auth/signout/", auth_views.signout, name="auth-signout"),
    path("auth/session/", auth_views.current_session, name="auth-session"),
    path("auth/invite/<str:token>/", auth_views.invite_status, name="auth-invite"),
    path("courses/", views.course_list, name="course-list"),
    path("courses/<slug:slug>/", views.course_detail, name="course-detail"),
    path("lessons/<slug:slug>/", views.lesson_detail, name="lesson-detail"),
    path("materials/<int:pk>/download/", views.material_download, name="material-download"),
    path("site-profile/", views.site_profile, name="site-profile"),
]
