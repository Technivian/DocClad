"""Phase 4D — invitation email resilience."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    AuditLog,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)

User = get_user_model()
PW = 'StrongPw!123'


def _org():
    return Organization.objects.create(name='Inv Org', slug='inv-org')


def _member(org, username, role):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


class InvitationDeliveryTests(TestCase):
    def setUp(self):
        self.org = _org()
        self.owner = _member(self.org, 'owner', OrganizationMembership.Role.OWNER)
        self.member = _member(self.org, 'member', OrganizationMembership.Role.MEMBER)
        self.client = Client()
        self.client.force_login(self.owner)

    def _invite(self, email='new@ex.com', role='MEMBER'):
        return self.client.post(reverse('contracts:organization_team'),
                                data={'email': email, 'role': role})

    def test_successful_invite_and_delivery(self):
        with patch('contracts.services.invitations.send_mail') as m:
            resp = self._invite()
        self.assertEqual(resp.status_code, 302)
        m.assert_called_once()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        self.assertEqual(inv.status, OrganizationInvitation.Status.PENDING)
        self.assertEqual(inv.delivery_status, OrganizationInvitation.DeliveryStatus.SENT)
        self.assertTrue(AuditLog.objects.filter(event_type='invite.delivery_succeeded').exists())

    def test_provider_failure_does_not_500_and_invitation_preserved(self):
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('smtp down')):
            resp = self._invite()
        self.assertEqual(resp.status_code, 302)  # not a 500
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        self.assertEqual(inv.status, OrganizationInvitation.Status.PENDING)  # still valid
        self.assertEqual(inv.delivery_status, OrganizationInvitation.DeliveryStatus.FAILED)
        self.assertEqual(inv.delivery_error, 'OSError')  # safe classification only
        self.assertTrue(AuditLog.objects.filter(event_type='invite.delivery_failed').exists())

    def test_failure_audit_has_no_secrets_or_token(self):
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('smtp secret 12345')):
            self._invite()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        row = AuditLog.objects.filter(event_type='invite.delivery_failed').first()
        blob = json.dumps(row.changes)
        self.assertNotIn('smtp secret 12345', blob)        # no raw exception message
        self.assertNotIn(str(inv.token), blob)             # no token

    def test_retry_after_failure_succeeds(self):
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('down')):
            self._invite()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        with patch('contracts.services.invitations.send_mail') as m:
            resp = self.client.post(reverse('contracts:retry_organization_invite', args=[inv.id]))
        self.assertEqual(resp.status_code, 302)
        m.assert_called_once()
        inv.refresh_from_db()
        self.assertEqual(inv.delivery_status, OrganizationInvitation.DeliveryStatus.SENT)

    def test_retry_keeps_same_token(self):
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('down')):
            self._invite()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        token_before = inv.token
        with patch('contracts.services.invitations.send_mail'):
            self.client.post(reverse('contracts:retry_organization_invite', args=[inv.id]))
        inv.refresh_from_db()
        self.assertEqual(inv.token, token_before)  # retry, not a new invitation

    def test_unauthorized_member_cannot_retry(self):
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('down')):
            self._invite()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')
        c = Client()
        c.force_login(self.member)
        resp = c.post(reverse('contracts:retry_organization_invite', args=[inv.id]))
        self.assertEqual(resp.status_code, 403)

    def test_cross_tenant_retry_blocked(self):
        other = Organization.objects.create(name='Other', slug='inv-other')
        other_owner = _member(other, 'other_owner', OrganizationMembership.Role.OWNER)
        with patch('contracts.services.invitations.send_mail', side_effect=OSError('down')):
            self._invite()
        inv = OrganizationInvitation.objects.get(email='new@ex.com')  # org A's invite
        c = Client()
        c.force_login(other_owner)
        resp = c.post(reverse('contracts:retry_organization_invite', args=[inv.id]))
        self.assertEqual(resp.status_code, 404)

    def test_duplicate_active_invitation_not_recreated(self):
        with patch('contracts.services.invitations.send_mail'):
            self._invite()
            self._invite()  # same email again
        self.assertEqual(
            OrganizationInvitation.objects.filter(email='new@ex.com', status='PENDING').count(), 1)
