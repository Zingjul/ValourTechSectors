"""Learner sign-up, sign-in, and session endpoints.

Registration is by invitation. Staff generate a single-use link in the admin
and send it to the person they want to admit; sign-up spends that link, records
an email address and a phone number plus the learner's own password, then starts
their session straight away so they land inside the site instead of on another
form. A link creates one account and then stops working, so forwarding it cannot
admit a second person. Sessions are cookie based on the same origin, so
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
from .models import Learner, RegistrationInvite
from .validators import (
    is_invite_token_shape,
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

# One wording per way a link can fail, so the sign-up page can explain itself
# instead of showing a form that is going to be refused. Nothing here reveals
# who used a link or which email addresses are registered.
INVITE_MESSAGES = {
    "missing": "Registration is by invitation. Ask the team to send you your personal link.",
    "unknown": "We could not find that invitation link. Ask the team to send you a new one.",
    "used": "That invitation link has already been used. Sign in, or ask the team for a new link.",
    "expired": "That invitation link has expired. Ask the team to send you a new one.",
    "revoked": "That invitation link was withdrawn. Ask the team if you still need access.",
}


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
            # And whether registration needs an invitation link.
            "registration": settings.LEARNER_REGISTRATION,
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


class InviteAlreadySpent(Exception):
    """Raised inside the sign-up transaction so the account is rolled back too."""

    def __init__(self, response):
        super().__init__("That invitation link can no longer register anyone.")
        self.response = response


def _invite_token(payload, request):
    """Take the token from the JSON body, or from ?invite= if a form posts it."""
    for value in (payload.get("invite"), request.GET.get("invite")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _invite_error(reason):
    return json_response(
        {
            "message": INVITE_MESSAGES.get(reason, INVITE_MESSAGES["unknown"]),
            "registration": settings.LEARNER_REGISTRATION,
            "invite_required": reason == "missing",
            "invite_invalid": reason != "missing",
            "reason": reason,
            "sign_in_path": SIGN_IN_PATH,
        },
        status=403,
    )


def resolve_invite(token):
    """Return ``(invite, reason)``; reason is empty when the link can register.

    Revoked beats used beats expired so the message a learner sees matches what
    staff did, whichever happened last.
    """
    if not is_invite_token_shape(token):
        return None, "unknown"
    invite = RegistrationInvite.objects.filter(token=token).first()
    if invite is None:
        return None, "unknown"
    return invite, "" if invite.is_available else invite.status


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

    # The invitation is checked before the fields: without a usable link there
    # is nothing to register, and the field rules stay private to invite holders.
    invite = None
    if settings.LEARNER_REGISTRATION == "invite":
        token = _invite_token(payload, request)
        if not token:
            return _invite_error("missing")
        invite, reason = resolve_invite(token)
        if reason:
            return _invite_error(reason)

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
            if invite is not None:
                # Re-read under a row lock: two people holding one forwarded
                # link must not both get an account from it.
                locked = RegistrationInvite.objects.select_for_update().filter(pk=invite.pk).first()
                if locked is None or not locked.is_available:
                    raise InviteAlreadySpent(_invite_error(locked.status if locked else "unknown"))
                invite = locked
            learner = Learner.objects.create_user(email=email, phone_number=phone_number, password=password)
            if invite is not None:
                invite.consume(learner)
    except InviteAlreadySpent as error:
        # Rolling back keeps the account out too: a spent link creates nobody.
        return error.response
    except IntegrityError:
        # Two sign-ups for one email can race; the first saved record wins. The
        # link is not spent, so the learner can try again with another address.
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
def invite_status(request, token):
    """Say whether an invitation link can still register someone.

    The sign-up page asks this before showing a form, so a learner who opens a
    spent or expired link is told plainly instead of being refused after typing
    their details. It answers about the token only: no learner details, and no
    way to discover which links exist.
    """
    if settings.LEARNER_REGISTRATION != "invite":
        return json_response(
            {
                "registration": settings.LEARNER_REGISTRATION,
                "valid": True,
                "message": "Anyone can register on this site.",
                "sign_in_path": SIGN_IN_PATH,
            }
        )

    invite, reason = resolve_invite(token)
    if reason:
        return json_response(
            {
                "registration": settings.LEARNER_REGISTRATION,
                "valid": False,
                "reason": reason,
                "message": INVITE_MESSAGES.get(reason, INVITE_MESSAGES["unknown"]),
                "sign_in_path": SIGN_IN_PATH,
            }
        )
    return json_response(
        {
            "registration": settings.LEARNER_REGISTRATION,
            "valid": True,
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            "message": "This invitation link is ready. Add your details to create your account.",
            "sign_in_path": SIGN_IN_PATH,
        }
    )


@require_GET
def current_session(request):
    """Answer the site's first question on load: is a learner signed in?"""
    return session_response(request, current_learner(request))
