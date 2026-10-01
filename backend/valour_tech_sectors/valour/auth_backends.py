"""Learner authentication.

Learners sign in with an email address and a password. Staff keep signing in to
``/admin/`` with their ``auth.User`` accounts through ``ModelBackend``, so the
admin lockout policy and the 12-character staff password rule stay separate from
the learner experience. Like the rest of the project, no visitor IP address is
stored: lockouts are counted per email address.
"""

from django.contrib.auth.backends import BaseBackend

from .models import Learner
from .validators import normalize_email


class LearnerBackend(BaseBackend):
    """Email + password sign-in for learner accounts."""

    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email or not password:
            return None
        try:
            learner = Learner.objects.get(email=normalize_email(email))
        except Learner.DoesNotExist:
            # Hash once anyway so an unknown email does not answer faster than a
            # known one, which would make the account list easy to enumerate.
            Learner().set_password(password)
            return None
        if not learner.is_active:
            return None
        learner.clear_expired_lockout()
        if learner.is_locked_out():
            return None
        if not learner.check_password(password):
            learner.register_failed_attempt()
            return None
        learner.reset_failed_attempts()
        return learner

    def get_user(self, learner_id):
        try:
            learner = Learner.objects.get(pk=learner_id)
        except (Learner.DoesNotExist, TypeError, ValueError):
            return None
        # A learner deactivated while signed in loses access on their next request.
        return learner if learner.is_active else None


def current_learner(request):
    """Return the signed-in learner, or None for visitors and staff sessions."""
    user = getattr(request, "user", None)
    return user if isinstance(user, Learner) else None


def can_open_content(request):
    """True for a signed-in learner, and for staff who manage the content anyway."""
    user = getattr(request, "user", None)
    if isinstance(user, Learner):
        return True
    # The owner must not be locked out of their own published lessons while
    # reviewing the live site with an admin session.
    return bool(getattr(user, "is_staff", False) and getattr(user, "is_active", True))
