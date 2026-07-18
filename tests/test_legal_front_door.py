"""Covers the Legal Front Door entry screen and the Upload Signed Contract
screen — both additive, link-only/thin-wrapper views introduced alongside
the CLM One Legal Work Engine plan. Neither introduces a new domain model;
this file checks routing, permission gating, and (for upload) that the
screen's own template renders and correctly targets the pre-existing,
unmodified document_upload_api.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership, OrgPolicy

User = get_user_model()


def _make_org_with_user(label, username):
    org = Organization.objects.create(name=f'{label} {username}', slug=f'{label.lower().replace(" ", "-")}-{username}')
    user = User.objects.create_user(username=username, password='testpass123!')
    OrganizationMembership.objects.create(organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True)
    client_ = TestClient()
    client_.login(username=username, password='testpass123!')
    return org, user, client_


class LegalFrontDoorViewTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Front Door Org', 'front_door_user')

    def test_requires_login(self):
        anon_client = TestClient()
        response = anon_client.get(reverse('contracts:legal_front_door'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_renders_all_seven_options(self):
        response = self.client_.get(reverse('contracts:legal_front_door'))
        self.assertEqual(response.status_code, 200)
        for title in (
            'Create a contract', 'Review a contract', 'Upload signed contract',
            'Start DPA review', 'Ask a legal question', 'Request approval',
            'Start renewal / amendment',
        ):
            self.assertContains(response, title)

    def test_ask_a_legal_question_is_marked_coming_soon_and_not_linked(self):
        response = self.client_.get(reverse('contracts:legal_front_door'))
        self.assertContains(response, 'Coming soon')
        # The coming-soon option must not render as a clickable card wrapper.
        self.assertNotContains(response, '<a href="None"')

    def test_options_link_to_existing_routes(self):
        response = self.client_.get(reverse('contracts:legal_front_door'))
        self.assertContains(response, reverse('contracts:contract_template_picker'))
        self.assertContains(response, reverse('contracts:repository'))
        self.assertContains(response, reverse('contracts:upload_signed_contract'))
        self.assertContains(response, reverse('contracts:dpa_review_pack_list'))
        self.assertContains(response, reverse('contracts:approval_request_list'))
        self.assertContains(response, f"{reverse('contracts:contract_create')}?type=AMENDMENT")


class UploadSignedContractViewTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Upload Org', 'upload_user')

    def test_requires_login(self):
        anon_client = TestClient()
        response = anon_client.get(reverse('contracts:upload_signed_contract'))
        self.assertEqual(response.status_code, 302)

    def test_get_renders_upload_form_targeting_the_existing_api(self):
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('contracts:document_upload_api'))
        self.assertContains(response, 'usc-dropzone')
        self.assertContains(response, 'contract_review_url')
        self.assertContains(response, "window.location.assign(result.data.contract_review_url)")

    @override_settings(GEMINI_AI_ENABLED=False, GEMINI_API_KEY='')
    def test_unconfigured_ai_is_explicitly_disabled_in_upload_ui(self):
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertContains(response, 'Manual review only')
        self.assertContains(response, 'AI review is not configured for this environment')
        self.assertContains(response, 'id="usc-run-ai-review" disabled', html=False)

    @override_settings(GEMINI_AI_ENABLED=True, GEMINI_API_KEY='test-provider-key')
    def test_configured_workspace_can_opt_in_to_ai_review(self):
        OrgPolicy.objects.create(organization=self.org, ai_features_enabled=True)
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertContains(response, 'AI review available · Human review required')
        self.assertContains(response, 'id="usc-run-ai-review" checked', html=False)
