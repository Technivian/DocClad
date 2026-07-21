"""Phase 11 — Backlog amplifiers: team queue, combobox, decision suggest, charts."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Organization,
    OrganizationMembership,
    WorkInteractionEvent,
)
from contracts.services.ai_decision_assist import suggest_approval_decision_comment
from contracts.services.assignments import get_active_work_items
from contracts.services.work_instrumentation import build_operating_metrics
from contracts.view_support import reassign_member_options

User = get_user_model()


class Phase11BacklogAmplifiersTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Amp Org", slug="amp-org")
        self.admin = User.objects.create_user(username="amp_admin", password="pass")
        self.member = User.objects.create_user(username="amp_member", password="pass")
        self.teammate = User.objects.create_user(
            username="amp_teammate", password="pass", first_name="Ada", last_name="Assignee",
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member, role=OrganizationMembership.Role.MEMBER,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.teammate, role=OrganizationMembership.Role.MEMBER,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title="Amp MSA",
            contract_type="MSA",
            status=Contract.Status.IN_PROGRESS,
            created_by=self.admin,
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step="legal_review",
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.teammate,
            due_date=timezone.localdate(),
        )
        self.client = Client()

    def test_member_cannot_force_team_scope(self):
        self.client.login(username="amp_member", password="pass")
        response = self.client.get(reverse("contracts:my_work") + "?scope=team")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_team_queue"])
        self.assertEqual(response.context["work_scope"], "personal")
        self.assertNotIn("Team queue", response.content.decode())

    def test_team_scope_includes_teammate_approval_for_admin(self):
        personal = get_active_work_items(self.org, self.admin, scope="personal")
        team = get_active_work_items(self.org, self.admin, scope="team")
        personal_ids = {row["id"] for row in personal}
        team_ids = {row["id"] for row in team}
        self.assertNotIn(f"approval:{self.approval.pk}", personal_ids)
        self.assertIn(f"approval:{self.approval.pk}", team_ids)
        team_row = next(row for row in team if row["id"] == f"approval:{self.approval.pk}")
        self.assertEqual(team_row.get("assignee_id"), self.teammate.pk)

    def test_reassign_options_include_workload_and_sort(self):
        options = reassign_member_options(self.org)
        teammate = next(row for row in options if row["id"] == self.teammate.pk)
        self.assertGreaterEqual(teammate["open_count"], 1)
        counts = [row["open_count"] for row in options]
        self.assertEqual(counts, sorted(counts))

    def test_suggest_decision_comment_template_fallback(self):
        result = suggest_approval_decision_comment(self.approval, "return", allow_ai=False)
        self.assertEqual(result["source"], "template")
        self.assertIn("Returning", result["suggestion"])
        self.assertEqual(result["decision"], "return")

    def test_suggest_decision_api_for_assignee(self):
        self.client.login(username="amp_teammate", password="pass")
        url = reverse("contracts:approval_suggest_decision_api", kwargs={"approval_id": self.approval.pk})
        response = self.client.post(
            url,
            data='{"decision":"reject"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("suggestion", payload)
        self.assertIn(payload.get("source"), {"template", "ai"})

    def test_work_health_charts_and_daily_series(self):
        WorkInteractionEvent.objects.create(
            organization=self.org,
            user=self.admin,
            event="completed",
            surface="my_work",
            work_item_id=f"approval:{self.approval.pk}",
            work_kind="approval",
            contract_id=self.contract.pk,
            contract_type="MSA",
        )
        WorkInteractionEvent.objects.create(
            organization=self.org,
            user=self.admin,
            event="surfaced",
            surface="my_work",
            work_item_id=f"approval:{self.approval.pk}",
            work_kind="approval",
            is_overdue=True,
            contract_id=self.contract.pk,
            contract_type="MSA",
        )
        metrics = build_operating_metrics(self.org, days=7)
        self.assertIn("daily_activity", metrics["metrics"])
        self.assertTrue(metrics["metrics"]["daily_activity"])

        self.client.login(username="amp_admin", password="pass")
        response = self.client.get(reverse("contracts:work_health_report"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("daily_series", response.context)
        content = response.content.decode()
        self.assertIn("wh-meter", content)
        self.assertIn("wh-bar", content)
        self.assertIn("Daily activity", content)
