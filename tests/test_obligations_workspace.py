"""Phase 4 of the Product Coherence Redesign: the dedicated Obligations
workspace (contracts:obligations_workspace), replacing the deadline_list
stopgap the in_house_clm nav used to point at.

Covers: derived compliance status (Met/Overdue/Breach Risk/Pending Action),
polymorphic contract/matter source resolution, tenant scoping, and that the
nav taxonomy now points Obligations at the real view.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    Client as ClientModel,
    Contract,
    Deadline,
    Matter,
    Organization,
    OrganizationMembership,
)
from contracts.nav_config import get_nav_for
from contracts.templatetags.clmone_format import (
    obligation_compliance_badge_class,
    obligation_compliance_label,
    obligation_compliance_status,
)

User = get_user_model()


def _today():
    return timezone.now().date()


class ObligationComplianceStatusTests(TestCase):
    """The derived-status filter itself, no DB/HTTP involved."""

    def _deadline(self, **overrides):
        defaults = dict(
            title='Test Obligation',
            due_date=_today() + timedelta(days=30),
            reminder_days=7,
            is_completed=False,
        )
        defaults.update(overrides)
        return Deadline(**defaults)

    def test_completed_is_met(self):
        d = self._deadline(is_completed=True, due_date=_today() - timedelta(days=5))
        self.assertEqual(obligation_compliance_status(d), 'MET')

    def test_past_due_incomplete_is_overdue(self):
        d = self._deadline(due_date=_today() - timedelta(days=1))
        self.assertEqual(obligation_compliance_status(d), 'OVERDUE')

    def test_inside_reminder_window_is_breach_risk(self):
        d = self._deadline(due_date=_today() + timedelta(days=3), reminder_days=7)
        self.assertEqual(obligation_compliance_status(d), 'BREACH_RISK')

    def test_outside_reminder_window_is_pending(self):
        d = self._deadline(due_date=_today() + timedelta(days=30), reminder_days=7)
        self.assertEqual(obligation_compliance_status(d), 'PENDING')

    def test_labels_and_badge_classes_cover_every_status(self):
        cases = {
            'MET': (self._deadline(is_completed=True), 'Met', 'badge-green'),
            'OVERDUE': (self._deadline(due_date=_today() - timedelta(days=1)), 'Overdue', 'badge-red'),
            'BREACH_RISK': (self._deadline(due_date=_today() + timedelta(days=1), reminder_days=7), 'Breach Risk', 'badge-red'),
            'PENDING': (self._deadline(due_date=_today() + timedelta(days=90), reminder_days=7), 'Pending Action', 'badge-blue'),
        }
        for status, (deadline, label, badge_class) in cases.items():
            self.assertEqual(obligation_compliance_label(deadline), label)
            self.assertEqual(obligation_compliance_badge_class(deadline), badge_class)


class ObligationsWorkspaceViewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Obligations Test Org', slug='obligations-test-org', workspace_mode='in_house_clm',
        )
        self.other_org = Organization.objects.create(name='Other Org', slug='obligations-other-org')
        self.user = User.objects.create_user(username='obligations_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='obligations_user', password='testpass123!')

        self.client_model = ClientModel.objects.create(organization=self.org, name='Acme Co')
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-1', title='Acme Matter', client=self.client_model,
        )
        self.contract = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='x', status='ACTIVE', created_by=self.user,
        )

        self.overdue = Deadline.objects.create(
            title='Overdue Filing', contract=self.contract, due_date=_today() - timedelta(days=2),
            reminder_days=7, assigned_to=self.user,
        )
        self.breach_risk = Deadline.objects.create(
            title='Upcoming Renewal Notice', matter=self.matter, due_date=_today() + timedelta(days=2),
            reminder_days=7,
        )
        self.pending = Deadline.objects.create(
            title='Distant Review', contract=self.contract, due_date=_today() + timedelta(days=90),
            reminder_days=7,
        )
        self.met = Deadline.objects.create(
            title='Filed Already', contract=self.contract, due_date=_today() - timedelta(days=10),
            reminder_days=7, is_completed=True, completed_at=timezone.now(),
        )

        # A deadline belonging to a different organization must never appear.
        other_contract = Contract.objects.create(
            organization=self.other_org, title='Other Org Contract', content='x',
            status='ACTIVE', created_by=self.user,
        )
        Deadline.objects.create(title='Not My Org', contract=other_contract, due_date=_today(), reminder_days=7)

    def test_renders_and_lists_all_org_obligations(self):
        response = self.client_.get(reverse('contracts:obligations_workspace'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Overdue Filing', content)
        self.assertIn('Upcoming Renewal Notice', content)
        self.assertIn('Distant Review', content)
        self.assertIn('Filed Already', content)
        self.assertNotIn('Not My Org', content)

    def test_status_counts(self):
        response = self.client_.get(reverse('contracts:obligations_workspace'))
        self.assertEqual(response.context['obligations_overdue_count'], 1)
        self.assertEqual(response.context['obligations_breach_risk_count'], 1)
        self.assertEqual(response.context['obligations_pending_count'], 1)
        self.assertEqual(response.context['obligations_met_count'], 1)

    def test_contract_source_takes_priority_and_links(self):
        response = self.client_.get(reverse('contracts:obligations_workspace'))
        content = response.content.decode()
        self.assertIn(reverse('contracts:contract_detail', args=[self.contract.pk]), content)

    def test_matter_only_source_links_to_matter(self):
        response = self.client_.get(reverse('contracts:obligations_workspace'))
        content = response.content.decode()
        self.assertIn(reverse('contracts:matter_detail', args=[self.matter.pk]), content)

    def test_unauthenticated_redirects_to_login(self):
        anon = TestClient()
        response = anon.get(reverse('contracts:obligations_workspace'))
        self.assertEqual(response.status_code, 302)

    def test_new_obligation_cta_present(self):
        response = self.client_.get(reverse('contracts:obligations_workspace'))
        self.assertContains(response, 'New Obligation')
        self.assertContains(response, reverse('contracts:deadline_create'))


class ObligationsNavTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Obligations Nav Org', slug='obligations-nav-org', workspace_mode='in_house_clm',
        )
        self.user = User.objects.create_user(username='obligations_nav_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )

    def test_obligations_nav_item_points_at_dedicated_view(self):
        entries = get_nav_for(self.org, self.user)
        obligations_entry = next(e for e in entries if e.get('label') == 'Obligations')
        self.assertEqual(obligations_entry['url_name'], 'contracts:obligations_workspace')

    def test_law_firm_ops_uses_the_same_standard_nav(self):
        law_firm_org = Organization.objects.create(
            name='Law Firm Org', slug='obligations-law-firm-org', workspace_mode='law_firm_ops',
        )
        entries = get_nav_for(law_firm_org, self.user)
        labels = [e.get('label') for e in entries if e['kind'] == 'item']
        self.assertIn('Obligations', labels)
