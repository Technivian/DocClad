"""Outbound e-signature dispatch.

Covers the provider abstraction (Null default + HTTP gateway), the
send_signature_request service (transition + idempotency) and the send view.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.models import (
    Contract,
    Document,
    Organization,
    OrganizationMembership,
    SignatureRequest,
)
from contracts.services.esign import refresh_signature_request, send_signature_request
from contracts.services.signature_providers import (
    DocumensoSignatureProvider,
    HttpSignatureProvider,
    NullSignatureProvider,
    SignatureProviderError,
    get_signature_provider,
)

User = get_user_model()


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class OutboundSignatureTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Firm Alpha', slug='esign-alpha')
        self.user = User.objects.create_user(username='esign_user', password='passA1234!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org, title='Alpha NDA', contract_type='NDA',
            status='ACTIVE', created_by=self.user,
        )
        self.sig = SignatureRequest.objects.create(
            organization=self.org, contract=self.contract,
            signer_name='Sam Signer', signer_email='sam@example.com',
            created_by=self.user,
        )

    def test_null_provider_sends_and_transitions(self):
        result = send_signature_request(self.sig, actor=self.user)
        self.sig.refresh_from_db()
        self.assertTrue(result['sent'])
        self.assertEqual(self.sig.status, SignatureRequest.Status.SENT)
        self.assertTrue(self.sig.external_id)
        self.assertEqual(self.sig.esign_provider, 'null')
        self.assertTrue(self.sig.sent_at)

    def test_send_is_idempotent(self):
        send_signature_request(self.sig, actor=self.user)
        again = send_signature_request(self.sig, actor=self.user)
        self.assertFalse(again['sent'])
        self.assertEqual(again['reason'], 'not_pending')

    def test_http_provider_parses_gateway_response(self):
        captured = {}

        def fake_opener(req, timeout=None):
            captured['url'] = req.full_url
            captured['auth'] = req.headers.get('Authorization')
            return _FakeResponse({'external_id': 'env-123', 'signing_url': 'https://sign.example/abc'})

        provider = HttpSignatureProvider('https://gw.example/v1', 'secret-key', opener=fake_opener)
        result = send_signature_request(self.sig, actor=self.user, provider=provider)
        self.sig.refresh_from_db()
        self.assertEqual(result['external_id'], 'env-123')
        self.assertEqual(self.sig.signing_url, 'https://sign.example/abc')
        self.assertEqual(self.sig.esign_provider, 'http')
        self.assertEqual(captured['url'], 'https://gw.example/v1/envelopes')
        self.assertEqual(captured['auth'], 'Bearer secret-key')

    def test_http_provider_missing_external_id_raises(self):
        provider = HttpSignatureProvider(
            'https://gw.example', 'k', opener=lambda req, timeout=None: _FakeResponse({})
        )
        with self.assertRaises(SignatureProviderError):
            provider.send(self.sig)

    @override_settings(ESIGN_PROVIDER='null')
    def test_factory_defaults_to_null(self):
        self.assertIsInstance(get_signature_provider(), NullSignatureProvider)

    @override_settings(ESIGN_PROVIDER='http', ESIGN_API_BASE='https://gw', ESIGN_API_KEY='k')
    def test_factory_builds_http_provider(self):
        self.assertIsInstance(get_signature_provider(), HttpSignatureProvider)

    def test_send_view_dispatches(self):
        self.client.login(username='esign_user', password='passA1234!')
        url = reverse('contracts:signature_request_send', kwargs={'pk': self.sig.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.sig.refresh_from_db()
        self.assertEqual(self.sig.status, SignatureRequest.Status.SENT)

    def test_send_view_cross_org_404(self):
        other = User.objects.create_user(username='other', password='passB1234!')
        other_org = Organization.objects.create(name='Beta', slug='esign-beta')
        OrganizationMembership.objects.create(
            organization=other_org, user=other,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='other', password='passB1234!')
        url = reverse('contracts:signature_request_send', kwargs={'pk': self.sig.pk})
        self.assertEqual(self.client.post(url).status_code, 404)


class DocuSignProviderTests(TestCase):
    def setUp(self):
        from contracts.models import Document
        self.org = Organization.objects.create(name='DS Org', slug='ds-org')
        self.user = User.objects.create_user(username='ds_user', password='p')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org, title='DS NDA', contract_type='NDA',
            status='ACTIVE', created_by=self.user,
        )
        self.document = Document.objects.create(
            organization=self.org, title='NDA.pdf', mime_type='application/pdf',
            uploaded_by=self.user,
        )
        from django.core.files.base import ContentFile
        self.document.file.save('nda.pdf', ContentFile(b'%PDF-1.4 test'), save=True)
        self.sig = SignatureRequest.objects.create(
            organization=self.org, contract=self.contract, document=self.document,
            signer_name='Dana Signer', signer_email='dana@example.com',
            created_by=self.user,
        )

    def _provider(self, opener):
        from contracts.services.signature_providers import DocuSignSignatureProvider
        return DocuSignSignatureProvider(
            'https://demo.docusign.net/restapi', 'acct-123', 'tok-abc', opener=opener,
        )

    def test_builds_envelope_and_parses_envelope_id(self):
        captured = {}

        def fake_opener(req, timeout=None):
            captured['url'] = req.full_url
            captured['auth'] = req.headers.get('Authorization')
            captured['payload'] = json.loads(req.data.decode('utf-8'))
            return _FakeResponse({'envelopeId': 'env-9', 'status': 'sent'})

        result = send_signature_request(self.sig, actor=self.user, provider=self._provider(fake_opener))
        self.sig.refresh_from_db()
        self.assertEqual(result['external_id'], 'env-9')
        self.assertEqual(self.sig.esign_provider, 'docusign')
        self.assertEqual(self.sig.status, SignatureRequest.Status.SENT)
        # Correct DocuSign envelopes endpoint + bearer auth + signer + document.
        self.assertEqual(captured['url'], 'https://demo.docusign.net/restapi/v2.1/accounts/acct-123/envelopes')
        self.assertEqual(captured['auth'], 'Bearer tok-abc')
        self.assertEqual(captured['payload']['status'], 'sent')
        self.assertEqual(captured['payload']['recipients']['signers'][0]['email'], 'dana@example.com')
        self.assertTrue(captured['payload']['documents'][0]['documentBase64'])

    def test_missing_document_raises(self):
        from contracts.services.signature_providers import SignatureProviderError
        self.sig.document = None
        self.sig.save()
        with self.assertRaises(SignatureProviderError):
            self._provider(lambda req, timeout=None: _FakeResponse({})).send(self.sig)

    def test_unconfigured_raises(self):
        from contracts.services.signature_providers import DocuSignSignatureProvider, SignatureProviderError
        provider = DocuSignSignatureProvider('', '', '', opener=lambda req, timeout=None: _FakeResponse({}))
        with self.assertRaises(SignatureProviderError):
            provider.send(self.sig)

    @override_settings(
        ESIGN_PROVIDER='docusign', ESIGN_DOCUSIGN_BASE_URI='https://demo.docusign.net/restapi',
        ESIGN_DOCUSIGN_ACCOUNT_ID='a', ESIGN_DOCUSIGN_ACCESS_TOKEN='t',
    )
    def test_factory_builds_docusign(self):
        from contracts.services.signature_providers import get_signature_provider, DocuSignSignatureProvider
        self.assertIsInstance(get_signature_provider(), DocuSignSignatureProvider)


class DocumensoProviderTests(TestCase):
    def setUp(self):
        from django.core.files.base import ContentFile

        self.org = Organization.objects.create(name='Documenso Org', slug='documenso-org')
        self.user = User.objects.create_user(username='documenso_user', password='p')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Documenso MSA',
            contract_type='MSA',
            status='ACTIVE',
            created_by=self.user,
        )
        self.document = Document.objects.create(
            organization=self.org,
            title='Documenso MSA.pdf',
            mime_type='application/pdf',
            uploaded_by=self.user,
        )
        self.document.file.save('documenso-msa.pdf', ContentFile(b'%PDF-1.4 test'), save=True)
        self.sig = SignatureRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            document=self.document,
            signer_name='Demi Signer',
            signer_email='demi@example.com',
            created_by=self.user,
        )

    def test_v2_provider_creates_and_distributes_envelope(self):
        captured = []
        responses = iter([
            {'id': 'envelope_demo_123'},
            {
                'success': True,
                'id': 'envelope_demo_123',
                'recipients': [{
                    'email': 'demi@example.com',
                    'signingUrl': 'https://app.documenso.com/sign/demo-token',
                }],
            },
        ])

        def fake_opener(req, timeout=None):
            captured.append(req)
            return _FakeResponse(next(responses))

        provider = DocumensoSignatureProvider(
            'api_demo_key',
            base_url='https://app.documenso.com',
            opener=fake_opener,
        )
        result = send_signature_request(self.sig, actor=self.user, provider=provider)
        self.sig.refresh_from_db()

        self.assertEqual(result['external_id'], 'envelope_demo_123')
        self.assertEqual(result['signing_url'], 'https://app.documenso.com/sign/demo-token')
        self.assertEqual(self.sig.esign_provider, 'documenso')
        self.assertEqual(self.sig.status, SignatureRequest.Status.SENT)
        self.assertEqual(captured[0].full_url, 'https://app.documenso.com/api/v2/envelope/create')
        self.assertEqual(captured[0].headers.get('Authorization'), 'api_demo_key')
        self.assertIn(b'"externalId": "clmone-', captured[0].data)
        self.assertIn(b'name="payload"', captured[0].data)
        self.assertIn(b'name="files"', captured[0].data)
        self.assertEqual(captured[1].full_url, 'https://app.documenso.com/api/v2/envelope/distribute')
        self.assertEqual(json.loads(captured[1].data.decode())['envelopeId'], 'envelope_demo_123')

    def test_refresh_maps_opened_recipient_to_viewed(self):
        self.sig.status = SignatureRequest.Status.SENT
        self.sig.esign_provider = 'documenso'
        self.sig.external_id = 'envelope_demo_456'
        self.sig.save()

        provider = DocumensoSignatureProvider(
            'api_demo_key',
            opener=lambda req, timeout=None: _FakeResponse({
                'id': 'envelope_demo_456',
                'status': 'PENDING',
                'updatedAt': '2026-07-16T10:00:00Z',
                'recipients': [{
                    'email': 'demi@example.com',
                    'readStatus': 'OPENED',
                    'signingStatus': 'NOT_SIGNED',
                }],
            }),
        )
        result = refresh_signature_request(self.sig, provider=provider)
        self.sig.refresh_from_db()
        self.assertTrue(result['changed'])
        self.assertEqual(self.sig.status, SignatureRequest.Status.VIEWED)

    @patch('contracts.views_domains.privacy_approvals.refresh_signature_request')
    def test_detail_exposes_webhook_free_refresh_action(self, mocked_refresh):
        self.sig.status = SignatureRequest.Status.SENT
        self.sig.esign_provider = 'documenso'
        self.sig.external_id = 'envelope_demo_refresh'
        self.sig.save()
        mocked_refresh.return_value = {
            'refreshed': True,
            'changed': False,
            'status': SignatureRequest.Status.SENT,
        }

        self.client.login(username='documenso_user', password='p')
        detail_url = reverse('contracts:signature_request_detail', kwargs={'pk': self.sig.pk})
        detail = self.client.get(detail_url)
        self.assertContains(detail, 'Refresh signing status')

        refresh_url = reverse('contracts:signature_request_refresh', kwargs={'pk': self.sig.pk})
        response = self.client.post(refresh_url)
        self.assertRedirects(response, detail_url)
        mocked_refresh.assert_called_once()

    @override_settings(
        ESIGN_PROVIDER='documenso',
        ESIGN_DOCUMENSO_API_KEY='api_demo_key',
        ESIGN_DOCUMENSO_BASE_URL='https://app.documenso.com',
    )
    def test_factory_builds_documenso(self):
        self.assertIsInstance(get_signature_provider(), DocumensoSignatureProvider)

    @override_settings(ESIGN_DOCUMENSO_WEBHOOK_SECRET='webhook-demo-secret')
    def test_v2_completed_webhook_marks_request_signed(self):
        self.sig.status = SignatureRequest.Status.SENT
        self.sig.esign_provider = 'documenso'
        self.sig.external_id = 'envelope_demo_789'
        self.sig.save()

        response = self.client.post(
            reverse('contracts:documenso_esign_webhook_api'),
            data=json.dumps({
                'event': 'DOCUMENT_COMPLETED',
                'payload': {
                    'id': 'envelope_demo_789',
                    'externalId': f'clmone-{self.org.id}-{self.sig.id}',
                    'status': 'COMPLETED',
                    'completedAt': '2026-07-16T10:05:00Z',
                    'recipients': [{
                        'email': 'demi@example.com',
                        'readStatus': 'OPENED',
                        'signingStatus': 'SIGNED',
                    }],
                },
                'createdAt': '2026-07-16T10:05:01Z',
            }),
            content_type='application/json',
            HTTP_X_DOCUMENSO_SECRET='webhook-demo-secret',
        )
        self.assertEqual(response.status_code, 200)
        self.sig.refresh_from_db()
        self.assertEqual(self.sig.status, SignatureRequest.Status.SIGNED)
