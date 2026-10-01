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
                401: "Sign in to continue.",
                403: "Access denied.",
                404: "This resource was not found.",
                429: "Too many requests. Please try again later.",
            }
            original = response
            if original.status_code == 405:
                # Read-only content endpoints and the POST-only sign-in endpoints
                # need different advice, so take it from the Allow header.
                allowed = original.get("Allow", "")
                message = f"This endpoint accepts {allowed} requests only." if allowed else "This endpoint does not accept that request method."
            else:
                message = messages.get(original.status_code, "The learning service is temporarily unavailable.")
            response = JsonResponse({"message": message}, status=original.status_code)
            for header in ("Allow", "Retry-After"):
                if header in original:
                    response[header] = original[header]
        response["Cache-Control"] = "private, no-store"
        return response
