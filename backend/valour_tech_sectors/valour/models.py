from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models

MAX_MATERIAL_SIZE_BYTES = settings.MAX_COURSE_FILE_SIZE_MB * 1024 * 1024


def validate_material_size(uploaded_file):
    if uploaded_file.size > MAX_MATERIAL_SIZE_BYTES:
        raise ValidationError("Files must be 25 MB or smaller.")


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
        validators=[FileExtensionValidator(allowed_extensions=("pdf", "doc", "docx")), validate_material_size],
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
