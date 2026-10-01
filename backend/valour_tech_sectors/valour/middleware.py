from django.http import JsonResponse


class ApiResponseMiddleware:
    """Keep API errors machine-readable and access-controlled redirects uncached."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/api/"):
            return response
        if response.status_code >= 400 and not response.get("Content-Type", "").startswith("application/json"):
            messages = {
                400: "Invalid request.",
                403: "Access denied.",
                404: "This resource was not found.",
                405: "This endpoint only accepts GET and HEAD requests.",
                429: "Too many requests. Please try again later.",
            }
            original = response
            response = JsonResponse(
                {"message": messages.get(original.status_code, "The learning service is temporarily unavailable.")},
                status=original.status_code,
            )
            for header in ("Allow", "Retry-After"):
                if header in original:
                    response[header] = original[header]
        response["Cache-Control"] = "private, no-store"
        return response
