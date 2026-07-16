import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.forms import ContractForm
from contracts.models import AuditLog, Contract, Organization, OrganizationMembership
from contracts.views_domains.contract_helpers import build_contract_lifecycle_guidance


User = get_user_model()


class ContractLifecycleAuditTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner-user',
            email='owner@example.com',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Lifecycle Org', slug='lifecycle-org')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='Lifecycle Contract',
            contract_type=Contract.ContractType.MSA,
            content='Initial draft',
            status=Contract.Status.DRAFT,
            lifecycle_stage='DRAFTING',
            counterparty='Acme Corp',
            governing_law='State of Delaware',
            jurisdiction='New York',
            risk_level=Contract.RiskLevel.MEDIUM,
            created_by=self.owner,
        )

    def test_contract_form_rejects_lifecycle_stage_skip(self):
        form = ContractForm(
            instance=self.contract,
            data={
                'title': self.contract.title,
                'contract_type': self.contract.contract_type,
                'content': self.contract.content,
                'status': self.contract.status,
                'counterparty': self.contract.counterparty,
                'currency': self.contract.currency,
                'governing_law': self.contract.governing_law,
                'jurisdiction': self.contract.jurisdiction,
                'language': self.contract.language,
                'risk_level': self.contract.risk_level,
                'data_transfer_flag': self.contract.data_transfer_flag,
                'dpa_attached': self.contract.dpa_attached,
                'scc_attached': self.contract.scc_attached,
                'lifecycle_stage': 'SIGNATURE',
                'start_date': '',
                'end_date': '',
                'renewal_date': '',
                'auto_renew': '',
                'notice_period_days': '',
                'termination_notice_date': '',
                'client': '',
                'matter': '',
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('lifecycle_stage', form.errors)

    def test_contract_update_writes_detailed_lifecycle_audit_log(self):
        self.client.login(username='owner-user', password='testpass123')
        response = self.client.post(
            reverse('contracts:contract_update', kwargs={'pk': self.contract.id}),
            data={
                'title': self.contract.title,
                'contract_type': self.contract.contract_type,
                'content': self.contract.content,
                'status': Contract.Status.DRAFT,
                'counterparty': self.contract.counterparty,
                'value': '',
                'currency': self.contract.currency,
                'governing_law': self.contract.governing_law,
                'jurisdiction': self.contract.jurisdiction,
                'language': self.contract.language,
                'risk_level': self.contract.risk_level,
                'data_transfer_flag': '',
                'dpa_attached': '',
                'scc_attached': '',
                'lifecycle_stage': 'INTERNAL_REVIEW',
                'start_date': '',
                'end_date': '',
                'renewal_date': '',
                'auto_renew': '',
                'notice_period_days': '',
                'termination_notice_date': '',
                'client': '',
                'matter': '',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.lifecycle_stage, 'INTERNAL_REVIEW')

        audit_log = AuditLog.objects.filter(
            user=self.owner,
            action=AuditLog.Action.UPDATE,
            model_name='Contract',
            object_id=self.contract.id,
        ).latest('timestamp')
        self.assertEqual(audit_log.changes['event'], 'contract_lifecycle_stage_changed')
        self.assertEqual(audit_log.changes['changed_fields'], ['lifecycle_stage'])
        self.assertEqual(audit_log.changes['field_changes']['lifecycle_stage']['before'], 'DRAFTING')
        self.assertEqual(audit_log.changes['field_changes']['lifecycle_stage']['after'], 'INTERNAL_REVIEW')

    def test_contract_detail_exposes_lifecycle_guidance_for_renewal_window(self):
        self.contract.end_date = timezone.localdate() + timedelta(days=10)
        self.contract.renewal_date = timezone.localdate() + timedelta(days=10)
        self.contract.auto_renew = True
        self.contract.status = Contract.Status.ACTIVE
        self.contract.lifecycle_stage = 'EXECUTED'
        self.contract.save(update_fields=['end_date', 'renewal_date', 'auto_renew', 'status', 'lifecycle_stage', 'updated_at'])

        self.client.login(username='owner-user', password='testpass123')
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.id}))

        self.assertEqual(response.status_code, 200)
        guidance = response.context['lifecycle_guidance']
        self.assertEqual(guidance['state'], 'Renewal Due')
        self.assertEqual(guidance['next_stage'], 'RENEWAL')
        self.assertIn('Finalize renewal language', guidance['action'])
        self.assertIn('Auto-renew is enabled.', guidance['signals'])

    def test_build_contract_lifecycle_guidance_marks_archived_contracts_as_complete(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Archived Contract',
            contract_type=Contract.ContractType.MSA,
            content='Archived body',
            status=Contract.Status.ACTIVE,
            lifecycle_stage='ARCHIVED',
            counterparty='Acme Corp',
            governing_law='State of Delaware',
            jurisdiction='New York',
            risk_level=Contract.RiskLevel.LOW,
            created_by=self.owner,
        )

        guidance = build_contract_lifecycle_guidance(contract)

        self.assertEqual(guidance['state'], 'Archived')
        self.assertEqual(guidance['next_stage'], 'ARCHIVED')
        self.assertIn('No operational action required', guidance['action'])

    def test_run_contract_lifecycle_jobs_promotes_renewal_window_contracts(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Renewal Window Contract',
            contract_type=Contract.ContractType.MSA,
            content='Renewal body',
            status=Contract.Status.ACTIVE,
            lifecycle_stage='EXECUTED',
            counterparty='Acme Corp',
            governing_law='State of Delaware',
            jurisdiction='New York',
            risk_level=Contract.RiskLevel.LOW,
            end_date=timezone.localdate() + timedelta(days=10),
            renewal_date=timezone.localdate() + timedelta(days=10),
            auto_renew=True,
            created_by=self.owner,
        )

        out = StringIO()
        call_command('run_contract_lifecycle_jobs', organization_slug=self.organization.slug, stdout=out)
        payload = json.loads(out.getvalue())

        contract.refresh_from_db()
        self.assertEqual(contract.lifecycle_stage, 'RENEWAL')
        self.assertEqual(payload['contracts_promoted_to_renewal'], 1)
        self.assertEqual(payload['contracts_archived'], 0)
        self.assertEqual(
            AuditLog.objects.filter(model_name='Contract', object_id=contract.id).count(),
            1,
        )

    def test_run_contract_lifecycle_jobs_dry_run_does_not_mutate_contracts(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Dry Run Renewal Contract',
            contract_type=Contract.ContractType.MSA,
            content='Renewal body',
            status=Contract.Status.ACTIVE,
            lifecycle_stage='EXECUTED',
            counterparty='Acme Corp',
            governing_law='State of Delaware',
            jurisdiction='New York',
            risk_level=Contract.RiskLevel.LOW,
            end_date=timezone.localdate() + timedelta(days=10),
            renewal_date=timezone.localdate() + timedelta(days=10),
            auto_renew=True,
            created_by=self.owner,
        )

        out = StringIO()
        call_command('run_contract_lifecycle_jobs', organization_slug=self.organization.slug, dry_run=True, stdout=out)
        payload = json.loads(out.getvalue())

        contract.refresh_from_db()
        self.assertEqual(contract.lifecycle_stage, 'EXECUTED')
        self.assertEqual(payload['contracts_promoted_to_renewal'], 0)
        self.assertEqual(
            AuditLog.objects.filter(model_name='Contract', object_id=contract.id).count(),
            0,
        )
