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

    def test_ask_a_legal_question_links_to_task_create(self):
        response = self.client_.get(reverse('contracts:legal_front_door'))
        self.assertContains(response, 'Ask a legal question')
        self.assertContains(response, reverse('contracts:legal_task_create'))
        self.assertNotContains(response, 'Coming soon')

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
        self.assertContains(response, reverse('contracts:document_extract_preview_api'))
        self.assertContains(response, 'usc-dropzone')
        self.assertContains(response, 'Upload agreement')
        self.assertContains(response, 'Confirm agreement details')
        self.assertContains(response, 'Review settings')
        self.assertContains(response, 'What happens next')
        self.assertContains(response, 'Most details are optional and may be extracted from the agreement.')
        self.assertContains(response, 'Upload an existing agreement for controlled analysis and review routing.')
        self.assertContains(response, 'uac-sticky-actions')
        self.assertContains(response, 'Create matter')
        self.assertContains(response, reverse('contracts:matter_create'))
        self.assertNotContains(response, '<select id="usc-matter">')
        self.assertNotContains(response, 'Contains a data processing agreement')
        self.assertNotContains(response, 'Source document and review')
        self.assertNotContains(response, 'Before you upload')
        self.assertTrue(response.context['hide_app_footer'])
        self.assertContains(response, 'contract_review_url')
        self.assertContains(response, "window.location.assign(result.data.contract_review_url)")
        self.assertContains(response, 'progress.blocked && review.requested')
        self.assertContains(response, 'Workflow progress')
        self.assertContains(response, 'function processingFromReview')
        self.assertContains(response, "'needs-input': 'Classifying'")
        self.assertContains(response, 'pending_confirmations')
        self.assertNotContains(response, "showProcessing(review.status === 'completed' ? 'Review ready' : 'AI reviewing')")

    @override_settings(GEMINI_AI_ENABLED=False, GEMINI_API_KEY='')
    def test_unconfigured_ai_is_explicitly_disabled_in_upload_ui(self):
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertContains(response, 'Manual review only')
        self.assertContains(response, 'AI review is not configured for this environment')
        self.assertContains(response, 'id="usc-run-ai-review"', html=False)
        self.assertContains(response, 'disabled', html=False)

    @override_settings(GEMINI_AI_ENABLED=True, GEMINI_API_KEY='test-provider-key')
    def test_configured_workspace_can_opt_in_to_ai_review(self):
        OrgPolicy.objects.create(organization=self.org, ai_features_enabled=True)
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertContains(response, 'AI review available · Human review required')
        self.assertContains(response, 'id="usc-run-ai-review" checked', html=False)
        self.assertContains(response, 'Run AI clause review')
        self.assertNotContains(response, 'Run AI clause review after upload')

    def test_related_matter_dropdown_appears_when_matters_exist(self):
        from contracts.models import Client, Matter

        client_obj = Client.objects.create(organization=self.org, name='Acme Client')
        Matter.objects.create(organization=self.org, client=client_obj, title='Acme Engagement')
        response = self.client_.get(reverse('contracts:upload_signed_contract'))
        self.assertContains(response, '<select id="usc-matter">')
        self.assertContains(response, 'Acme Engagement')
        self.assertNotContains(response, 'No matters in this workspace yet')


class DocumentExtractPreviewApiTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Extract Org', 'extract_user')

    def test_requires_login(self):
        response = TestClient().post(reverse('contracts:document_extract_preview_api'))
        self.assertEqual(response.status_code, 302)

    def test_extracts_metadata_without_creating_contract(self):
        from contracts.models import Contract, Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        payload = (
            b'Master Service Agreement between Acme and Northwind.\n'
            b'Effective date: 2026-03-01\n'
            b'Governed by the laws of England and Wales.\n'
            b'Contract value EUR 50,000.00\n'
            b'Personal data processing and GDPR controller obligations apply.\n'
        )
        upload = SimpleUploadedFile('msa.txt', payload, content_type='text/plain')
        before_contracts = Contract.objects.count()
        before_docs = Document.objects.count()
        response = self.client_.post(
            reverse('contracts:document_extract_preview_api'),
            {'file': upload},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        extraction = data['extraction']
        self.assertEqual(extraction['contract_type']['value'], 'MSA')
        self.assertTrue(extraction['governing_law']['value'])
        self.assertEqual(extraction['value']['value'], '50000.00')
        self.assertEqual(extraction['possible_dpa']['value'], 'true')
        self.assertEqual(Contract.objects.count(), before_contracts)
        self.assertEqual(Document.objects.count(), before_docs)

    def test_rejects_missing_file(self):
        response = self.client_.post(reverse('contracts:document_extract_preview_api'), {})
        self.assertEqual(response.status_code, 400)
