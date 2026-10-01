import re
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator


def validate_material_content(uploaded_file):
    """Reject renamed non-documents. This is a format check, not a malware scanner."""
    # Previously saved files have already been checked; avoid fetching entire
    # private objects from S3 every time staff edit their metadata.
    if getattr(uploaded_file, "_committed", False):
        return
    extension = PurePosixPath(uploaded_file.name).suffix.lower()
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        signature = uploaded_file.read(8)
        if extension == ".pdf":
            valid = signature.startswith(b"%PDF-")
        elif extension == ".doc":
            valid = signature == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        elif extension == ".docx":
            uploaded_file.seek(0)
            with ZipFile(uploaded_file) as archive:
                names = set(archive.namelist())
                valid = {"[Content_Types].xml", "word/document.xml"}.issubset(names)
                valid = valid and not any(name.lower().endswith("vbaproject.bin") for name in names)
        else:
            return  # FileExtensionValidator supplies the extension-specific error.
    except (BadZipFile, OSError, ValueError):
        valid = False
    finally:
        uploaded_file.seek(position)
    if not valid:
        raise ValidationError("The file contents do not match an allowed PDF, DOC, or non-macro DOCX document.")


# --- Learner account fields -------------------------------------------------
# Sign-up asks for an email address and a phone number only. Both are stored in
# a normalized form so the record stays searchable and sign-in matches sign-up.
_PHONE_SEPARATORS = re.compile(r"[\s().\-]")
_PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")
_email_validator = EmailValidator(message="Enter a valid email address, for example ada@example.com.")


def normalize_email(value):
    """Lowercase and trim; the domain part of an email address is not case sensitive."""
    return (value or "").strip().lower()


def validate_learner_email(value):
    email = normalize_email(value)
    if not email:
        raise ValidationError("Enter the email address you want to sign in with.")
    if len(email) > 254:
        raise ValidationError("That email address is too long.")
    _email_validator(email)
    return email


def normalize_phone_number(value):
    """Drop spaces, brackets, dots, and dashes; keep an optional leading +."""
    return _PHONE_SEPARATORS.sub("", (value or "").strip())


def validate_learner_phone(value):
    """Accept local and international numbers without assuming a country code."""
    phone_number = normalize_phone_number(value)
    if not phone_number:
        raise ValidationError("Enter a phone number learners can be reached on.")
    if not _PHONE_PATTERN.match(phone_number):
        raise ValidationError("Enter a phone number with 7 to 15 digits, for example +234 803 123 4567.")
    return phone_number


def learner_password_validators(min_length=None):
    """Learner password rules, kept separate from the stricter staff policy."""
    return [
        MinimumLengthValidator(min_length=min_length or settings.LEARNER_PASSWORD_MIN_LENGTH),
        CommonPasswordValidator(),
        NumericPasswordValidator(),
    ]


def validate_learner_password(password, *, email="", phone_number="", min_length=None):
    password = password or ""
    validate_password(password, password_validators=learner_password_validators(min_length))
    # A password built from the details the learner just typed is easy to guess.
    local_part = normalize_email(email).partition("@")[0]
    phone_digits = re.sub(r"\D", "", phone_number or "")
    lowered = password.lower()
    if any(len(fragment) >= 4 and fragment in lowered for fragment in (local_part, phone_digits)):
        raise ValidationError("Your password cannot contain your email name or your phone number.")
