from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Course, Learner, Lesson, Material, Section, SiteProfile, SocialLink, VideoLink
from .validators import validate_learner_password


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("title", "description", "ordering", "is_published", "is_locked", "lock_notice")
    show_change_link = True


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = (
        "title",
        "slug",
        "estimated_minutes",
        "ordering",
        "is_published",
        "is_locked",
        "lock_notice",
    )
    show_change_link = True
    prepopulated_fields = {"slug": ("title",)}


class VideoLinkInline(admin.TabularInline):
    model = VideoLink
    extra = 0
    fields = ("title", "platform", "url", "ordering", "is_active")


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0
    fields = (
        "title",
        "description",
        "kind",
        "file",
        "ordering",
        "is_published",
        "is_locked",
        "lock_notice",
    )


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "is_published", "is_locked", "ordering", "updated_at")
    list_filter = ("is_published", "is_locked", "level")
    search_fields = ("title", "summary", "description")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("ordering", "title")
    inlines = (SectionInline,)
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "description")}),
        ("Learning details", {"fields": ("level", "estimated_minutes", "ordering")}),
        ("Availability", {"fields": ("is_published", "is_locked", "lock_notice")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "is_published", "is_locked", "ordering")
    list_filter = ("is_published", "is_locked", "course")
    search_fields = ("title", "course__title")
    ordering = ("course__ordering", "ordering")
    inlines = (LessonInline,)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "is_published", "is_locked", "ordering", "estimated_minutes")
    list_filter = ("is_published", "is_locked", "section__course", "section")
    search_fields = ("title", "summary", "notes", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("section__course__ordering", "section__ordering", "ordering")
    inlines = (VideoLinkInline, MaterialInline)
    fieldsets = (
        (None, {"fields": ("section", "title", "slug", "summary")}),
        ("Lesson content", {"fields": ("notes", "safety_notice")}),
        ("Timing and access", {"fields": ("estimated_minutes", "ordering", "is_published", "is_locked", "lock_notice")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(VideoLink)
class VideoLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "platform", "lesson", "is_active", "ordering")
    list_filter = ("platform", "is_active", "lesson__section__course")
    search_fields = ("title", "url", "lesson__title", "lesson__section__course__title")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "lesson", "is_published", "is_locked", "ordering")
    list_filter = ("kind", "is_published", "is_locked", "lesson__section__course")
    search_fields = ("title", "description", "lesson__title")


@admin.register(SiteProfile)
class SiteProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Brand", {"fields": ("brand_name", "tagline")}),
        ("Contact details", {"fields": ("contact_email", "phone_number", "whatsapp_url", "contact_note")}),
        ("Updated", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SiteProfile.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("platform", "label", "url", "is_active", "ordering")
    list_filter = ("platform", "is_active")
    search_fields = ("label", "url")
    ordering = ("ordering", "platform")


class LearnerPasswordForm(forms.Form):
    """Staff-assisted password reset for a learner account.

    The site has no email delivery configured yet, so a learner who forgets
    their password asks the team and a staff member sets a new one here. The
    learner rules apply, not the 12-character staff policy.
    """

    new_password1 = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=f"At least {settings.LEARNER_PASSWORD_MIN_LENGTH} characters, and not only numbers.",
    )
    new_password2 = forms.CharField(
        label="Confirm the new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, learner, *args, **kwargs):
        self.learner = learner
        super().__init__(*args, **kwargs)

    def clean_new_password2(self):
        password = self.cleaned_data.get("new_password1")
        confirmation = self.cleaned_data.get("new_password2")
        if password and confirmation and password != confirmation:
            raise ValidationError("The two passwords do not match.", code="password_mismatch")
        if password:
            try:
                validate_learner_password(password, email=self.learner.email, phone_number=self.learner.phone_number)
            except ValidationError as error:
                raise ValidationError(error.messages) from None
        return confirmation

    def save(self):
        self.learner.set_password(self.cleaned_data["new_password1"])
        self.learner.failed_login_attempts = 0
        self.learner.locked_until = None
        self.learner.save(update_fields=["password", "failed_login_attempts", "locked_until", "updated_at"])
        return self.learner


@admin.register(Learner)
class LearnerAdmin(admin.ModelAdmin):
    """The owner's record of everyone who signed up to learn."""

    list_display = ("email", "phone_number", "created_at", "last_login", "access_state")
    list_filter = ("is_active", "created_at", "last_login")
    search_fields = ("email", "phone_number")
    search_help_text = "Search the email address or phone number given at sign-up."
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_login",
        "failed_login_attempts",
        "locked_until",
        "password_link",
    )
    fieldsets = (
        ("Sign-up details", {"fields": ("email", "phone_number")}),
        ("Access", {"fields": ("is_active", "password_link")}),
        (
            "Sign-in activity",
            {
                "fields": ("last_login", "failed_login_attempts", "locked_until"),
                "classes": ("collapse",),
            },
        ),
        ("Record kept since", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ("unlock_sign_in",)

    def has_add_permission(self, request):
        # Accounts are created by sign-up on the site so the password is always
        # set by the learner themselves, never typed into the admin.
        return False

    def get_urls(self):
        return [
            path(
                "<path:object_id>/password/",
                self.admin_site.admin_view(self.set_password),
                name="valour_learner_password",
            ),
            *super().get_urls(),
        ]

    @admin.display(description="Access", ordering="is_active")
    def access_state(self, learner):
        if not learner.is_active:
            return "Deactivated"
        if learner.is_locked_out():
            locked_until = timezone.localtime(learner.locked_until).strftime("%d %b %Y, %H:%M")
            return format_html("Locked until {}", locked_until)
        return "Active"

    @admin.display(description="Sign-in password")
    def password_link(self, learner):
        url = reverse("admin:valour_learner_password", args=[learner.pk], current_app=self.admin_site.name)
        return format_html(
            '<a class="button" href="{}">Set a new sign-in password</a>'
            "<p class=\"help\">Hashed and never shown. Learners cannot recover it themselves yet.</p>",
            url,
        )

    @admin.action(description="Unlock sign-in and clear failed attempts")
    def unlock_sign_in(self, request, queryset):
        unlocked = 0
        for learner in queryset:
            if learner.failed_login_attempts or learner.locked_until:
                learner.reset_failed_attempts()
                unlocked += 1
        self.message_user(request, f"Sign-in unlocked for {unlocked} learner(s).", messages.SUCCESS)

    def set_password(self, request, object_id):
        learner = get_object_or_404(Learner, pk=object_id)
        if not self.has_change_permission(request, learner):
            raise PermissionDenied
        if request.method == "POST":
            form = LearnerPasswordForm(learner, request.POST)
            if form.is_valid():
                form.save()
                self.message_user(request, f"A new sign-in password was set for {learner.email}.", messages.SUCCESS)
                return HttpResponseRedirect(
                    reverse("admin:valour_learner_change", args=[learner.pk], current_app=self.admin_site.name)
                )
        else:
            form = LearnerPasswordForm(learner)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Set a new sign-in password for {learner.email}",
            "subtitle": None,
            "form": form,
            "original": learner,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request, learner),
            "has_change_permission": self.has_change_permission(request, learner),
        }
        return render(request, "admin/valour/learner/set_password.html", context)
