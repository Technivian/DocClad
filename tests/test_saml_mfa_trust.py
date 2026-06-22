"""Phase 4G — explicit SAML MFA trust policy."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import AuditLog, Organization
from contracts.saml import saml_mfa_satisfied, set_saml_mfa_policy

User = get_user_model()

MFA_CONTEXT = 'urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract'
PWD_CONTEXT = 'urn:oasis:names:tc:SAML:2.0:ac:classes:Password'


class _FakeAuth:
    def __init__(self, contexts):
        self._contexts = contexts

    def get_last_authn_contexts(self):
        return self._contexts


def _org(**kw):
    return Organization.objects.create(name='S', slug='s-org', **kw)


class SamlAssuranceDecisionTests(TestCase):
    def test_accepted_context_satisfies(self):
        org = _org(require_mfa=True, saml_accepted_authn_contexts=MFA_CONTEXT)
        res = saml_mfa_satisfied(org, _FakeAuth([MFA_CONTEXT]))
        self.assertTrue(res['satisfied'])
        self.assertEqual(res['mode'], 'accepted_authn_context')

    def test_missing_context_fails_closed(self):
        org = _org(require_mfa=True, saml_accepted_authn_contexts=MFA_CONTEXT)
        res = saml_mfa_satisfied(org, _FakeAuth([PWD_CONTEXT]))
        self.assertFalse(res['satisfied'])

    def test_no_context_at_all_fails_closed(self):
        org = _org(require_mfa=True, saml_accepted_authn_contexts=MFA_CONTEXT)
        res = saml_mfa_satisfied(org, _FakeAuth([]))
        self.assertFalse(res['satisfied'])

    def test_explicit_trusted_idp_compatibility_mode(self):
        org = _org(require_mfa=True, saml_mfa_trusted=True)
        res = saml_mfa_satisfied(org, _FakeAuth([]))
        self.assertTrue(res['satisfied'])
        self.assertEqual(res['mode'], 'org_trusted_idp')

    def test_untrusted_default_fails_closed(self):
        org = _org(require_mfa=True)  # no trust, no accepted contexts
        res = saml_mfa_satisfied(org, _FakeAuth([PWD_CONTEXT]))
        self.assertFalse(res['satisfied'])

    def test_multiple_accepted_contexts_parsed(self):
        org = _org(require_mfa=True,
                   saml_accepted_authn_contexts=f'{MFA_CONTEXT}\n{PWD_CONTEXT}')
        self.assertTrue(saml_mfa_satisfied(org, _FakeAuth([PWD_CONTEXT]))['satisfied'])


class SamlPolicyAuditTests(TestCase):
    def test_policy_change_is_audited(self):
        org = _org()
        user = User.objects.create_user(username='admin', password='x')
        set_saml_mfa_policy(org, trusted=True, user=user)
        org.refresh_from_db()
        self.assertTrue(org.saml_mfa_trusted)
        audit = AuditLog.objects.filter(event_type='saml.mfa_policy_changed', object_id=org.id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.organization_id, org.id)
        self.assertIn('saml_mfa_trusted', audit.changes['changed_fields'])

    def test_no_change_no_audit(self):
        org = _org(saml_mfa_trusted=False)
        before = AuditLog.objects.filter(event_type='saml.mfa_policy_changed').count()
        set_saml_mfa_policy(org, trusted=False)
        after = AuditLog.objects.filter(event_type='saml.mfa_policy_changed').count()
        self.assertEqual(before, after)
