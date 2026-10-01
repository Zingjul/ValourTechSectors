from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Course,
    Learner,
    Lesson,
    Material,
    RegistrationInvite,
    Section,
    SiteProfile,
    SocialLink,
    VideoLink,
    default_invite_expiry,
)
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
        "invite_record",
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
        (
            "Record kept since",
            {"fields": ("created_at", "updated_at", "invite_record"), "classes": ("collapse",)},
        ),
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

    @admin.display(description="Invitation")
    def invite_record(self, learner):
        """Which link admitted this learner, so access can be traced back to staff."""
        # A reverse one-to-one raises an AttributeError subclass when unused, so
        # getattr is enough to ask "was there one?".
        invite = getattr(learner, "registration_invite", None)
        if invite is None:
            return "No invitation recorded for this account."
        details = [f"Link {invite.short_token}"]
        if invite.used_at:
            details.append(f"used {timezone.localtime(invite.used_at):%d %b %Y, %H:%M}")
        if invite.note:
            details.append(f"note: {invite.note}")
        if invite.created_by_id:
            details.append(f"issued by {invite.created_by}")
        return " · ".join(details)

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


class RegistrationInviteForm(forms.ModelForm):
    """The add form: a note, an expiry, and a revoke switch.

    The token, who generated it, and who used it are all managed by the app, so
    they are read-only everywhere and never typed by hand.
    """

    class Meta:
        model = RegistrationInvite
        fields = ("note", "expires_at", "is_revoked")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None and not self.initial.get("expires_at"):
            self.initial["expires_at"] = default_invite_expiry()


@admin.register(RegistrationInvite)
class RegistrationInviteAdmin(admin.ModelAdmin):
    """Where the owner hands out access: one link, one registration.

    A link is generated here, copied, and sent privately (WhatsApp, email, in
    person). It admits exactly one person and then stops working, so a forwarded
    link cannot open the site to whoever receives it second.
    """

    form = RegistrationInviteForm
    list_display = ("invite_path", "note", "status_badge", "created_at", "expires_at", "used_by")
    list_filter = ("is_revoked", ("used_by", admin.EmptyFieldListFilter), "created_at")
    search_fields = ("note", "token", "used_by__email", "used_by__phone_number")
    search_help_text = "Search the private note, the link token, or the learner a link admitted."
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("token", "invite_path", "created_by", "created_at", "used_by", "used_at")
    fieldsets = (
        ("Invitation link", {"fields": ("invite_path", "token")}),
        ("About this link", {"fields": ("note", "expires_at", "is_revoked")}),
        (
            "Record",
            {
                "fields": ("created_at", "created_by", "used_by", "used_at"),
                "classes": ("collapse",),
            },
        ),
    )
    actions = ("revoke_invites", "extend_invites")
    change_list_template = "admin/valour/registrationinvite/change_list.html"
    change_form_template = "admin/valour/registrationinvite/change_form.html"

    class Media:
        css = {"all": ("valour/admin/invites.css",)}

    def get_urls(self):
        # The generate shortcut must be matched before the "<path:object_id>"
        # routes Django adds below it.
        return [
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_invite),
                name="valour_registrationinvite_generate",
            ),
            *super().get_urls(),
        ]

    @admin.display(description="Invitation link")
    def invite_path(self, invite):
        return format_html("/signup?invite={}…", invite.token[:12])

    @admin.display(description="Status")
    def status_badge(self, invite):
        labels = {"available": "Available", "used": "Used", "expired": "Expired", "revoked": "Revoked"}
        return format_html(
            '<span class="invite-status invite-status--{}">{}</span>', invite.status, labels[invite.status]
        )

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # A spent link is the record of how an account was admitted, so it stays.
        if obj is not None and obj.is_used:
            return False
        return super().has_delete_permission(request, obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Put the copyable link, and what it can still do, on the invite page."""
        invite = self.get_object(request, object_id)
        context = dict(extra_context or {})
        if invite is not None:
            context["invite_url"] = invite.registration_url(request)
            context["invite_available"] = invite.is_available
            context["invite_help"] = self._invite_help(invite)
        return super().change_view(request, object_id, form_url, context)

    def _invite_help(self, invite):
        if invite.status == "used":
            learner = invite.used_by
            used_at = timezone.localtime(invite.used_at).strftime("%d %b %Y, %H:%M") if invite.used_at else ""
            return f"This link already registered {learner} {used_at}. Generate another link for anyone else.".strip()
        if invite.status == "expired":
            expired = timezone.localtime(invite.expires_at).strftime("%d %b %Y, %H:%M") if invite.expires_at else ""
            return f"This link expired {expired} and no longer registers anyone. Use the extend action, or generate a new one."
        if invite.status == "revoked":
            return "This link was revoked and no longer registers anyone."
        if invite.expires_at:
            until = timezone.localtime(invite.expires_at).strftime("%d %b %Y, %H:%M")
            return f"It registers one person, then stops working. Send it privately — anyone holding it can use it until {until}."
        return "It registers one person, then stops working. Send it privately — anyone holding it can use it."

    def generate_invite(self, request):
        """Make one fresh link and land on its page, where it can be copied."""
        if not self.has_add_permission(request):
            raise PermissionDenied
        invite = RegistrationInvite.objects.create(
            created_by=request.user if request.user.is_authenticated else None,
            expires_at=default_invite_expiry(),
        )
        url = invite.registration_url(request)
        self.message_user(
            request,
            format_html(
                'Invitation link ready: <a href="{}">{}</a> It registers one person, then stops working.',
                url,
                url,
            ),
            messages.SUCCESS,
        )
        return HttpResponseRedirect(
            reverse(
                "admin:valour_registrationinvite_change", args=[invite.pk], current_app=self.admin_site.name
            )
        )

    @admin.action(description="Revoke selected unused links")
    def revoke_invites(self, request, queryset):
        revoked = queryset.filter(is_revoked=False, used_by__isnull=True).update(is_revoked=True)
        if revoked:
            self.message_user(request, f"{revoked} unused link(s) revoked.", messages.SUCCESS)
        else:
            self.message_user(
                request,
                "Nothing to revoke: those links are already revoked or have registered someone.",
                messages.WARNING,
            )

    @admin.action(description="Give selected unused links the full validity again")
    def extend_invites(self, request, queryset):
        days = settings.LEARNER_INVITE_VALID_DAYS or 14
        expiry = timezone.now() + timedelta(days=days)
        extended = queryset.filter(used_by__isnull=True).update(expires_at=expiry)
        if extended:
            self.message_user(request, f"{extended} link(s) now valid until {timezone.localtime(expiry):%d %b %Y}.", messages.SUCCESS)
        else:
            self.message_user(request, "Those links have already registered someone.", messages.WARNING)
