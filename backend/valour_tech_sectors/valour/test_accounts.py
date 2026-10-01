"""Learner sign-up, sign-in, session, and content-access tests."""

from importlib import import_module

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Course, Learner, Lesson, Material, Section, VideoLink
from .testing import (
    LEARNER_PASSWORD,
    create_learner,
    force_sign_in,
    json_body,
    sign_in,
)


def post_json(client, url_name, payload, **kwargs):
    return client.post(reverse(url_name), data=json_body(payload), content_type="application/json", **kwargs)


class PublishedLessonTestCase(TestCase):
    """A published course with one open lesson, video, and downloadable file."""

    def setUp(self):
        self.course = Course.objects.create(title="Resistors", slug="resistors", is_published=True)
        self.section = Section.objects.create(course=self.course, title="Basics")
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Resistance and units",
            slug="resistance-and-units",
            summary="What resistance does in a circuit.",
            notes="Resistance is measured in ohms.",
            safety_notice="Disconnect power before changing a component.",
        )
        self.video = VideoLink.objects.create(
            lesson=self.lesson,
            platform=VideoLink.Platform.YOUTUBE,
            url="https://youtu.be/dQw4w9WgXcQ",
        )
        self.material = Material.objects.create(
            lesson=self.lesson,
            title="Datasheet",
            kind=Material.Kind.PDF,
            file="course-materials/datasheet.pdf",
        )


