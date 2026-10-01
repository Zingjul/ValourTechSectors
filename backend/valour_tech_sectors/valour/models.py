import secrets
from datetime import timedelta
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import F
from django.utils import timezone

from .validators import (
    normalize_email,
    normalize_phone_number,
    validate_learner_phone,
    validate_material_content,
)


def validate_material_size(uploaded_file):
    if uploaded_file.size > settings.MAX_COURSE_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Files must be {settings.MAX_COURSE_FILE_SIZE_MB} MB or smaller.")


def material_upload_path(instance, filename):
    extension = PurePosixPath(filename).suffix.lower()
    return f"course-materials/{uuid4().hex}{extension}"


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.CharField(max_length=280, blank=True)
    description = models.TextField(blank=True, help_text="Plain text; formatting is handled by the site.")
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)
    estimated_minutes = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    ordering = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False)
    lock_notice = models.CharField(
        max_length=240,
        blank=True,
        default="This course is currently locked.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ordering", "title")
        indexes = [models.Index(fields=("is_published", "ordering"))]

    def __str__(self):
        return self.title


class Section(models.Model):
    course = models.ForeignKey(Course, related_name="sections", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=280, blank=True)
    ordering = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False)
    lock_notice = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ("ordering", "id")
        indexes = [models.Index(fields=("course", "is_published", "ordering"))]

    def __str__(self):
        return f"{self.course.title} · {self.title}"


class Lesson(models.Model):
    section = models.ForeignKey(Section, related_name="lessons", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.CharField(max_length=280, blank=True)
    notes = models.TextField(blank=True, help_text="Written lesson notes. HTML is escaped on the React site.")
    safety_notice = models.CharField(max_length=500, blank=True, help_text="Optional safety guidance shown before the lesson content.")
    estimated_minutes = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    ordering = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True, db_index=True)
    is_locked = models.BooleanField(default=False)
    lock_notice = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ordering", "title")
        indexes = [models.Index(fields=("section", "is_published", "ordering"))]

    def __str__(self):
        return self.title


class VideoLink(models.Model):
    class Platform(models.TextChoices):
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"

    lesson = models.ForeignKey(Lesson, related_name="videos", on_delete=models.CASCADE)
    title = models.CharField(max_length=160, blank=True, help_text="For example: Resistor colour code walkthrough")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    url = models.URLField(max_length=500, help_text="Paste the original public post/video URL.")
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("ordering", "id")

    def __str__(self):
        return self.title or f"{self.get_platform_display()} video for {self.lesson}"

    def clean(self):
        super().clean()
        if not self.url:
            return
        parsed = urlparse(self.url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        allowed_hosts = {
            self.Platform.YOUTUBE: ("youtube.com", "youtu.be"),
            self.Platform.TIKTOK: ("tiktok.com",),
            self.Platform.INSTAGRAM: ("instagram.com",),
            self.Platform.FACEBOOK: ("facebook.com", "fb.watch"),
        }
        if parsed.scheme != "https":
            raise ValidationError({"url": "Video links must use HTTPS."})
        domains = allowed_hosts.get(self.platform, ())
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains):
            raise ValidationError({"url": "The URL host does not match the selected video platform."})

    def embed_url(self):
        parsed = urlparse(self.url)
        host = (parsed.hostname or "").lower()
        path_parts = [part for part in parsed.path.split("/") if part]

        if self.platform == self.Platform.YOUTUBE:
            video_id = ""
            if host == "youtu.be":
                video_id = path_parts[0] if path_parts else ""
            elif host.endswith("youtube.com"):
                if parsed.path == "/watch":
                    video_id = parse_qs(parsed.query).get("v", [""])[0]
                elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
                    video_id = path_parts[1]
            if len(video_id) != 11 or not all(char.isalnum() or char in "_-" for char in video_id):
                return None
            return f"https://www.youtube-nocookie.com/embed/{video_id}"

        if self.platform == self.Platform.TIKTOK and "video" in path_parts:
            video_index = path_parts.index("video")
            video_id = path_parts[video_index + 1] if video_index + 1 < len(path_parts) else ""
            if video_id.isdigit():
                return f"https://www.tiktok.com/player/v1/{video_id}"

        if self.platform == self.Platform.FACEBOOK:
            query = urlencode({"href": self.url, "show_text": "0", "width": "560"})
            return f"https://www.facebook.com/plugins/video.php?{query}"

        # Instagram requires its platform embed markup and may require Meta oEmbed
        # configuration. Keep the source link available rather than injecting HTML.
        return None


