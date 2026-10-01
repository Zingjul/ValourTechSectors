"""Shared fixtures for tests that need a learner account.

Named without a ``test`` prefix so Django's test runner does not import it as a
test module.
"""

import json

from .auth_views import LEARNER_AUTH_BACKEND
from .models import Learner, RegistrationInvite, default_invite_expiry

LEARNER_EMAIL = "ada@example.com"
LEARNER_PHONE = "+234 803 123 4567"
LEARNER_PHONE_NORMALIZED = "+2348031234567"
LEARNER_PASSWORD = "resistor-colour-code"

# Sign-up spends an invitation link, so tests that register successfully need a
# fresh one each time. Pass NO_INVITE to leave the token out of a payload.
NO_INVITE = object()
_UNSET = object()


def json_body(payload):
    return json.dumps(payload)


def create_learner(email=LEARNER_EMAIL, phone_number=LEARNER_PHONE, password=LEARNER_PASSWORD):
    return Learner.objects.create_user(email=email, phone_number=phone_number, password=password)


def create_invite(note="", expires_at=_UNSET, created_by=None):
    """A fresh, unused registration link.

    ``expires_at=None`` makes one that never expires on its own; leaving it out
    applies the configured default, the way the admin does.
    """
    if expires_at is _UNSET:
        expires_at = default_invite_expiry()
    return RegistrationInvite.objects.create(note=note, expires_at=expires_at, created_by=created_by)


def sign_in(client, learner=None, password=LEARNER_PASSWORD):
    """Sign in through the real endpoint so the shipped flow is what gets tested."""
    learner = learner or create_learner()
    response = client.post(
        "/api/v1/auth/signin/",
        data=json_body({"email": learner.email, "password": password}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    return learner


def force_sign_in(client, learner=None):
    """Attach a learner session directly, for tests that only need to be signed in.

    The backend is named because django-axes comes first in
    AUTHENTICATION_BACKENDS and would otherwise be chosen for the session.
    """
    learner = learner or create_learner()
    client.force_login(learner, backend=LEARNER_AUTH_BACKEND)
    return learner
