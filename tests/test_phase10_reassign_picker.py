"""Phase 10 — Reassign assignee picker (name select + reason, no numeric ID prompt)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership
from contracts.view_support import reassign_member_options

User = get_user_model()


class Phase10ReassignPickerTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Picker Org", slug="picker-org")
        self.admin = User.objects.create_user(username="picker_admin", password="pass")
        self.member = User.objects.create_user(username="picker_member", password="pass")
        self.teammate = User.objects.create_user(
            username="picker_teammate",
            password="pass",
            first_name="Tess",
            last_name="Teammate",
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member, role=OrganizationMembership.Role.MEMBER
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.teammate, role=OrganizationMembership.Role.MEMBER
        )
        self.client = Client()

    def test_reassign_member_options_lists_org_members(self):
        options = reassign_member_options(self.org)
        ids = {row["id"] for row in options}
        self.assertIn(self.admin.pk, ids)
        self.assertIn(self.member.pk, ids)
        self.assertIn(self.teammate.pk, ids)
        teammate = next(row for row in options if row["id"] == self.teammate.pk)
        self.assertIn("Tess", teammate["label"])
        self.assertEqual(teammate["username"], "picker_teammate")
        self.assertIn("open_count", teammate)
        self.assertIn("search", teammate)

    def test_my_work_admin_gets_reassign_members_and_dialog(self):
        self.client.login(username="picker_admin", password="pass")
        response = self.client.get(reverse("contracts:my_work"))
        self.assertEqual(response.status_code, 200)
        members = response.context["reassign_members"]
        ids = {row["id"] for row in members}
        self.assertIn(self.teammate.pk, ids)
        content = response.content.decode()
        self.assertIn("my-work-reassign-dialog", content)
        self.assertIn("data-reassign-assignee", content)
        self.assertIn("data-reassign-search", content)
        self.assertIn("data-reassign-options", content)
        self.assertIn("reassign-members-data", content)
        self.assertIn("my-work-decision-dialog", content)
        self.assertIn("data-decision-suggest", content)
        self.assertNotIn("Enter the new assignee user id", content)
        self.assertNotIn("User ID:", content)

    def test_my_work_member_has_empty_reassign_members(self):
        self.client.login(username="picker_member", password="pass")
        response = self.client.get(reverse("contracts:my_work"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reassign_members"], [])

    def test_approvals_admin_gets_reassign_members_and_dialog(self):
        self.client.login(username="picker_admin", password="pass")
        response = self.client.get(reverse("contracts:approval_request_list"))
        self.assertEqual(response.status_code, 200)
        members = response.context["reassign_members"]
        ids = {row["id"] for row in members}
        self.assertIn(self.teammate.pk, ids)
        content = response.content.decode()
        self.assertIn("approvals-reassign-dialog", content)
        self.assertIn("data-reassign-assignee", content)
        self.assertIn("data-reassign-search", content)
        self.assertIn("openReassignDialog", content)
        self.assertIn("approvals-decision-dialog", content)
        self.assertIn("openDecisionCommentDialog", content)
        self.assertNotIn("Enter user ID", content)

    def test_my_work_team_queue_toggle_for_admin(self):
        self.client.login(username="picker_admin", password="pass")
        response = self.client.get(reverse("contracts:my_work") + "?scope=team")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_view_team_queue"])
        self.assertEqual(response.context["work_scope"], "team")
        content = response.content.decode()
        self.assertIn("Team queue", content)
        self.assertIn("Open work across your organization", content)
        self.assertIn("data-col=\"assignee\"", content)
        self.assertIn("my-work-filter-assignee", content)
