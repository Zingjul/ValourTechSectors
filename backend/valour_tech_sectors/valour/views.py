import logging
from urllib.parse import urlparse

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import DatabaseError, connections
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_safe

from .models import Course, Lesson, Material, Section, SiteProfile, SocialLink, VideoLink

logger = logging.getLogger(__name__)


def json_response(data, *, status=200):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def health(request):
    return json_response({"status": "ok"})


@require_safe
def ready(request):
    """Readiness depends on Postgres and the built frontend, not external video providers."""
    if not settings.DEBUG and not (settings.FRONTEND_DIST / "index.html").is_file():
        logger.error("Readiness frontend build is missing.")
        return json_response({"status": "unavailable"}, status=503)
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        # Connection errors may contain credentials; never return/log their text.
        logger.error("Readiness database probe failed.")
        return json_response({"status": "unavailable"}, status=503)
    return json_response({"status": "ok"})


def _public_lessons():
    return Lesson.objects.select_related("section__course").prefetch_related(
        Prefetch("videos", queryset=VideoLink.objects.filter(is_active=True), to_attr="public_videos"),
        Prefetch("materials", queryset=Material.objects.filter(is_published=True), to_attr="public_materials"),
    )


def _lesson_is_locked(lesson):
    return lesson.is_locked or lesson.section.is_locked or lesson.section.course.is_locked


def _lock_notice(*items):
    for item in items:
        if item and getattr(item, "is_locked", False) and item.lock_notice:
            return item.lock_notice
    return "This learning material is currently locked."


def _video_data(video):
    embed_url = video.embed_url()
    return {
        "id": video.pk,
        "title": video.title or f"{video.get_platform_display()} lesson",
        "platform": video.platform,
        "platform_label": video.get_platform_display(),
        "source_url": video.url,
        "embed_url": embed_url,
    }


def _material_data(material, *, inherited_lock=False, inherited_notice=""):
    locked = inherited_lock or material.is_locked
    notice = (
        _lock_notice(material)
        if material.is_locked
        else inherited_notice if inherited_lock else ""
    )
    return {
        "id": material.pk,
        "title": material.title,
        "description": material.description,
        "kind": material.kind,
        "kind_label": material.get_kind_display(),
        "file_name": material.file.name.rsplit("/", 1)[-1] if material.file else "",
        "extension": material.file_extension,
        "is_locked": locked,
        "lock_notice": notice,
        "download_url": None if locked else f"/api/v1/materials/{material.pk}/download/",
    }


def _lesson_outline_data(lesson, *, inherited_lock=False):
    locked = inherited_lock or lesson.is_locked
    lock_notice = _lock_notice(lesson.section.course, lesson.section, lesson) if locked else ""
    videos = [] if locked else [_video_data(video) for video in lesson.public_videos]
    materials = [
        _material_data(material, inherited_lock=locked, inherited_notice=lock_notice)
        for material in lesson.public_materials
    ]
    return {
        "id": lesson.pk,
        "title": lesson.title,
        "slug": lesson.slug,
        "summary": lesson.summary,
        "estimated_minutes": lesson.estimated_minutes,
        "is_locked": locked,
        "lock_notice": lock_notice,
        "url": f"/api/v1/lessons/{lesson.slug}/",
        "notes": "" if locked else lesson.notes,
        "safety_notice": "" if locked else lesson.safety_notice,
        "videos": videos,
        "materials": materials,
    }


def _course_data(course, *, include_outline=False):
    data = {
        "id": course.pk,
        "title": course.title,
        "slug": course.slug,
        "summary": course.summary,
        "description": course.description,
        "level": course.level,
        "level_label": course.get_level_display(),
        "estimated_minutes": course.estimated_minutes,
        "is_locked": course.is_locked,
        "lock_notice": course.lock_notice if course.is_locked else "",
        "url": f"/api/v1/courses/{course.slug}/",
    }
    if not include_outline:
        return data

    sections = []
    for section in course.public_sections:
        section_locked = course.is_locked or section.is_locked
        lessons = [
            _lesson_outline_data(lesson, inherited_lock=section_locked)
            for lesson in section.public_lessons
        ]
        sections.append(
            {
                "id": section.pk,
                "title": section.title,
                "description": section.description,
                "is_locked": section_locked,
                "lock_notice": _lock_notice(course, section) if section_locked else "",
                "lessons": lessons,
            }
        )
    data["sections"] = sections
    return data


