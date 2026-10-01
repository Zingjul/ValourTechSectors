from django.contrib import admin

from .models import Course, Lesson, Material, Section, SiteProfile, SocialLink, VideoLink


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
