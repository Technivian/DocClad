"""Tests for the Risk Register + Audit Trail layout adoption block.

Covers: shared shell/header convergence, compact KPI strips backed by real
data only, English status labels overriding RiskLog's Dutch-labeled
TextChoices, AssigneeChip reuse for risk ownership, preserved filters/
pagination/chain-verification behaviour, cross-tenant isolation, and copy
free of raw enums/ISO timestamps/model names/Dutch chrome.
"""
import re

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
    RiskLog,
)

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
DUTCH_RISK_WORDS = (
    'Veiligheid', 'Escalatie', 'Geen match', 'Wachttijd overschreden',
    'Capaciteit probleem', 'Intake incompleet', 'Uitval risico',
    'In opvolging', 'Afgerond', 'Omschrijving', 'Urgentie', 'Verantwoordelijke',
)


def page_body(html, root_id):
    """Slice out Django Debug Toolbar's panel — DEBUG=True dumps the full
    template context, so raw values can appear there even when the real
    page body never renders them."""
    start = html.find(f'id="{root_id}"')
    end = html.find('id="djDebug"')
    if start == -1:
        return html
    return html[start:end] if end != -1 else html[start:]


class RiskRegisterShellConvergenceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Shell Firm', slug='risk-shell-firm', workspace_mode='law_firm_ops')
        self.user = User.objects.create_user(username='risk_shell_user', password='testpass123', email='shell@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='risk_shell_user', password='testpass123')

    def test_renders_for_member(self):
        response = self.client.get(reverse('contracts:risk_log_list'))
        self.assertEqual(response.status_code, 200)

    def test_uses_shared_page_wrap_shell(self):
        response = self.client.get(reverse('contracts:risk_log_list'))
        html = response.content.decode()
        self.assertIn('page-wrap page-wrap-fluid', html)

    def test_uses_shared_page_header_pattern(self):
        response = self.client.get(reverse('contracts:risk_log_list'))
        html = response.content.decode()
        self.assertIn('arch-header', html)
        self.assertIn('arch-title', html)

    def test_kpi_strip_renders_with_real_counts(self):
        Contract.objects.create(organization=self.organization, title='KPI Contract', content='Seed', status='ACTIVE', created_by=self.user)
        contract = Contract.objects.get(title='KPI Contract')
        RiskLog.objects.create(title='Open Risk', description='d', contract=contract, status=RiskLog.Status.OPEN, risk_level=RiskLog.RiskLevel.HIGH, created_by=self.user)
        RiskLog.objects.create(title='Resolved Risk', description='d', contract=contract, status=RiskLog.Status.RESOLVED, risk_level=RiskLog.RiskLevel.LOW, created_by=self.user)

        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        self.assertIn('kpi-strip', body)
        self.assertEqual(response.context['open_risk_count'], 1)
        self.assertEqual(response.context['resolved_risk_count'], 1)
        self.assertEqual(response.context['high_severity_count'], 1)


class RiskRegisterRowContentTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Row Firm', slug='risk-row-firm', workspace_mode='law_firm_ops')
        self.owner = User.objects.create_user(username='risk_owner', password='testpass123', email='owner@example.com', first_name='Rowan')
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='risk_owner', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Row Risk Contract', content='Seed', status='ACTIVE', created_by=self.owner,
        )

    def test_row_shows_owner_via_assignee_chip_and_english_status(self):
        RiskLog.objects.create(
            title='Row Risk', description='A risk needing follow-up', contract=self.contract,
            assigned_to=self.owner, status=RiskLog.Status.IN_PROGRESS, risk_level=RiskLog.RiskLevel.MEDIUM,
            created_by=self.owner,
        )
        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        self.assertIn('Rowan', body)
        self.assertIn('In Progress', body)
        self.assertNotIn('In opvolging', body)

    def test_related_contract_link_present(self):
        risk = RiskLog.objects.create(
            title='Linked Risk', description='d', contract=self.contract, created_by=self.owner,
        )
        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        self.assertIn(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}), body)

    def test_no_dutch_words_leak_for_any_status_or_signal_type(self):
        for status in (RiskLog.Status.OPEN, RiskLog.Status.IN_PROGRESS, RiskLog.Status.RESOLVED):
            RiskLog.objects.create(
                title=f'Risk {status}', description='d', contract=self.contract,
                status=status, signal_type=RiskLog.SignalType.DROPOUT_RISK, created_by=self.owner,
            )
        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        for word in DUTCH_RISK_WORDS:
            self.assertNotIn(word, body, f'Found Dutch chrome "{word}" in Risk Register body')

    def test_no_raw_iso_timestamps(self):
        RiskLog.objects.create(title='Ts Risk', description='d', contract=self.contract, created_by=self.owner)
        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Risk Register response')

    def test_empty_state_renders(self):
        response = self.client.get(reverse('contracts:risk_log_list'))
        body = page_body(response.content.decode(), 'risk-register-root')
        self.assertIn('No risks logged yet', body)
        self.assertIn('Risks appear here after a user records a finding', body)
        self.assertIn('Log first risk', body)

    def test_search_and_risk_level_filter_still_work(self):
        RiskLog.objects.create(title='Findable Risk', description='unique-marker-xyz', contract=self.contract, risk_level=RiskLog.RiskLevel.CRITICAL, created_by=self.owner)
        RiskLog.objects.create(title='Other Risk', description='d', contract=self.contract, risk_level=RiskLog.RiskLevel.LOW, created_by=self.owner)

        response = self.client.get(reverse('contracts:risk_log_list'), {'q': 'unique-marker-xyz'})
        titles = [r.title for r in response.context['risk_logs']]
        self.assertEqual(titles, ['Findable Risk'])

        response = self.client.get(reverse('contracts:risk_log_list'), {'risk_level': 'CRITICAL'})
        titles = [r.title for r in response.context['risk_logs']]
        self.assertEqual(titles, ['Findable Risk'])


class RiskRegisterCrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Risk Org A', slug='risk-layout-org-a', workspace_mode='law_firm_ops')
        self.org_b = Organization.objects.create(name='Risk Org B', slug='risk-layout-org-b', workspace_mode='law_firm_ops')
        self.user_a = User.objects.create_user(username='risk_layout_a', password='testpass123', email='a@example.com')
        self.user_b = User.objects.create_user(username='risk_layout_b', password='testpass123', email='b@example.com')
        OrganizationMembership.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.MEMBER, is_active=True)
        contract_a = Contract.objects.create(organization=self.org_a, title='Org A Contract', content='Seed', status='ACTIVE', created_by=self.user_a)
        self.risk_a = RiskLog.objects.create(title='Org A Risk', description='d', contract=contract_a, created_by=self.user_a)

    def test_other_org_member_does_not_see_risk_or_its_kpi_counted(self):
        client = TestClient()
        client.login(username='risk_layout_b', password='testpass123')
        response = client.get(reverse('contracts:risk_log_list'))
        ids = [r.id for r in response.context['risk_logs']]
        self.assertNotIn(self.risk_a.id, ids)
        self.assertEqual(response.context['open_risk_count'], 0)


class AuditTrailShellConvergenceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Audit Shell Firm', slug='audit-shell-firm')
        self.user = User.objects.create_user(username='audit_shell_user', password='testpass123', email='audit@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='audit_shell_user', password='testpass123')

    def test_renders_for_member(self):
        response = self.client.get(reverse('contracts:audit_log_list'))
        self.assertEqual(response.status_code, 200)

    def test_uses_shared_page_wrap_shell(self):
        response = self.client.get(reverse('contracts:audit_log_list'))
        html = response.content.decode()
        self.assertIn('page-wrap page-wrap-fluid', html)

    def test_uses_shared_page_header_pattern(self):
        response = self.client.get(reverse('contracts:audit_log_list'))
        html = response.content.decode()
        self.assertIn('arch-header', html)
        self.assertIn('arch-title', html)

    def test_kpi_strip_renders_with_real_counts(self):
        from contracts.middleware import log_action
        log_action(self.user, AuditLog.Action.CREATE, 'Contract', object_id=1, object_repr='x', organization=self.organization, changes={'event': 'x'})
        response = self.client.get(reverse('contracts:audit_log_list'))
        body = page_body(response.content.decode(), 'audit-trail-root')
        self.assertIn('kpi-strip', body)
        self.assertGreaterEqual(response.context['event_count'], 1)

    def test_chain_status_context_still_present(self):
        response = self.client.get(reverse('contracts:audit_log_list'))
        self.assertIn('chain_status', response.context)
        self.assertIn(response.context['chain_status']['status'], ('valid', 'empty'))

    def test_filters_still_render_with_autosubmit(self):
        response = self.client.get(reverse('contracts:audit_log_list'))
        html = response.content.decode()
        self.assertIn('name="action"', html)
        self.assertIn('name="model"', html)
        self.assertIn('data-autosubmit', html)

    def test_empty_state_renders(self):
        # Logging in already writes a LOGIN audit event, so the table is never
        # truly empty in practice — filter to an action with no real matches
        # to exercise the {% empty %} branch instead.
        response = self.client.get(reverse('contracts:audit_log_list'), {'action': 'DELETE'})
        body = page_body(response.content.decode(), 'audit-trail-root')
        self.assertIn('No audit log entries.', body)

    def test_no_raw_internals_in_body(self):
        from contracts.middleware import log_action
        log_action(self.user, AuditLog.Action.CREATE, 'Contract', object_id=1, object_repr='x', organization=self.organization, changes={'event': 'x'})
        response = self.client.get(reverse('contracts:audit_log_list'))
        body = page_body(response.content.decode(), 'audit-trail-root')
        self.assertNotIn('AuditLog', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Audit Trail response')


class AuditTrailCrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Audit Org A', slug='audit-layout-org-a')
        self.org_b = Organization.objects.create(name='Audit Org B', slug='audit-layout-org-b')
        self.user_a = User.objects.create_user(username='audit_layout_a', password='testpass123', email='a@example.com')
        self.user_b = User.objects.create_user(username='audit_layout_b', password='testpass123', email='b@example.com')
        OrganizationMembership.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.MEMBER, is_active=True)
        from contracts.middleware import log_action
        log_action(self.user_a, AuditLog.Action.CREATE, 'Contract', object_id=1, object_repr='Org A Contract', organization=self.org_a, changes={'event': 'x'})

    def test_other_org_member_does_not_see_event_or_count_it(self):
        client = TestClient()
        client.login(username='audit_layout_b', password='testpass123')
        response = client.get(reverse('contracts:audit_log_list'))
        reprs = [log.object_repr for log in response.context['logs']]
        self.assertNotIn('Org A Contract', reprs)
        # event_count must reflect only org B's own activity (its own LOGIN
        # event from the call above), never org A's — not a literal zero,
        # since logging in itself writes a real audit event.
        self.assertEqual(response.context['event_count'], AuditLog.objects.filter(organization=self.org_b).count())
