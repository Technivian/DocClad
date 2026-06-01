"""Tests for enterprise admin console service and API."""
import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase


def _make_org(id=1, name='Acme', slug='acme'):
    org = MagicMock()
    org.pk = id
    org.name = name
    org.slug = slug
    return org


def _make_policy(mfa_required=False, require_approval_above_value=None,
                 data_transfer_review_required=True, retention_period_days=2555,
                 max_api_tokens_per_user=5, allow_public_sharing=False,
                 ai_features_enabled=True, updated_at=None):
    p = MagicMock()
    p.mfa_required = mfa_required
    p.require_approval_above_value = require_approval_above_value
    p.data_transfer_review_required = data_transfer_review_required
    p.retention_period_days = retention_period_days
    p.max_api_tokens_per_user = max_api_tokens_per_user
    p.allow_public_sharing = allow_public_sharing
    p.ai_features_enabled = ai_features_enabled
    p.updated_at = updated_at
    return p


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestAdminConsoleService(SimpleTestCase):

    @patch('contracts.services.admin_console.OrgPolicy')
    @patch('contracts.services.admin_console.OrganizationMembership')
    @patch('contracts.services.admin_console.OrganizationAPIToken')
    def test_get_settings_returns_org_info(self, MockToken, MockMembership, MockPolicy):
        org = _make_org()
        policy = _make_policy(updated_at=None)
        MockPolicy.objects.get_or_create.return_value = (policy, False)
        MockMembership.objects.filter.return_value.count.return_value = 5
        MockToken.objects.filter.return_value.count.return_value = 2
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        settings = svc.get_settings(org)
        self.assertEqual(settings.org_id, 1)
        self.assertEqual(settings.name, 'Acme')
        self.assertEqual(settings.member_count, 5)
        self.assertEqual(settings.token_count, 2)
        self.assertIn('mfa_required', settings.policy)

    @patch('contracts.services.admin_console.OrgPolicy')
    def test_update_policy_allowed_fields(self, MockPolicy):
        org = _make_org()
        policy = _make_policy()
        MockPolicy.objects.get_or_create.return_value = (policy, False)
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        user = MagicMock()
        result = svc.update_policy(org, user, mfa_required=True, retention_period_days=3650)
        self.assertTrue(policy.mfa_required)
        self.assertEqual(policy.retention_period_days, 3650)
        policy.save.assert_called_once()

    @patch('contracts.services.admin_console.OrgPolicy')
    def test_update_policy_ignores_unknown_fields(self, MockPolicy):
        org = _make_org()
        policy = _make_policy()
        MockPolicy.objects.get_or_create.return_value = (policy, False)
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        # 'injected_field' is not in allowed_fields, should be silently ignored
        svc.update_policy(org, MagicMock(), injected_field='evil')
        self.assertFalse(hasattr(policy, 'injected_field') and policy.injected_field == 'evil')

    @patch('contracts.services.admin_console.SalesforceOrganizationConnection')
    @patch('contracts.services.admin_console.WebhookEndpoint')
    @patch('contracts.services.admin_console.OrganizationMembership')
    def test_list_integrations_salesforce_enabled(self, MockMembership, MockWebhook, MockSF):
        org = _make_org()
        sf = MagicMock()
        sf.is_active = True
        sf.instance_url = 'https://acme.salesforce.com'
        MockSF.objects.filter.return_value.first.return_value = sf
        MockWebhook.objects.filter.return_value.count.return_value = 0
        MockMembership.objects.filter.return_value.exclude.return_value.count.return_value = 0
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        integrations = svc.list_integrations(org)
        sf_int = next(i for i in integrations if i.name == 'salesforce')
        self.assertTrue(sf_int.enabled)
        self.assertEqual(sf_int.details['instance_url'], 'https://acme.salesforce.com')

    @patch('contracts.services.admin_console.SalesforceOrganizationConnection')
    @patch('contracts.services.admin_console.WebhookEndpoint')
    @patch('contracts.services.admin_console.OrganizationMembership')
    def test_list_integrations_no_sf(self, MockMembership, MockWebhook, MockSF):
        org = _make_org()
        MockSF.objects.filter.return_value.first.return_value = None
        MockWebhook.objects.filter.return_value.count.return_value = 3
        MockMembership.objects.filter.return_value.exclude.return_value.count.return_value = 0
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        integrations = svc.list_integrations(org)
        sf_int = next(i for i in integrations if i.name == 'salesforce')
        webhook_int = next(i for i in integrations if i.name == 'webhooks')
        self.assertFalse(sf_int.enabled)
        self.assertTrue(webhook_int.enabled)
        self.assertEqual(webhook_int.details['endpoint_count'], 3)

    @patch('contracts.services.admin_console.AuditLog')
    @patch('contracts.services.admin_console.OrganizationMembership')
    def test_get_audit_summary(self, MockMembership, MockAudit):
        org = _make_org()
        MockMembership.objects.filter.return_value.values_list.return_value = [1, 2]
        log = MagicMock()
        log.pk = 1
        log.action = 'CREATE'
        log.user = MagicMock()
        log.user.username = 'alice'
        log.model_name = 'Contract'
        log.object_repr = 'NDA #1'
        log.timestamp = MagicMock()
        log.timestamp.isoformat.return_value = '2026-06-01T10:00:00+00:00'
        MockAudit.objects.filter.return_value.order_by.return_value.__getitem__ = lambda self, s: [log]
        MockAudit.objects.filter.return_value.order_by.return_value = [log]
        from contracts.services.admin_console import AdminConsoleService
        svc = AdminConsoleService()
        result = svc.get_audit_summary(org, limit=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['action'], 'CREATE')
        self.assertEqual(result[0]['actor'], 'alice')


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class TestAdminConsoleApi(SimpleTestCase):

    def _req(self, method='GET', body=None):
        req = MagicMock()
        req.method = method
        req.body = json.dumps(body).encode() if body else b''
        req.GET = {}
        req.user = MagicMock()
        req.user.is_authenticated = True
        return req

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_admin_console_service')
    def test_admin_settings_get(self, mock_svc_factory, mock_org):
        mock_org.return_value = _make_org()
        from contracts.services.admin_console import OrgSettings
        mock_svc = MagicMock()
        mock_svc.get_settings.return_value = OrgSettings(
            org_id=1, name='Acme', slug='acme', member_count=3, token_count=1,
            policy={'mfa_required': False, 'retention_period_days': 2555,
                    'require_approval_above_value': None, 'data_transfer_review_required': True,
                    'max_api_tokens_per_user': 5, 'allow_public_sharing': False,
                    'ai_features_enabled': True, 'updated_at': None},
        )
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import admin_settings_api
        resp = admin_settings_api(self._req(), )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['name'], 'Acme')
        self.assertIn('policy', data)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_admin_console_service')
    def test_admin_policy_patch(self, mock_svc_factory, mock_org):
        mock_org.return_value = _make_org()
        policy = _make_policy(mfa_required=True, updated_at=None)
        mock_svc = MagicMock()
        mock_svc.update_policy.return_value = policy
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import admin_policy_api
        resp = admin_policy_api(self._req(method='PATCH', body={'mfa_required': True}))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_admin_console_service')
    def test_admin_integrations_get(self, mock_svc_factory, mock_org):
        mock_org.return_value = _make_org()
        from contracts.services.admin_console import IntegrationStatus
        mock_svc = MagicMock()
        mock_svc.list_integrations.return_value = [
            IntegrationStatus(name='salesforce', enabled=True, details={'instance_url': 'https://x.sf.com'}),
            IntegrationStatus(name='webhooks', enabled=False, details={'endpoint_count': 0}),
        ]
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import admin_integrations_api
        resp = admin_integrations_api(self._req())
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['integrations']), 2)
        self.assertTrue(data['integrations'][0]['enabled'])

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_admin_console_service')
    def test_admin_audit_get(self, mock_svc_factory, mock_org):
        mock_org.return_value = _make_org()
        mock_svc = MagicMock()
        mock_svc.get_audit_summary.return_value = [
            {'id': 1, 'action': 'CREATE', 'actor': 'alice', 'model_name': 'Contract',
             'object_repr': 'NDA #1', 'timestamp': '2026-06-01T10:00:00+00:00'},
        ]
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import admin_audit_api
        resp = admin_audit_api(self._req())
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['logs']), 1)
        self.assertEqual(data['logs'][0]['actor'], 'alice')