@require_safe
def course_list(request):
    courses = Course.objects.filter(is_published=True).order_by("ordering", "title", "pk")
    query = request.GET.get("q", "").strip()[:120]
    level = request.GET.get("level", "").strip().lower()
    if query:
        courses = courses.filter(Q(title__icontains=query) | Q(summary__icontains=query))
    if level:
        if level not in Course.Level.values:
            return json_response({"error": "Choose beginner, intermediate, or advanced."}, status=400)
        courses = courses.filter(level=level)

    try:
        page_number = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page_number = 1
    paginator = Paginator(courses, 12)
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    return json_response(
        {
            "count": paginator.count,
            "page": page.number,
            "pages": paginator.num_pages,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "results": [_course_data(course) for course in page.object_list],
        }
    )


@require_safe
def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.prefetch_related(
            Prefetch(
                "sections",
                queryset=Section.objects.filter(is_published=True).prefetch_related(
                    Prefetch("lessons", queryset=_public_lessons().filter(is_published=True), to_attr="public_lessons")
                ),
                to_attr="public_sections",
            )
        ),
        slug=slug,
        is_published=True,
    )
    return json_response(_course_data(course, include_outline=True))


def _lesson_is_published(lesson):
    return (
        lesson.is_published
        and lesson.section.is_published
        and lesson.section.course.is_published
    )


def _lesson_detail_data(lesson):
    return {
        "id": lesson.pk,
        "title": lesson.title,
        "slug": lesson.slug,
        "summary": lesson.summary,
        "notes": lesson.notes,
        "safety_notice": lesson.safety_notice,
        "estimated_minutes": lesson.estimated_minutes,
        "course": {
            "title": lesson.section.course.title,
            "slug": lesson.section.course.slug,
        },
        "section": {"title": lesson.section.title, "id": lesson.section_id},
        "videos": [
            _video_data(video)
            for video in lesson.public_videos
        ],
        "materials": [
            _material_data(material)
            for material in lesson.public_materials
        ],
    }


@require_safe
def lesson_detail(request, slug):
    lesson = get_object_or_404(
        _public_lessons(),
        slug=slug,
    )
    if not _lesson_is_published(lesson):
        raise Http404
    if _lesson_is_locked(lesson):
        return json_response(
            {
                "locked": True,
                "message": _lock_notice(lesson.section.course, lesson.section, lesson),
            },
            status=403,
        )
    return json_response(_lesson_detail_data(lesson))


def _material_is_locked(material):
    lesson = material.lesson
    return (
        material.is_locked
        or lesson.is_locked
        or lesson.section.is_locked
        or lesson.section.course.is_locked
    )


@require_safe
def material_download(request, pk):
    material = get_object_or_404(
        Material.objects.select_related("lesson__section__course"),
        pk=pk,
        is_published=True,
        lesson__is_published=True,
        lesson__section__is_published=True,
        lesson__section__course__is_published=True,
    )
    if _material_is_locked(material):
        lesson = material.lesson
        return json_response(
            {
                "locked": True,
                "message": _lock_notice(material, lesson, lesson.section, lesson.section.course),
            },
            status=403,
        )
    if not material.file:
        raise Http404
    try:
        file_url = material.file.url
    except (BotoCoreError, ClientError):
        logger.error("Material URL signing failed.")
        return json_response({"message": "This download is temporarily unavailable."}, status=503)
    except (ValueError, OSError):
        raise Http404
    if not file_url:
        raise Http404
    parsed = urlparse(file_url)
    if parsed.scheme:
        storage_origin = urlparse(settings.SUPABASE_URL)
        if (
            parsed.scheme != "https"
            or not storage_origin.netloc
            or parsed.netloc.lower() != storage_origin.netloc.lower()
            or parsed.username
            or parsed.password
        ):
            raise Http404
    elif parsed.netloc or not parsed.path.startswith("/") or file_url.startswith("//"):
        # Local development files are root-relative /media/ URLs only; reject
        # protocol-relative URLs so file metadata cannot become an open redirect.
        raise Http404

    response = redirect(file_url)
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_safe
def site_profile(request):
    profile = SiteProfile.objects.first()
    social_links = SocialLink.objects.filter(is_active=True).order_by("ordering", "platform", "id")
    return json_response(
        {
            "brand_name": profile.brand_name if profile else "ValourTech Sectors",
            "tagline": profile.tagline if profile else "",
            "contact_email": profile.contact_email if profile else "",
            "phone_number": profile.phone_number if profile else "",
            "whatsapp_url": profile.whatsapp_url if profile else "",
            "contact_note": profile.contact_note if profile else "",
            "social_links": [
                {
                    "id": link.pk,
                    "platform": link.platform,
                    "platform_label": link.get_platform_display(),
                    "label": link.label or link.get_platform_display(),
                    "url": link.url,
                }
                for link in social_links
            ],
        }
    )
