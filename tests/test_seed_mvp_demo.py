"""Regression coverage for the curated local MVP walkthrough seed."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contracts.models import (
    ApprovalRule,
    CommandCenterWorkItem,
    Contract,
    Organization,
    OrganizationMembership,
    RiskSignal,
)


class SeedMvpDemoCommandTests(TestCase):
    def test_creates_the_deployment_demo_admin_with_the_published_credentials(self):
        call_command('seed_mvp_demo')

        admin = get_user_model().objects.get(username='mvp_admin')

        self.assertEqual(admin.email, 'mvp_admin@clmone.local')
        self.assertEqual(admin.get_full_name(), 'Alex Admin')
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.check_password('CLMOneMVP!2026'))
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization__slug='clmone-mvp',
                user=admin,
                role=OrganizationMembership.Role.OWNER,
                is_active=True,
            ).exists()
        )

    def test_single_user_mode_keeps_all_walkthrough_work_assigned_to_mvp_admin(self):
        call_command('seed_mvp_demo', '--single-user')

        users = get_user_model().objects.order_by('username')
        self.assertEqual(list(users.values_list('username', flat=True)), ['mvp_admin'])
        admin = users.get()
        self.assertTrue(Contract.objects.filter(organization__slug='clmone-mvp', owner=admin).exists())
        self.assertTrue(CommandCenterWorkItem.objects.filter(organization__slug='clmone-mvp', owner=admin).exists())

    def test_reset_removes_stale_demo_work_and_restores_northstar_priority(self):
        output = StringIO()
        call_command('seed_mvp_demo', stdout=output)
        org = Organization.objects.get(slug='clmone-mvp')
        admin = get_user_model().objects.get(username='mvp_admin')
        stale_contract = Contract.objects.create(
            organization=org,
            title='Stale browser acceptance contract',
            created_by=admin,
        )
        CommandCenterWorkItem.objects.create(
            organization=org,
            source_type=CommandCenterWorkItem.SourceType.CONTRACT,
            source_model='Contract',
            source_object_id=stale_contract.pk,
            title=stale_contract.title,
            contract=stale_contract,
            owner=admin,
        )

        call_command('seed_mvp_demo', '--reset', stdout=output)

        titles = set(Contract.objects.filter(organization=org).values_list('title', flat=True))
        self.assertEqual(titles, {
            'Northstar Vendor Agreement',
            'MSA — Northstar Consulting B.V.',
            'MSA — Northstar Consulting B.V. - Exception',
            'Northstar Consulting B.V. — Approved obligation demo',
        })
        self.assertTrue(CommandCenterWorkItem.objects.filter(organization=org, title='Northstar Vendor Agreement').exists())
        self.assertTrue(CommandCenterWorkItem.objects.filter(organization=org, title='MSA Commercial Review Workflow').exists())
        self.assertTrue(ApprovalRule.objects.filter(organization=org, approval_step='LEGAL', trigger_value='MSA').exists())
        self.assertTrue(ApprovalRule.objects.filter(organization=org, approval_step='FINANCE', trigger_value='MSA').exists())
        exception_contract = Contract.objects.get(organization=org, title='MSA — Northstar Consulting B.V. - Exception')
        self.assertTrue(RiskSignal.objects.filter(workflow__contract=exception_contract, code='nonstandard_payment_terms').exists())
