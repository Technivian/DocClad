"""Phase 12 — Backlog polish: live assignee search, trends, more decision suggests."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
    WorkInteractionEvent,
)
from contracts.services.ai_decision_assist import suggest_work_action_comment
from contracts.services.work_instrumentation import build_operating_trends
from contracts.view_support import reassign_member_options

User = get_user_model()


class Phase12BacklogPolishTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Polish Org", slug="polish-org")
        self.admin = User.objects.create_user(username="polish_admin", password="pass")
        self.member = User.objects.create_user(
            username="polish_member", password="pass", first_name="Pat", last_name="Member",
        )
        self.teammate = User.objects.create_user(
            username="polish_teammate", password="pass", first_name="Quinn", last_name="Teammate",
        )
        for user, role in (
            (self.admin, OrganizationMembership.Role.ADMIN),
            (self.member, OrganizationMembership.Role.MEMBER),
            (self.teammate, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(organization=self.org, user=user, role=role)
        self.contract = Contract.objects.create(
            organization=self.org,
            title="Polish MSA",
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
            due_date=timezone.now(),
        )
        self.client = Client()

    def test_reassign_member_options_filters_and_limits(self):
        options = reassign_member_options(self.org, q="Quinn", limit=10)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["username"], "polish_teammate")
        capped = reassign_member_options(self.org, limit=1)
        self.assertEqual(len(capped), 1)

    def test_assignee_options_api_admin_only(self):
        url = reverse("contracts:assignee_options_api")
        self.client.login(username="polish_member", password="pass")
        denied = self.client.get(url, {"q": "Quinn"})
        self.assertEqual(denied.status_code, 403)

        self.client.login(username="polish_admin", password="pass")
        ok = self.client.get(url, {"q": "Quinn", "limit": "10"})
        self.assertEqual(ok.status_code, 200)
        payload = ok.json()
        self.assertTrue(payload.get("ok"))
        usernames = {row["username"] for row in payload["members"]}
        self.assertIn("polish_teammate", usernames)

    def test_work_suggest_comment_reassign_and_escalate(self):
        reassign = suggest_work_action_comment(
            "reassign", approval=self.approval, allow_ai=False,
        )
        self.assertEqual(reassign["source"], "template")
        self.assertIn("Reassigning", reassign["suggestion"])

        deadline = Deadline.objects.create(
            title="File renewal notice",
            contract=self.contract,
            assigned_to=self.member,
            due_date=timezone.localdate() + timedelta(days=3),
            created_by=self.admin,
            deadline_type=Deadline.DeadlineType.RENEWAL,
            priority=Deadline.Priority.HIGH,
        )
        escalate = suggest_work_action_comment(
            "escalate", deadline=deadline, allow_ai=False,
        )
        self.assertIn("Escalating", escalate["suggestion"])

        self.client.login(username="polish_admin", password="pass")
        response = self.client.post(
            reverse("contracts:work_suggest_comment_api"),
            data=f'{{"kind":"reassign","approval_id":{self.approval.pk}}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("suggestion", response.json())

    def test_conflict_suggest_and_status_note(self):
        pack = DPAReviewPack.objects.create(
            organization=self.org,
            contract=self.contract,
            reviewer=self.member,
            approval_status=DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
            created_by=self.admin,
        )
        risk = DPARiskItem.objects.create(
            review_pack=pack,
            category=DPARiskItem.Category.LIABILITY,
            title="Cross-doc liability mismatch",
            description="MSA vs DPA liability caps disagree.",
            severity=DPARiskItem.Severity.HIGH,
            owners="LEGAL",
            is_cross_document_conflict=True,
            status=DPARiskItem.Status.OPEN,
        )
        suggestion = suggest_work_action_comment(
            "conflict_resolved", risk_item=risk, allow_ai=False,
        )
        self.assertIn("resolved", suggestion["suggestion"].lower())

        self.client.login(username="polish_member", password="pass")
        status_url = reverse("contracts:dpa_risk_item_set_status", kwargs={"pk": risk.pk})
        response = self.client.post(
            status_url,
            data='{"status":"RESOLVED","note":"Reconciled after counsel review."}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("note_id"))
        risk.refresh_from_db()
        self.assertEqual(risk.status, "RESOLVED")
        self.assertTrue(risk.notes.exists())

    def test_operating_trends_and_work_health_ui(self):
        now = timezone.now()
        WorkInteractionEvent.objects.create(
            organization=self.org,
            user=self.admin,
            event="completed",
            surface="my_work",
            work_item_id="approval:1",
            work_kind="approval",
            occurred_at=now - timedelta(days=1),
        )
        WorkInteractionEvent.objects.create(
            organization=self.org,
            user=self.admin,
            event="completed",
            surface="approvals",
            work_item_id="approval:2",
            work_kind="approval",
            occurred_at=now - timedelta(days=10),
        )
        trends = build_operating_trends(self.org, days=7)
        self.assertIn("completed_from_my_work_pct", trends["trends"])
        self.assertIn("direction", trends["trends"]["completed_from_my_work_pct"])

        self.client.login(username="polish_admin", password="pass")
        response = self.client.get(reverse("contracts:work_health_report") + "?days=7")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("trend_cards"))
        content = response.content.decode()
        self.assertIn("Period trends", content)
        self.assertIn("wh-trend", content)
        self.assertIn("data-reassign-suggest", self.client.get(reverse("contracts:my_work")).content.decode())
        self.assertIn("assignee-options", self.client.get(reverse("contracts:my_work")).content.decode())
