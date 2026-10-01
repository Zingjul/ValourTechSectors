from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Course, Lesson, Material, Section, SiteProfile, SocialLink, VideoLink


class PublicCourseApiTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            title="Resistors",
            slug="resistors",
            summary="Learn how resistors behave in a circuit.",
            description="A practical introduction to resistance.",
            level=Course.Level.BEGINNER,
            is_published=True,
        )
        self.section = Section.objects.create(course=self.course, title="Start here", ordering=1)
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Resistance and units",
            slug="resistance-and-units",
            notes="Resistance is measured in ohms.",
            safety_notice="Disconnect power before changing a component.",
        )
        self.video = VideoLink.objects.create(
            lesson=self.lesson,
            title="An introduction to resistance",
            platform=VideoLink.Platform.YOUTUBE,
            url="https://youtu.be/dQw4w9WgXcQ",
        )

    def test_catalog_lists_only_published_courses_and_includes_lock_state(self):
        Course.objects.create(title="Draft", slug="draft", is_published=False)
        self.course.is_locked = True
        self.course.save()

        response = self.client.get(reverse("valour:course-list"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["slug"], "resistors")
        self.assertTrue(payload["results"][0]["is_locked"])

    def test_locked_course_stays_visible_and_withholds_descendant_content(self):
        self.course.is_locked = True
        self.course.lock_notice = "This course is not open yet."
        self.course.save()

        response = self.client.get(reverse("valour:course-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_locked"])
        self.assertEqual(payload["lock_notice"], "This course is not open yet.")
        lesson = payload["sections"][0]["lessons"][0]
        self.assertTrue(lesson["is_locked"])
        self.assertEqual(lesson["notes"], "")
        self.assertEqual(lesson["safety_notice"], "")
        self.assertEqual(lesson["videos"], [])

    def test_catalog_supports_query_and_level_filter(self):
        response = self.client.get(reverse("valour:course-list"), {"q": "resistor", "level": "beginner"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

        response = self.client.get(reverse("valour:course-list"), {"level": "expert"})
        self.assertEqual(response.status_code, 400)

    def test_course_outline_keeps_locked_titles_but_withholds_content_and_links(self):
        self.lesson.is_locked = True
        self.lesson.save()
        material = Material.objects.create(
            lesson=self.lesson,
            title="Resistor notes",
            kind=Material.Kind.PDF,
            file="course-materials/resistor-notes.pdf",
        )

        response = self.client.get(reverse("valour:course-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        lesson = response.json()["sections"][0]["lessons"][0]
        self.assertEqual(lesson["title"], "Resistance and units")
        self.assertTrue(lesson["is_locked"])
        self.assertEqual(lesson["notes"], "")
        self.assertEqual(lesson["videos"], [])
        self.assertIsNone(lesson["materials"][0]["download_url"])
        self.assertEqual(material.pk, lesson["materials"][0]["id"])

    def test_locked_lesson_endpoint_returns_notice_not_lesson_content(self):
        self.section.is_locked = True
        self.section.lock_notice = "This section will open soon."
        self.section.save()

        response = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"locked": True, "message": "This section will open soon."})

    def test_open_lesson_returns_notes_and_youtube_embed_and_source(self):
        response = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["notes"], self.lesson.notes)
        self.assertEqual(payload["safety_notice"], self.lesson.safety_notice)
        self.assertEqual(payload["videos"][0]["source_url"], self.video.url)
        self.assertEqual(
            payload["videos"][0]["embed_url"],
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        )

    def test_tiktok_and_facebook_use_provider_players_and_instagram_falls_back(self):
        tiktok = VideoLink.objects.create(
            lesson=self.lesson,
            platform=VideoLink.Platform.TIKTOK,
            url="https://www.tiktok.com/@valourtech/video/1234567890123456789",
        )
        facebook = VideoLink.objects.create(
            lesson=self.lesson,
            platform=VideoLink.Platform.FACEBOOK,
            url="https://www.facebook.com/ValourTech/videos/1234567890/",
        )
        instagram = VideoLink.objects.create(
            lesson=self.lesson,
            platform=VideoLink.Platform.INSTAGRAM,
            url="https://www.instagram.com/reel/ABC123/",
        )

        self.assertEqual(tiktok.embed_url(), "https://www.tiktok.com/player/v1/1234567890123456789")
        self.assertIn("facebook.com/plugins/video.php", facebook.embed_url())
        self.assertIsNone(instagram.embed_url())

    def test_unpublished_course_and_lesson_are_not_public(self):
        self.course.is_published = False
        self.course.save()
        self.assertEqual(self.client.get(reverse("valour:course-detail", args=[self.course.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug])).status_code, 404)

    def test_locked_material_cannot_be_downloaded(self):
        material = Material.objects.create(
            lesson=self.lesson,
            title="Component datasheet",
            kind=Material.Kind.PDF,
            file="course-materials/datasheet.pdf",
            is_locked=True,
        )

        response = self.client.get(reverse("valour:material-download", args=[material.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["locked"])

    def test_open_material_uses_a_redirect_to_storage_url(self):
        material = Material.objects.create(
            lesson=self.lesson,
            title="Component datasheet",
            kind=Material.Kind.PDF,
            file="course-materials/datasheet.pdf",
        )

        response = self.client.get(reverse("valour:material-download", args=[material.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/media/course-materials/datasheet.pdf", response["Location"])

    def test_video_link_rejects_platform_host_mismatch(self):
        video = VideoLink(
            lesson=self.lesson,
            platform=VideoLink.Platform.TIKTOK,
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        )
        with self.assertRaisesMessage(ValidationError, "The URL host does not match"):
            video.full_clean()


class SiteProfileApiTests(TestCase):
    def test_staff_admin_requires_authentication(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_site_profile_does_not_invent_contact_or_social_details(self):
        response = self.client.get(reverse("valour:site-profile"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["brand_name"], "ValourTech Sectors")
        self.assertEqual(response.json()["contact_email"], "")
        self.assertEqual(response.json()["social_links"], [])

    def test_profile_and_active_social_links_are_returned(self):
        SiteProfile.objects.create(contact_email="learn@example.com")
        SocialLink.objects.create(platform=SocialLink.Platform.INSTAGRAM, url="https://instagram.com/valourtech")
        SocialLink.objects.create(
            platform=SocialLink.Platform.YOUTUBE,
            url="https://youtube.com/@valourtech",
            is_active=False,
        )

        response = self.client.get(reverse("valour:site-profile"))

        self.assertEqual(response.json()["contact_email"], "learn@example.com")
        self.assertEqual(len(response.json()["social_links"]), 1)
        self.assertEqual(response.json()["social_links"][0]["platform"], "instagram")