class Material(models.Model):
    class Kind(models.TextChoices):
        PDF = "pdf", "PDF"
        WORD = "word", "Word document"

    lesson = models.ForeignKey(Lesson, related_name="materials", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=280, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(
        upload_to=material_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=("pdf", "doc", "docx")),
            validate_material_size,
            validate_material_content,
        ],
    )
    ordering = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True, db_index=True)
    is_locked = models.BooleanField(default=False)
    lock_notice = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("ordering", "title")

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.file and self.file.name:
            extension = PurePosixPath(self.file.name).suffix.lower()
            expected_kind = self.Kind.PDF if extension == ".pdf" else self.Kind.WORD
            if self.kind and self.kind != expected_kind:
                raise ValidationError({"kind": "Choose a material type that matches the uploaded file."})

    @property
    def file_extension(self):
        return PurePosixPath(self.file.name or "").suffix.lower().lstrip(".")


class SiteProfile(models.Model):
    """One editable record for real brand/contact details supplied by the owner."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    brand_name = models.CharField(max_length=120, default="ValourTech Sectors")
    tagline = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=40, blank=True)
    whatsapp_url = models.URLField(max_length=500, blank=True)
    contact_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site and contact details"
        verbose_name_plural = "site and contact details"

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Site details cannot be deleted; clear fields that should no longer appear.")

    def __str__(self):
        return self.brand_name


class SocialLink(models.Model):
    class Platform(models.TextChoices):
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        LINKEDIN = "linkedin", "LinkedIn"
        OTHER = "other", "Other"

    platform = models.CharField(max_length=20, choices=Platform.choices)
    label = models.CharField(max_length=100, blank=True, help_text="Optional account name shown on the site.")
    url = models.URLField(max_length=500)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("ordering", "platform", "id")

    def __str__(self):
        return self.label or self.get_platform_display()


class LearnerManager(BaseUserManager):
    """Learner accounts come from sign-up on the site; staff never invent them."""

    use_in_migrations = True

    def create_user(self, email, phone_number="", password=None, **extra_fields):
        email = normalize_email(email)
        if not email:
            raise ValueError("A learner account needs an email address.")
        extra_fields.setdefault("is_active", True)
        learner = self.model(email=email, phone_number=normalize_phone_number(phone_number), **extra_fields)
        learner.set_password(password)
        learner.save(using=self._db)
        return learner


class Learner(AbstractBaseUser):
    """A visitor who signed up to open lessons.

    Learners are deliberately separate from the staff accounts in
    ``django.contrib.auth``: they sign in with an email address, they can never
    reach /admin/, and the record kept for the owner is the email address, the
    phone number, and when they joined and last signed in.
    """

    email = models.EmailField(
        max_length=254,
        unique=True,
        help_text="Stored lowercased; this is what the learner signs in with.",
    )
    phone_number = models.CharField(
        max_length=32,
        validators=[validate_learner_phone],
        help_text="Contact number captured at sign-up, for example +234 803 123 4567.",
    )
    # AbstractBaseUser keeps is_active as a plain attribute; a real field lets
    # staff deactivate a learner while keeping their record.
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivated learners cannot sign in. The record is kept.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Failed sign-ins are counted per email address so a lockout survives across
    # workers and deploys without storing visitor IP addresses.
    failed_login_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    locked_until = models.DateTimeField(null=True, blank=True, editable=False)

    objects = LearnerManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    # Learners hold no Django permissions, so the admin and every permission
    # check keep answering "no" for a learner session.
    is_staff = False
    is_superuser = False

    class Meta:
        ordering = ("-created_at", "email")
        verbose_name = "learner"
        verbose_name_plural = "learners"

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = normalize_email(self.email)
        self.phone_number = normalize_phone_number(self.phone_number)

    def has_perm(self, perm, obj=None):
        return False

    def has_perms(self, perm_list, obj=None):
        return False

    def has_module_perms(self, app_label):
        return False

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def is_locked_out(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def lockout_seconds_remaining(self):
        if not self.is_locked_out():
            return 0
        return max(1, int((self.locked_until - timezone.now()).total_seconds()))

    def clear_expired_lockout(self):
        """A finished cooldown starts counting again from the next failure."""
        if not self.locked_until or self.is_locked_out():
            return
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

    def register_failed_attempt(self):
        # The counter is incremented in the database so concurrent attempts from
        # several workers cannot each read the same stale value.
        Learner.objects.filter(pk=self.pk).update(
            failed_login_attempts=F("failed_login_attempts") + 1,
            updated_at=timezone.now(),
        )
        self.refresh_from_db(fields=["failed_login_attempts", "updated_at"])
        if self.failed_login_attempts < settings.LEARNER_LOGIN_FAILURE_LIMIT:
            return
        self.locked_until = timezone.now() + timedelta(minutes=settings.LEARNER_LOGIN_LOCKOUT_MINUTES)
        self.save(update_fields=["locked_until", "updated_at"])

    def reset_failed_attempts(self):
        if not self.failed_login_attempts and not self.locked_until:
            return
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])


def default_invite_expiry():
    """When a freshly generated invitation link stops working.

    ``LEARNER_INVITE_VALID_DAYS`` of 0 means links stay usable until they are
    spent or revoked.
    """
    days = settings.LEARNER_INVITE_VALID_DAYS
    if days <= 0:
        return None
    return timezone.now() + timedelta(days=days)


class RegistrationInviteQuerySet(models.QuerySet):
    def available(self):
        """Links that could still register someone right now."""
        return self.filter(is_revoked=False, used_by__isnull=True).exclude(expires_at__lt=timezone.now())


class RegistrationInvite(models.Model):
    """A single-use link that admits exactly one person.

    Staff generate links in the admin and send them to whoever they choose. A
    link is spent the moment it creates an account, so forwarding it cannot
    admit a second person, and it can be revoked or left to expire.

    Tokens are stored as generated (256 bits of randomness) so a link can be
    copied again from the admin while it is still unused. They are never shown
    on the public site, and the admin-only ``note`` stays out of every API
    response.
    """

    token = models.CharField(max_length=64, unique=True, editable=False, db_index=True)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="A private reminder for staff, for example who this link was sent to. Never shown on the site.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_invites",
        editable=False,
        help_text="The staff account that generated this link.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Leave empty for a link that stays usable until it is spent or revoked.",
    )
    is_revoked = models.BooleanField(default=False, help_text="A revoked link stops working at once.")
    used_by = models.OneToOneField(
        "Learner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_invite",
        editable=False,
        help_text="The account this link created. A spent link cannot be used again.",
    )
    used_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = RegistrationInviteQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "registration invite"
        verbose_name_plural = "registration invites"

    def __str__(self):
        return self.note or f"Invite {self.short_token}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def short_token(self):
        return f"{self.token[:8]}…" if self.token else ""

    @property
    def is_used(self):
        return self.used_by_id is not None

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_available(self):
        return not (self.is_revoked or self.is_used or self.is_expired)

    @property
    def status(self):
        if self.is_revoked:
            return "revoked"
        if self.is_used:
            return "used"
        if self.is_expired:
            return "expired"
        return "available"

    @property
    def registration_path(self):
        """The relative path a link opens, so it works behind any hostname."""
        return f"/signup?invite={self.token}"

    def registration_url(self, request):
        return request.build_absolute_uri(self.registration_path)

    def consume(self, learner):
        """Spend the link on the account it just created."""
        self.used_by = learner
        self.used_at = timezone.now()
        self.save(update_fields=["used_by", "used_at"])
        return self
