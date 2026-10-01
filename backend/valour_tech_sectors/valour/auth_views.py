"""Learner sign-up, sign-in, and session endpoints.

Sign-up records an email address and a phone number plus the learner's own
password, then starts their session straight away so they land inside the site
instead of on another form. Sessions are cookie based on the same origin, so
every mutating call carries a CSRF token. The token travels in the JSON body
rather than a script-readable cookie because ``CSRF_COOKIE_HTTPONLY`` stays on.

Log lines stay free of email addresses and phone numbers: the database is the
record of who signed up.
"""

import json
import logging
import math

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST

from .auth_backends import current_learner
from .models import Learner
from .validators import (
    normalize_email,
    validate_learner_email,
    validate_learner_password,
    validate_learner_phone,
)
from .views import SIGN_IN_PATH, json_response

logger = logging.getLogger(__name__)

LEARNER_AUTH_BACKEND = "valour.auth_backends.LearnerBackend"
# A sign-up or sign-in body is a few hundred bytes; anything larger is a mistake
# or an attempt to make the process spend time on junk.
MAX_PAYLOAD_BYTES = 8 * 1024
MAX_PASSWORD_LENGTH = 200


def learner_payload(learner):
    """The learner details the site is allowed to show back to them."""
    return {
        "email": learner.email,
        "phone_number": learner.phone_number,
        "member_since": learner.created_at.date().isoformat() if learner.created_at else "",
        "last_sign_in": learner.last_login.date().isoformat() if learner.last_login else "",
    }


def session_response(request, learner, *, status=200):
    return json_response(
        {
            "authenticated": learner is not None,
            "learner": learner_payload(learner) if learner else None,
            # The site uses this to decide whether to show sign-in prompts.
            "content_access": settings.LEARNER_CONTENT_ACCESS,
            "sign_in_path": SIGN_IN_PATH,
            # login()/logout() rotate the CSRF secret, so hand back the new token.
            "csrf_token": get_token(request),
        },
        status=status,
    )


def _json_payload(request):
    """Return the JSON object body, or None when the request is not usable."""
    if request.content_type.split(";")[0].strip().lower() != "application/json":
        return None
    if len(request.body) > MAX_PAYLOAD_BYTES:
        return None
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _text(payload, key, limit=254):
    value = payload.get(key)
    return value.strip()[:limit] if isinstance(value, str) else ""


def _secret(payload, key):
    """Passwords are not stripped: a trailing space is the learner's choice."""
    value = payload.get(key)
    return value[:MAX_PASSWORD_LENGTH] if isinstance(value, str) else ""


def _wants_a_long_session(payload):
    remember = payload.get("remember")
    if remember is True:
        return True
    return isinstance(remember, str) and remember.strip().lower() in {"1", "true", "yes", "on"}


def _start_session(request, learner, payload):
    # login() cycles the session key, so a session that existed before sign-in
    # cannot be reused by whoever held it (session fixation).
    login(request, learner, backend=LEARNER_AUTH_BACKEND)
    if _wants_a_long_session(payload):
        request.session.set_expiry(settings.LEARNER_SESSION_REMEMBER_DAYS * 24 * 60 * 60)
    else:
        request.session.set_expiry(0)  # End with the browser, like a staff session.


def _email_taken_response():
    return json_response(
        {
            "message": "That email address already has an account. Sign in instead.",
            "errors": {"email": ["That email address already has an account."]},
            "account_exists": True,
        },
        status=409,
    )


def _sign_in_refused(email):
    learner = Learner.objects.filter(email=normalize_email(email)).first()
    if learner and learner.is_locked_out():
        seconds = learner.lockout_seconds_remaining()
        response = json_response(
            {
                "message": f"Too many sign-in attempts. Try again in {math.ceil(seconds / 60)} minutes.",
                "locked": True,
            },
            status=429,
        )
        response["Retry-After"] = str(seconds)
        return response
    # One message for a wrong password, a deactivated account, and an unknown
    # email, so sign-in cannot be used to list who has registered.
    return json_response(
        {
            "message": "That email address and password do not match our records.",
            "errors": {"password": "That email address and password do not match our records."},
        },
        status=401,
    )


@require_POST
def signup(request):
    if current_learner(request) is not None:
        return json_response(
            {"message": "You are already signed in. Sign out first to create another account."},
            status=409,
        )
    payload = _json_payload(request)
    if payload is None:
        return json_response({"message": "Send the sign-up details as JSON."}, status=400)

    email = _text(payload, "email")
    phone_number = _text(payload, "phone_number", limit=40)
    password = _secret(payload, "password")

    errors = {}
    try:
        email = validate_learner_email(email)
    except ValidationError as error:
        errors["email"] = error.messages
    try:
        phone_number = validate_learner_phone(phone_number)
    except ValidationError as error:
        errors["phone_number"] = error.messages
    try:
        validate_learner_password(password, email=email, phone_number=phone_number)
    except ValidationError as error:
        errors["password"] = error.messages
    if "confirm_password" in payload and _secret(payload, "confirm_password") != password:
        errors["confirm_password"] = ["The two passwords do not match."]
    if errors:
        return json_response({"message": "Please correct the highlighted fields.", "errors": errors}, status=400)

    if Learner.objects.filter(email=email).exists():
        return _email_taken_response()
    try:
        with transaction.atomic():
            learner = Learner.objects.create_user(email=email, phone_number=phone_number, password=password)
    except IntegrityError:
        # Two sign-ups for one email can race; the first saved record wins.
        return _email_taken_response()

    _start_session(request, learner, payload)
    logger.info("Learner account created.")
    return session_response(request, learner, status=201)


@require_POST
def signin(request):
    payload = _json_payload(request)
    if payload is None:
        return json_response({"message": "Send your sign-in details as JSON."}, status=400)

    email = _text(payload, "email")
    password = _secret(payload, "password")
    errors = {}
    if not email:
        errors["email"] = ["Enter your email address."]
    if not password:
        errors["password"] = ["Enter your password."]
    if errors:
        return json_response({"message": "Enter your email address and password.", "errors": errors}, status=400)

    learner = authenticate(request, email=email, password=password)
    if learner is None:
        logger.info("Learner sign-in refused.")
        return _sign_in_refused(email)

    _start_session(request, learner, payload)
    return session_response(request, learner)


@require_POST
def signout(request):
    logout(request)
    return session_response(request, None)


@require_GET
def current_session(request):
    """Answer the site's first question on load: is a learner signed in?"""
    return session_response(request, current_learner(request))
