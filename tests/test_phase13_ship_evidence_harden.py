"""Phase 13 — Ship readiness: adoption evidence + team-queue hardening."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Organization,
    OrganizationMembership,
)
from contracts.services.assignments import TEAM_QUEUE_ROW_LIMIT, get_active_work_items_result
from contracts.services.work_instrumentation import build_adoption_evidence, record_adoption_event
from contracts.view_support import open_work_count_by_user

User = get_user_model()


class Phase13ShipEvidenceHardenTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Ship Org", slug="ship-org")
        self.admin = User.objects.create_user(username="ship_admin", password="pass")
        self.teammate = User.objects.create_user(username="ship_teammate", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.teammate, role=OrganizationMembership.Role.MEMBER,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title="Ship MSA",
            contract_type="MSA",
            status=Contract.Status.IN_PROGRESS,
            created_by=self.admin,
        )
        self.client = Client()

    def test_adoption_evidence_and_work_health_panel(self):
        record_adoption_event(
            organization=self.org, user=self.admin, evidence_key="team_queue",
        )
        record_adoption_event(
            organization=self.org, user=self.admin, evidence_key="assignee_search",
        )
        evidence = build_adoption_evidence(self.org, days=7)
        self.assertGreaterEqual(evidence["signals"]["team_queue_views"], 1)
        self.assertGreaterEqual(evidence["signals"]["assignee_searches"], 1)
        self.assertIn("gates", evidence)

        self.client.login(username="ship_admin", password="pass")
        response = self.client.get(reverse("contracts:work_health_report") + "?days=7")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("adoption_cards"))
        self.assertIn("Adoption evidence", response.content.decode())

    def test_team_queue_cap_and_evidence_recording(self):
        for i in range(3):
            ApprovalRequest.objects.create(
                organization=self.org,
                contract=self.contract,
                approval_step=f"step_{i}",
                status=ApprovalRequest.Status.PENDING,
                assigned_to=self.teammate,
                due_date=timezone.now(),
            )
        result = get_active_work_items_result(self.org, self.admin, scope="team", row_limit=2)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertGreaterEqual(result["total_before_cap"], 3)
        self.assertEqual(TEAM_QUEUE_ROW_LIMIT, 250)

        self.client.login(username="ship_admin", password="pass")
        response = self.client.get(reverse("contracts:my_work") + "?scope=team")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["work_scope"], "team")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_open_work_count_is_cached(self):
        cache.clear()
        first = open_work_count_by_user(self.org)
        second = open_work_count_by_user(self.org)
        self.assertEqual(first, second)

    def test_evidence_beacon_api(self):
        self.client.login(username="ship_admin", password="pass")
        response = self.client.post(
            reverse("contracts:work_interaction_api"),
            data='{"evidence":"suggest_applied","surface":"my_work"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        evidence = build_adoption_evidence(self.org, days=7)
        self.assertGreaterEqual(evidence["signals"]["suggest_applied"], 1)