class SignUpTests(TestCase):
    def test_sign_up_records_the_email_and_phone_number_and_starts_a_session(self):
        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "Ada@Example.com", "phone_number": "+234 803 123 4567", "password": LEARNER_PASSWORD},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["learner"]["email"], "ada@example.com")
        self.assertEqual(payload["learner"]["phone_number"], "+2348031234567")
        self.assertTrue(payload["csrf_token"])

        learner = Learner.objects.get(email="ada@example.com")
        self.assertEqual(learner.phone_number, "+2348031234567")
        self.assertTrue(learner.check_password(LEARNER_PASSWORD))
        self.assertEqual(Learner.objects.count(), 1)
        # The learner is signed in immediately: no second form after sign-up.
        self.assertEqual(self.client.session.get("_auth_user_backend"), "valour.auth_backends.LearnerBackend")

    def test_passwords_are_hashed_and_never_echoed_back(self):
        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "ada@example.com", "phone_number": "+2348031234567", "password": LEARNER_PASSWORD},
        )

        learner = Learner.objects.get()
        self.assertNotEqual(learner.password, LEARNER_PASSWORD)
        self.assertTrue(learner.password.startswith(("pbkdf2_", "scrypt_", "bcrypt_", "argon2")))
        self.assertNotIn(LEARNER_PASSWORD, response.content.decode())
        self.assertNotIn("password", response.json()["learner"])

    def test_sign_up_rejects_a_second_account_for_the_same_email(self):
        create_learner()

        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "ADA@example.com", "phone_number": "+2348031234567", "password": LEARNER_PASSWORD},
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["account_exists"])
        self.assertIn("Sign in instead", response.json()["message"])
        self.assertEqual(Learner.objects.count(), 1)

    def test_sign_up_reports_one_error_per_invalid_field(self):
        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "ada@", "phone_number": "call me", "password": "123", "confirm_password": "456"},
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]
        self.assertEqual(sorted(errors), ["confirm_password", "email", "password", "phone_number"])
        self.assertFalse(Learner.objects.exists())

    def test_sign_up_validates_the_phone_number_the_owner_will_use(self):
        accepted = ["+2348031234567", "0803 123 4567", "(09) 461-2233", "+1 (415) 555-0132"]
        rejected = ["", "abc", "+23480", "0803123456789012345", "+234-803-123-4567-8901"]

        for number in accepted:
            with self.subTest(number=number):
                Learner.objects.all().delete()
                response = post_json(
                    self.client,
                    "valour:auth-signup",
                    {"email": "ada@example.com", "phone_number": number, "password": LEARNER_PASSWORD},
                )
                self.assertEqual(response.status_code, 201, response.content)

        for number in rejected:
            with self.subTest(number=number):
                Learner.objects.all().delete()
                response = post_json(
                    self.client,
                    "valour:auth-signup",
                    {"email": "ada@example.com", "phone_number": number, "password": LEARNER_PASSWORD},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("phone_number", response.json()["errors"])

    def test_sign_up_refuses_weak_passwords_and_passwords_built_from_the_learners_details(self):
        weak = [
            ("too short", "ada@example.com", "+2348031234567", "res12"),
            ("only numbers", "ada@example.com", "+2348031234567", "08031234567"),
            ("too common", "ada@example.com", "+2348031234567", "password12345"),
            ("the email name", "adaeze@example.com", "+2348031234567", "adaeze-is-clever"),
            ("the phone number", "ada@example.com", "+2348031234567", "call-2348031234567"),
        ]

        for label, email, phone_number, password in weak:
            with self.subTest(password=label):
                response = post_json(
                    self.client,
                    "valour:auth-signup",
                    {"email": email, "phone_number": phone_number, "password": password},
                )
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("password", response.json()["errors"])
        self.assertFalse(Learner.objects.exists())

    def test_sign_up_keeps_the_learner_rules_instead_of_the_staff_password_policy(self):
        # Staff must use 12 characters; a learner may use 8.
        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "ada@example.com", "phone_number": "+2348031234567", "password": "voltmeter"},
        )

        self.assertEqual(response.status_code, 201, response.content)

    def test_sign_up_needs_json_and_refuses_oversized_bodies(self):
        with self.subTest(body="form encoded"):
            response = self.client.post(reverse("valour:auth-signup"), {"email": "ada@example.com"})
            self.assertEqual(response.status_code, 400)
        with self.subTest(body="broken json"):
            response = self.client.post(
                reverse("valour:auth-signup"), data="{not json", content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
        with self.subTest(body="json list"):
            response = self.client.post(reverse("valour:auth-signup"), data="[]", content_type="application/json")
            self.assertEqual(response.status_code, 400)
        with self.subTest(body="too large"):
            response = self.client.post(
                reverse("valour:auth-signup"),
                data=json_body({"email": "ada@example.com", "phone_number": "9" * 20000}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Learner.objects.exists())

    def test_sign_up_is_post_only_and_needs_a_csrf_token(self):
        response = self.client.get(reverse("valour:auth-signup"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")
        self.assertIn("POST", response.json()["message"])

        strict = Client(enforce_csrf_checks=True)
        response = post_json(
            strict,
            "valour:auth-signup",
            {"email": "ada@example.com", "phone_number": "+2348031234567", "password": LEARNER_PASSWORD},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "Access denied."})
        self.assertFalse(Learner.objects.exists())

    def test_an_already_signed_in_learner_cannot_create_another_account(self):
        force_sign_in(self.client)

        response = post_json(
            self.client,
            "valour:auth-signup",
            {"email": "second@example.com", "phone_number": "+2348031234567", "password": LEARNER_PASSWORD},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Learner.objects.count(), 1)


class SignInTests(TestCase):
    def test_sign_in_opens_the_account_and_records_when_it_happened(self):
        learner = create_learner()
        self.assertIsNone(learner.last_login)

        response = post_json(
            self.client, "valour:auth-signin", {"email": "ADA@example.com", "password": LEARNER_PASSWORD}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["learner"]["email"], learner.email)
        learner.refresh_from_db()
        self.assertIsNotNone(learner.last_login)
        self.assertEqual(learner.failed_login_attempts, 0)

    def test_sign_in_gives_the_same_answer_for_a_wrong_password_and_an_unknown_email(self):
        create_learner()

        wrong_password = post_json(
            self.client, "valour:auth-signin", {"email": "ada@example.com", "password": "not-the-password"}
        )
        unknown_email = post_json(
            self.client, "valour:auth-signin", {"email": "stranger@example.com", "password": "not-the-password"}
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_email.status_code, 401)
        self.assertEqual(wrong_password.json()["message"], unknown_email.json()["message"])
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_sign_in_refuses_blank_details_and_non_json_bodies(self):
        for payload in ({}, {"email": "ada@example.com"}, {"password": LEARNER_PASSWORD}):
            with self.subTest(payload=payload):
                response = post_json(self.client, "valour:auth-signin", payload)
                self.assertEqual(response.status_code, 400)

        response = self.client.get(reverse("valour:auth-signin"))
        self.assertEqual(response.status_code, 405)

    def test_sign_in_rotates_the_session_key_so_a_stolen_anonymous_session_cannot_be_reused(self):
        learner = create_learner()
        engine = import_module(settings.SESSION_ENGINE)
        anonymous = engine.SessionStore()
        anonymous["before_sign_in"] = True
        anonymous.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = anonymous.session_key

        post_json(self.client, "valour:auth-signin", {"email": learner.email, "password": LEARNER_PASSWORD})

        self.assertNotEqual(self.client.session.session_key, anonymous.session_key)
        self.assertEqual(int(self.client.session["_auth_user_id"]), learner.pk)
        # The key an attacker could have kept is deleted, not just abandoned.
        self.assertFalse(Session.objects.filter(session_key=anonymous.session_key).exists())

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_sign_in_keeps_the_learner_session_secure(self):
        learner = create_learner()

        post_json(self.client, "valour:auth-signin", {"email": learner.email, "password": LEARNER_PASSWORD})

        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_remembering_a_learner_extends_the_session_beyond_the_browser(self):
        learner = create_learner()

        post_json(
            self.client,
            "valour:auth-signin",
            {"email": learner.email, "password": LEARNER_PASSWORD, "remember": True},
        )

        self.assertEqual(
            self.client.session.get_expiry_age(),
            settings.LEARNER_SESSION_REMEMBER_DAYS * 24 * 60 * 60,
        )

        self.client.post(reverse("valour:auth-signout"))
        post_json(self.client, "valour:auth-signin", {"email": learner.email, "password": LEARNER_PASSWORD})
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    @override_settings(LEARNER_LOGIN_FAILURE_LIMIT=3, LEARNER_LOGIN_LOCKOUT_MINUTES=15)
    def test_repeated_failures_lock_that_email_address_only(self):
        locked_out = create_learner()
        unaffected = create_learner(email="grace@example.com")

        for attempt in range(2):
            response = post_json(
                self.client, "valour:auth-signin", {"email": locked_out.email, "password": "wrong-password"}
            )
            self.assertEqual(response.status_code, 401, f"attempt {attempt}")

        # The attempt that reaches the limit is refused as a lockout at once.
        tripped = post_json(
            self.client, "valour:auth-signin", {"email": locked_out.email, "password": "wrong-password"}
        )
        self.assertEqual(tripped.status_code, 429)

        locked_out.refresh_from_db()
        self.assertTrue(locked_out.is_locked_out())

        response = post_json(
            self.client, "valour:auth-signin", {"email": locked_out.email, "password": LEARNER_PASSWORD}
        )
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.json()["locked"])
        self.assertLessEqual(int(response["Retry-After"]), 15 * 60)
        self.assertIn("Too many sign-in attempts", response.json()["message"])

        # Another learner is untouched, and no visitor IP address is stored.
        self.assertEqual(sign_in(self.client, unaffected).email, unaffected.email)
        self.assertEqual(AccessAttempt.objects.count(), 0)

    @override_settings(LEARNER_LOGIN_FAILURE_LIMIT=3, LEARNER_LOGIN_LOCKOUT_MINUTES=15)
    def test_a_finished_lockout_lets_the_learner_back_in_and_starts_counting_again(self):
        learner = create_learner()
        learner.failed_login_attempts = 3
        learner.locked_until = timezone.now() - timezone.timedelta(minutes=1)
        learner.save()

        response = post_json(
            self.client, "valour:auth-signin", {"email": learner.email, "password": LEARNER_PASSWORD}
        )

        self.assertEqual(response.status_code, 200)
        learner.refresh_from_db()
        self.assertEqual(learner.failed_login_attempts, 0)
        self.assertIsNone(learner.locked_until)

    def test_a_deactivated_learner_cannot_sign_in_but_keeps_their_record(self):
        learner = create_learner()
        learner.is_active = False
        learner.save()

        response = post_json(
            self.client, "valour:auth-signin", {"email": learner.email, "password": LEARNER_PASSWORD}
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Learner.objects.filter(pk=learner.pk).exists())

    def test_a_deactivated_learner_loses_an_open_session_on_their_next_request(self):
        learner = force_sign_in(self.client)
        self.assertEqual(self.client.get(reverse("valour:auth-session")).json()["authenticated"], True)

        learner.is_active = False
        learner.save()

        self.assertEqual(self.client.get(reverse("valour:auth-session")).json()["authenticated"], False)

    def test_staff_accounts_cannot_use_the_learner_sign_in_endpoint(self):
        staff = get_user_model().objects.create_user(
            username="owner", email="ada@example.com", password=LEARNER_PASSWORD, is_staff=True
        )

        response = post_json(
            self.client, "valour:auth-signin", {"email": staff.email, "password": LEARNER_PASSWORD}
        )

        self.assertEqual(response.status_code, 401)

    def test_learner_failures_do_not_lock_staff_out_of_the_admin(self):
        learner = create_learner()
        for _ in range(settings.LEARNER_LOGIN_FAILURE_LIMIT):
            post_json(self.client, "valour:auth-signin", {"email": learner.email, "password": "wrong-password"})

        # A learner sign-in failure is not an admin failure, so django-axes (which
        # only watches the admin) records nothing and locks nobody out.
        self.assertEqual(AccessAttempt.objects.count(), 0)

        get_user_model().objects.create_user(username="owner", password="owner-strong-password", is_staff=True)
        response = self.client.post("/admin/login/", {"username": "owner", "password": "owner-strong-password"})
        self.assertEqual(response.status_code, 302)  # Into the admin, not a lockout page.


class SessionAndSignOutTests(TestCase):
    def test_the_session_endpoint_answers_for_visitors_and_learners(self):
        anonymous = self.client.get(reverse("valour:auth-session"))
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous.json()["authenticated"], False)
        self.assertIsNone(anonymous.json()["learner"])
        self.assertEqual(anonymous.json()["content_access"], settings.LEARNER_CONTENT_ACCESS)
        self.assertTrue(anonymous.json()["csrf_token"])

        learner = force_sign_in(self.client)
        signed_in = self.client.get(reverse("valour:auth-session"))
        self.assertEqual(signed_in.json()["authenticated"], True)
        self.assertEqual(signed_in.json()["learner"]["email"], learner.email)
        self.assertEqual(signed_in.json()["learner"]["phone_number"], learner.phone_number)
        self.assertIn("no-store", signed_in["Cache-Control"])

    def test_sign_out_ends_the_session_and_issues_a_fresh_csrf_token(self):
        force_sign_in(self.client)
        previous_token = self.client.get(reverse("valour:auth-session")).json()["csrf_token"]
        session_key = self.client.session.session_key

        response = self.client.post(reverse("valour:auth-signout"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["authenticated"], False)
        self.assertNotEqual(response.json()["csrf_token"], previous_token)
        self.assertNotEqual(self.client.session.session_key, session_key)
        self.assertEqual(self.client.get(reverse("valour:auth-session")).json()["authenticated"], False)

    def test_sign_out_is_post_only_and_works_for_a_visitor(self):
        self.assertEqual(self.client.get(reverse("valour:auth-signout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("valour:auth-signout")).status_code, 200)


class ContentAccessTests(PublishedLessonTestCase):
    def test_a_visitor_sees_the_lesson_prompt_and_none_of_its_content(self):
        response = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))

        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertTrue(payload["sign_in_required"])
        self.assertEqual(payload["sign_in_path"], "/signin")
        self.assertEqual(payload["lesson"]["title"], self.lesson.title)
        self.assertEqual(payload["lesson"]["course"]["slug"], self.course.slug)
        body = response.content.decode()
        for secret in (self.lesson.notes, self.lesson.safety_notice, self.video.url, "youtube-nocookie"):
            self.assertNotIn(secret, body)
        self.assertIn("Cookie", response["Vary"])

    def test_a_signed_in_learner_gets_the_lesson_content(self):
        force_sign_in(self.client)

        response = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["notes"], self.lesson.notes)
        self.assertEqual(payload["videos"][0]["source_url"], self.video.url)
        self.assertEqual(payload["materials"][0]["download_url"], f"/api/v1/materials/{self.material.pk}/download/")

    def test_the_owner_can_review_published_lessons_with_a_staff_session(self):
        owner = get_user_model().objects.create_user(username="owner", password=LEARNER_PASSWORD, is_staff=True)
        self.client.force_login(owner, backend="django.contrib.auth.backends.ModelBackend")

        self.assertEqual(self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug])).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("valour:material-download", args=[self.material.pk])).status_code, 302
        )

    def test_a_course_outline_lists_lessons_but_withholds_content_for_visitors(self):
        response = self.client.get(reverse("valour:course-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sign_in_required"])
        lesson = payload["sections"][0]["lessons"][0]
        self.assertEqual(lesson["title"], self.lesson.title)
        self.assertTrue(lesson["sign_in_required"])
        self.assertEqual(lesson["notes"], "")
        self.assertEqual(lesson["videos"], [])
        self.assertIsNone(lesson["materials"][0]["download_url"])
        self.assertTrue(lesson["materials"][0]["sign_in_required"])
        self.assertNotIn(self.lesson.notes, response.content.decode())

    def test_a_course_outline_shows_content_to_a_signed_in_learner(self):
        force_sign_in(self.client)

        payload = self.client.get(reverse("valour:course-detail", args=[self.course.slug])).json()

        self.assertFalse(payload["sign_in_required"])
        self.assertEqual(payload["sign_in_message"], "")
        lesson = payload["sections"][0]["lessons"][0]
        self.assertFalse(lesson["sign_in_required"])
        self.assertEqual(lesson["notes"], self.lesson.notes)
        self.assertEqual(len(lesson["videos"]), 1)

    def test_a_visitor_downloading_a_file_is_sent_to_the_sign_in_page(self):
        url = reverse("valour:material-download", args=[self.material.pk])

        api_response = self.client.get(url, headers={"accept": "application/json"})
        self.assertEqual(api_response.status_code, 401)
        self.assertTrue(api_response.json()["sign_in_required"])
        self.assertEqual(api_response.json()["next"], f"/lessons/{self.lesson.slug}")

        browser_response = self.client.get(url, headers={"sec-fetch-dest": "document", "accept": "*/*"})
        self.assertEqual(browser_response.status_code, 302)
        # A relative Location keeps the redirect on this origin.
        self.assertEqual(browser_response["Location"], f"/signin?next=/lessons/{self.lesson.slug}")

    def test_a_signed_in_learner_still_downloads_the_file(self):
        force_sign_in(self.client)

        response = self.client.get(reverse("valour:material-download", args=[self.material.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/media/course-materials/datasheet.pdf", response["Location"])

    def test_a_staff_lock_outranks_sign_in_and_unpublished_content_stays_hidden(self):
        self.lesson.is_locked = True
        self.lesson.lock_notice = "This lesson opens next week."
        self.lesson.save()
        force_sign_in(self.client)

        locked = self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug]))
        self.assertEqual(locked.status_code, 403)
        self.assertEqual(locked.json()["message"], "This lesson opens next week.")

        self.lesson.is_locked = False
        self.lesson.is_published = False
        self.lesson.save()
        self.assertEqual(
            self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug])).status_code, 404
        )

    @override_settings(LEARNER_CONTENT_ACCESS="open")
    def test_open_access_keeps_the_site_public_while_accounts_are_only_a_record(self):
        self.assertEqual(self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug])).status_code, 200)
        self.assertEqual(self.client.get(reverse("valour:material-download", args=[self.material.pk])).status_code, 302)
        self.assertFalse(self.client.get(reverse("valour:course-detail", args=[self.course.slug])).json()["sign_in_required"])

    @override_settings(LEARNER_CONTENT_ACCESS="everything")
    def test_everything_access_also_closes_the_catalogue_but_never_the_public_pages(self):
        self.assertEqual(self.client.get(reverse("valour:course-list")).status_code, 401)
        self.assertEqual(self.client.get(reverse("valour:course-detail", args=[self.course.slug])).status_code, 401)
        self.assertEqual(self.client.get(reverse("valour:lesson-detail", args=[self.lesson.slug])).status_code, 401)

        # Health, readiness, and the contact details stay reachable by anyone.
        self.assertEqual(self.client.get(reverse("valour:health")).status_code, 200)
        self.assertEqual(self.client.get(reverse("valour:site-profile")).status_code, 200)

        force_sign_in(self.client)
        self.assertEqual(self.client.get(reverse("valour:course-list")).status_code, 200)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class LearnerAdminTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner", email="owner@example.com", password=LEARNER_PASSWORD
        )
        self.learner = create_learner()
        # Named because django-axes is first in AUTHENTICATION_BACKENDS and would
        # otherwise be recorded as the session backend for a staff login.
        self.client.force_login(self.owner, backend="django.contrib.auth.backends.ModelBackend")

    def test_staff_see_the_sign_up_record_and_can_search_it(self):
        listing = self.client.get(reverse("admin:valour_learner_changelist"))
        self.assertContains(listing, self.learner.email)
        self.assertContains(listing, self.learner.phone_number)

        found = self.client.get(reverse("admin:valour_learner_changelist"), {"q": "8031234567"})
        self.assertContains(found, self.learner.email)
        missing = self.client.get(reverse("admin:valour_learner_changelist"), {"q": "nobody@example.com"})
        self.assertNotContains(missing, self.learner.email)

    def test_the_change_form_never_shows_the_password_hash(self):
        response = self.client.get(reverse("admin:valour_learner_change", args=[self.learner.pk]))

        self.assertContains(response, self.learner.email)
        self.assertNotContains(response, self.learner.password)

    def test_staff_cannot_invent_an_account_but_can_update_the_contact_details(self):
        self.assertEqual(self.client.get(reverse("admin:valour_learner_add")).status_code, 403)

        response = self.client.post(
            reverse("admin:valour_learner_change", args=[self.learner.pk]),
            {"email": self.learner.email, "phone_number": "+234 805 000 1111", "is_active": "on"},
        )

        self.assertEqual(response.status_code, 302)
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.phone_number, "+2348050001111")

    def test_staff_can_reset_a_forgotten_password_and_the_learner_can_sign_in_with_it(self):
        url = reverse("admin:valour_learner_password", args=[self.learner.pk])

        invalid = self.client.post(url, {"new_password1": "12345678", "new_password2": "12345678"})
        self.assertEqual(invalid.status_code, 200)  # Re-renders the form with the error.
        self.learner.refresh_from_db()
        self.assertFalse(self.learner.check_password("12345678"))

        mismatched = self.client.post(url, {"new_password1": "fresh-start-1", "new_password2": "fresh-start-2"})
        self.assertContains(mismatched, "do not match")

        valid = self.client.post(url, {"new_password1": "fresh-start-1", "new_password2": "fresh-start-1"})
        self.assertEqual(valid.status_code, 302)
        self.learner.refresh_from_db()
        self.assertTrue(self.learner.check_password("fresh-start-1"))
        self.assertFalse(self.learner.check_password(LEARNER_PASSWORD))

        visitor = Client()
        response = post_json(visitor, "valour:auth-signin", {"email": self.learner.email, "password": "fresh-start-1"})
        self.assertEqual(response.status_code, 200)

    def test_staff_can_clear_a_lockout_with_one_action(self):
        self.learner.failed_login_attempts = settings.LEARNER_LOGIN_FAILURE_LIMIT
        self.learner.locked_until = timezone.now() + timezone.timedelta(minutes=10)
        self.learner.save()

        self.client.post(
            reverse("admin:valour_learner_changelist"),
            {"action": "unlock_sign_in", "_selected_action": [self.learner.pk]},
        )

        self.learner.refresh_from_db()
        self.assertEqual(self.learner.failed_login_attempts, 0)
        self.assertIsNone(self.learner.locked_until)

    def test_a_learner_session_cannot_reach_the_admin(self):
        learner_client = Client()
        force_sign_in(learner_client, create_learner(email="learner@example.com"))

        response = learner_client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_the_admin_requires_a_staff_session(self):
        response = Client().get(reverse("admin:valour_learner_changelist"))
        self.assertEqual(response.status_code, 302)
