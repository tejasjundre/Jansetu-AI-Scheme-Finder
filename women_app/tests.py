import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .myscheme_api import merge_myscheme_detail_into_record
from .models import ChatHistory, CitizenProfile, EligibilityAssessment, EscalationRequest, Scheme


class PageTests(TestCase):
    @patch("women_app.views.get_launch_news")
    def test_home_page_loads(self, mock_get_launch_news):
        mock_news = [
            {
                "title": "New official scheme launch",
                "summary": "Official update",
                "url": "https://pib.gov.in/example",
                "published_on": "25 MAR 2026",
                "image_url": "https://pib.gov.in/example.png",
                "source_name": "Press Information Bureau",
            }
        ]
        mock_get_launch_news.return_value = mock_news
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JanSetu")
        self.assertContains(response, "Daily government scheme news")

    def test_wizard_page_loads(self):
        response = self.client.get(reverse("wizard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "wizard")

    def test_healthz_loads(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("services", payload)
        self.assertEqual(payload["services"]["database"], "ok")

    def test_schemes_page_uses_json_fallback(self):
        response = self.client.get(reverse("schemes"))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["scheme_total"], 0)

    @patch("women_app.views.fetch_scheme_detail")
    def test_scheme_detail_page_loads(self, mock_fetch_scheme_detail):
        Scheme.objects.create(
            name="Sample Official Scheme",
            category="education",
            description="Sample description",
            eligibility="Sample eligibility",
            official_source_name="Ministry of Education",
            url="https://www.myscheme.gov.in/schemes/sample-official-scheme",
        )
        mock_fetch_scheme_detail.return_value = {
            "name": "Sample Official Scheme",
            "brief_description": "Detailed summary",
            "quick_links": [{"label": "Open myScheme page", "url": "https://www.myscheme.gov.in/schemes/sample-official-scheme"}],
            "documents": ["Identity proof"],
            "faqs": [],
            "scheme_level": "Central",
            "nodal_ministry": "Ministry of Education",
        }

        response = self.client.get(reverse("scheme_detail", args=["sample-official-scheme"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sample Official Scheme")


class WizardAndSupportTests(TestCase):
    def test_wizard_submission_creates_assessment(self):
        payload = {
            "language": "en",
            "age": 24,
            "annual_income": 180000,
            "income_band": "under_2l",
            "gender": "female",
            "state": "Maharashtra",
            "district": "Pune",
            "residence_type": "urban",
            "support_need": "financial",
            "is_student": "",
            "is_mother": "",
            "is_entrepreneur": "on",
            "has_disability": "",
            "caste_category": "general",
            "document_readiness": "partial",
            "notes": "Needs startup help",
        }
        response = self.client.post(reverse("wizard"), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EligibilityAssessment.objects.count(), 1)
        self.assertContains(response, "recommendation")

    def test_wizard_focus_submission_maps_to_support_need(self):
        payload = {
            "language": "en",
            "need_focus": "student",
            "age": 19,
            "annual_income": 90000,
            "income_band": "under_1l",
            "gender": "female",
            "state": "Maharashtra",
            "district": "Pune",
            "residence_type": "urban",
            "support_need": "",
            "caste_category": "general",
            "document_readiness": "partial",
            "notes": "Needs study help",
        }
        response = self.client.post(reverse("wizard"), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EligibilityAssessment.objects.count(), 1)
        assessment = EligibilityAssessment.objects.first()
        self.assertEqual(assessment.support_need, "education")
        self.assertTrue(assessment.is_student)

    def test_support_submission_creates_request(self):
        payload = {
            "name": "Asha",
            "phone_number": "9999999999",
            "email": "asha@example.com",
            "preferred_language": "en",
            "support_type": "callback",
            "state": "Maharashtra",
            "district": "Pune",
            "message": "Need offline help with documents",
        }
        response = self.client.post(reverse("support"), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EscalationRequest.objects.count(), 1)
        self.assertContains(response, "saved")


class CitizenAuthProfileTests(TestCase):
    def test_register_creates_user_and_profile(self):
        response = self.client.post(
            reverse("citizen_register"),
            data={
                "username": "citizen1",
                "email": "citizen1@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_user_model().objects.filter(username="citizen1").exists())
        user = get_user_model().objects.get(username="citizen1")
        self.assertTrue(CitizenProfile.objects.filter(user=user).exists())

    def test_login_and_personalized_schemes_mode(self):
        user = get_user_model().objects.create_user(username="citizen2", password="StrongPass123!")
        CitizenProfile.objects.create(
            user=user,
            age=24,
            annual_income=180000,
            income_band="under_2l",
            gender="female",
            state="Maharashtra",
            district="Pune",
            residence_type="urban",
            support_need="education",
            document_readiness="partial",
        )
        self.client.post(
            reverse("citizen_login"),
            data={"username": "citizen2", "password": "StrongPass123!"},
        )
        response = self.client.get(reverse("schemes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personalized mode active")

    def test_profile_page_requires_login(self):
        response = self.client.get(reverse("citizen_profile"))
        self.assertEqual(response.status_code, 302)


class ChatApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_chat_api_requires_csrf(self):
        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_chat_api_accepts_valid_request(self):
        home_response = self.client.get(reverse("home"))
        csrftoken = home_response.cookies["csrftoken"].value

        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps(
                {
                    "message": "I am 24, female, income 180000, from Maharashtra, need financial support",
                    "lang": "en",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("reply", payload)
        self.assertEqual(ChatHistory.objects.count(), 1)
        self.assertGreaterEqual(ChatHistory.objects.first().matched_scheme_count, 0)


class OperationsAndSeedTests(TestCase):
    def test_seed_command_populates_scheme_table(self):
        self.assertEqual(Scheme.objects.count(), 0)
        call_command("seed_schemes")
        self.assertGreaterEqual(Scheme.objects.count(), 1)

    def test_sync_state_portals_creates_records(self):
        call_command("sync_state_portals", limit=5, skip_url_check=True)
        created = Scheme.objects.filter(name__icontains="Official Scheme Portal").count()
        self.assertGreaterEqual(created, 5)

    def test_verified_state_registry_includes_portal_fallback_states(self):
        from women_app.state_source_registry import load_state_verified_sources

        load_state_verified_sources.cache_clear()
        sources = load_state_verified_sources()
        states = {item["state"] for item in sources}
        self.assertIn("Tripura", states)
        self.assertGreaterEqual(len(states), 36)

    @patch("women_app.management.commands.crawl_state_verified_sources.crawl_source_for_scheme_links")
    @patch("women_app.management.commands.crawl_state_verified_sources.load_state_verified_sources")
    def test_crawl_state_verified_sources_creates_discovered_records(self, mock_load_sources, mock_crawler):
        mock_load_sources.return_value = [
            {
                "state": "Maharashtra",
                "source_name": "MahaDBT Scholarship and Benefit Portal",
                "url": "https://mahadbt.maharashtra.gov.in",
                "category": "education",
                "tags": ["student", "scholarship", "mahadbt"],
            }
        ]
        mock_crawler.return_value = [
            {
                "url": "https://mahadbt.maharashtra.gov.in/scheme/test-scheme",
                "label": "Post Matric Scholarship Scheme",
                "score": 3,
            }
        ]

        call_command(
            "crawl_state_verified_sources",
            max_pages=1,
            max_links_per_source=5,
            limit_sources=1,
        )

        scheme = Scheme.objects.get(url="https://mahadbt.maharashtra.gov.in/scheme/test-scheme")
        self.assertEqual(scheme.official_source_name, "MahaDBT Scholarship and Benefit Portal")
        self.assertIn("Maharashtra", scheme.state_coverage)

    def test_ops_dashboard_requires_staff_login(self):
        response = self.client.get(reverse("ops_dashboard"))
        self.assertEqual(response.status_code, 302)

        user = get_user_model().objects.create_user(
            username="opsadmin",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("ops_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operations")

    def test_ops_dashboard_post_updates_escalation(self):
        user = get_user_model().objects.create_user(
            username="opsmanager",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        escalation = EscalationRequest.objects.create(
            name="Kiran",
            phone_number="9000000000",
            email="kiran@example.com",
            preferred_language="en",
            support_type="callback",
            state="Maharashtra",
            district="Pune",
            message="Need support",
            status="new",
        )

        self.client.force_login(user)
        due_value = (timezone.now() + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("ops_dashboard"),
            data={
                "escalation_id": escalation.id,
                "status": "in_progress",
                "assigned_to": str(user.id),
                "due_at": due_value,
                "resolution_notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        escalation.refresh_from_db()
        self.assertEqual(escalation.status, "in_progress")
        self.assertEqual(escalation.assigned_to_id, user.id)


class SupportApiTests(TestCase):
    def test_help_center_api_returns_data(self):
        response = self.client.get(reverse("help_center_api"), {"state": "Maharashtra", "district": "Pune"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("centers", payload)
        self.assertGreaterEqual(len(payload["centers"]), 1)

    def test_speech_to_text_api_requires_audio(self):
        response = self.client.post(reverse("speech_to_text_api"), data={"lang": "hi"})
        self.assertEqual(response.status_code, 400)

    @patch("women_app.views.synthesize_speech_mp3")
    def test_text_to_speech_api_returns_audio(self, mock_tts):
        mock_tts.return_value = b"fake-audio"
        response = self.client.post(
            reverse("text_to_speech_api"),
            data=json.dumps({"text": "Hello", "lang": "en"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")


class MySchemeEnrichmentTests(TestCase):
    def test_merge_detail_enriches_summary_record(self):
        summary = {
            "name": "Sample Scheme",
            "slug": "sample-scheme",
            "category": "other",
            "description": "Short",
            "eligibility": "Open official portal",
            "min_age": 0,
            "max_age": 120,
            "income_limit": 99999999,
            "gender": "any",
            "official_source_name": "myScheme",
            "url": "https://www.myscheme.gov.in/schemes/sample-scheme",
            "verification_status": "verified",
            "last_verified_on": "2026-03-01",
            "verification_notes": "Imported",
            "state_coverage": ["All India"],
            "district_coverage": [],
            "beneficiary_tags": ["student"],
            "expiry_date": "",
            "required_documents": [],
            "where_to_apply": "Open portal",
            "offline_location": "myScheme",
            "helpline": "",
            "effort_level": "medium",
        }
        detail = {
            "slug": "sample-scheme",
            "brief_description": "Detailed summary",
            "eligibility_text": "Students from low-income households",
            "documents": ["Aadhaar card", "Income certificate", "Bank details"],
            "application_steps": ["Register on portal", "Submit documents"],
            "quick_links": [{"label": "Apply online", "url": "https://example.gov.in/apply"}],
            "nodal_ministry": "Ministry of Education",
            "nodal_department": "Scholarship Division",
            "categories": ["Education & Learning"],
            "state_coverage": ["Maharashtra", "Karnataka"],
            "tags": ["student", "scholarship"],
            "faqs": [{"question": "Need help?", "answer_md": "Call 1800-123-456"}],
            "description": "Call 1800-123-456 for support",
        }

        merged = merge_myscheme_detail_into_record(summary, detail)

        self.assertEqual(merged["category"], "education")
        self.assertEqual(merged["official_source_name"], "Ministry of Education")
        self.assertEqual(merged["offline_location"], "Scholarship Division")
        self.assertEqual(merged["where_to_apply"], "Register on portal Submit documents")
        self.assertEqual(merged["required_documents"], ["Aadhaar card", "Income certificate", "Bank details"])
        self.assertEqual(merged["state_coverage"], ["Maharashtra", "Karnataka"])
        self.assertEqual(merged["verification_status"], "verified")
        self.assertEqual(merged["last_verified_on"], date.today().isoformat())
        self.assertIn("Enriched from official myScheme scheme detail endpoint.", merged["verification_notes"])
        self.assertTrue(merged["helpline"])

    def test_merge_detail_without_payload_keeps_summary(self):
        summary = {
            "name": "Sample Scheme",
            "slug": "sample-scheme",
            "category": "education",
            "description": "desc",
            "eligibility": "eligibility",
            "official_source_name": "myScheme",
            "url": "https://www.myscheme.gov.in/schemes/sample-scheme",
            "verification_status": "verified",
            "last_verified_on": "2026-03-01",
            "verification_notes": "Imported",
            "state_coverage": ["All India"],
            "district_coverage": [],
            "beneficiary_tags": ["student"],
            "required_documents": [],
            "where_to_apply": "Open portal",
            "offline_location": "myScheme",
            "helpline": "",
            "effort_level": "medium",
        }

        merged = merge_myscheme_detail_into_record(summary, None)
        self.assertEqual(merged, summary)

    @patch("women_app.myscheme_api.get_state_district_map")
    def test_merge_detail_expands_districts_from_state_coverage(self, mock_district_map):
        mock_district_map.return_value = {
            "Tripura": ["West Tripura", "Dhalai"],
        }
        summary = {
            "name": "Tripura Scheme",
            "slug": "tripura-scheme",
            "category": "education",
            "description": "desc",
            "eligibility": "eligibility",
            "official_source_name": "myScheme",
            "url": "https://www.myscheme.gov.in/schemes/tripura-scheme",
            "verification_status": "verified",
            "last_verified_on": "2026-03-01",
            "verification_notes": "Imported",
            "state_coverage": ["Tripura"],
            "district_coverage": [],
            "beneficiary_tags": ["student"],
            "required_documents": [],
            "where_to_apply": "Open portal",
            "offline_location": "myScheme",
            "helpline": "",
            "effort_level": "medium",
        }
        detail = {
            "slug": "tripura-scheme",
            "state_coverage": ["Tripura"],
            "district_coverage": [],
            "tags": ["student"],
            "quick_links": [],
            "documents": [],
            "application_steps": [],
            "faqs": [],
        }

        merged = merge_myscheme_detail_into_record(summary, detail)
        self.assertEqual(merged["district_coverage"], ["West Tripura", "Dhalai"])

    @patch("women_app.myscheme_api.get_state_district_map")
    def test_backfill_district_coverage_command_updates_state_targeted_scheme(self, mock_district_map):
        mock_district_map.return_value = {
            "Tripura": ["West Tripura", "Dhalai"],
        }
        scheme = Scheme.objects.create(
            name="Tripura Support Scheme",
            category="education",
            description="desc",
            eligibility="eligibility",
            min_age=0,
            max_age=60,
            income_limit=999999,
            gender="any",
            official_source_name="Department",
            url="https://www.myscheme.gov.in/schemes/tripura-support-scheme",
            verification_status="verified",
            state_coverage="Tripura",
            district_coverage="",
            beneficiary_tags="student",
            where_to_apply="Portal",
            effort_level="medium",
        )

        call_command("backfill_district_coverage", only_empty=True, limit=10)
        scheme.refresh_from_db()
        self.assertIn("West Tripura", scheme.district_coverage)
        self.assertIn("Dhalai", scheme.district_coverage)
