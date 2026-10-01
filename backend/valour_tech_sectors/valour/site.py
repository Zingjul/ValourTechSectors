from functools import lru_cache

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_safe


@lru_cache(maxsize=1)
def _frontend_html():
    return (settings.FRONTEND_DIST / "index.html").read_text(encoding="utf-8")


@require_safe
def frontend(request, *, status=200):
    try:
        html = _frontend_html()
    except OSError:
        response = HttpResponse("The site is temporarily unavailable.", status=503, content_type="text/plain")
        response["Retry-After"] = "60"
    else:
        response = HttpResponse(html, status=status)
    response["Cache-Control"] = "no-store"
    response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not settings.DEBUG:
        response["Content-Security-Policy"] = settings.FRONTEND_CONTENT_SECURITY_POLICY
    return response


@require_safe
def robots(request):
    return HttpResponse(
        # The sign-in and sign-up pages are for people, not for search results.
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nDisallow: /media/\n"
        "Disallow: /signin\nDisallow: /signup\n",
        content_type="text/plain",
    )


def not_found(request, exception):
    # Missing API endpoints/assets must not be rewritten to the SPA with 200 OK.
    if request.path.startswith("/api/"):
        return JsonResponse({"message": "This resource was not found."}, status=404)
    if any(request.path == f"/{prefix}" or request.path.startswith(f"/{prefix}/") for prefix in ("admin", "static", "media")):
        return HttpResponse("Not found.", status=404, content_type="text/plain")
    return frontend(request, status=404)


def server_error(request):
    if request.path.startswith("/api/"):
        return JsonResponse({"message": "The learning service is temporarily unavailable."}, status=500)
    response = HttpResponse("The site is temporarily unavailable. Please try again later.", status=500, content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response
