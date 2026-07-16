from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.middleware import log_action
from contracts.models import (
    AuditLog,
    ApprovalRule,
    CommandCenterRailItem,
    CommandCenterWorkItem,
    Contract,
    ContractTemplate,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
    UserProfile,
)
from contracts.services.msa_workflow import create_msa_workflow_instance


DEMO_PASSWORD = 'CLMOneMVP!2026'


class Command(BaseCommand):
    help = 'Create an idempotent, realistic workspace for the MVP acceptance journey.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove existing MVP workspace operational records before recreating the curated demo journey.',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        org, _ = Organization.objects.update_or_create(
            slug='clmone-mvp',
            defaults={
                'name': 'CLM One MVP Workspace',
                'workspace_mode': Organization.WorkspaceMode.IN_HOUSE_CLM,
                'is_active': True,
                'require_mfa': False,
            },
        )

        if options['reset']:
            self._reset_workspace(org)

        users = {}
        user_specs = (
            ('mvp_admin', 'Alex', 'Admin', 'mvp_admin@clmone.local', OrganizationMembership.Role.OWNER, UserProfile.Role.ADMIN),
            ('mvp_owner', 'Olivia', 'Owner', 'mvp_owner@clmone.local', OrganizationMembership.Role.MEMBER, UserProfile.Role.ASSOCIATE),
            ('mvp_reviewer', 'Ravi', 'Reviewer', 'mvp_reviewer@clmone.local', OrganizationMembership.Role.MEMBER, UserProfile.Role.SENIOR_ASSOCIATE),
        )
        for username, first_name, last_name, email, membership_role, profile_role in user_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'is_active': True,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
            OrganizationMembership.objects.update_or_create(
                organization=org,
                user=user,
                defaults={'role': membership_role, 'is_active': True},
            )
            UserProfile.objects.update_or_create(user=user, defaults={'role': profile_role})
            users[username] = user

        template, _ = ContractTemplate.objects.update_or_create(
            name='Approved Mutual NDA',
            contract_type=Contract.ContractType.NDA,
            defaults={
                'description': 'Approved two-way confidentiality starting point for the MVP journey.',
                'body': (
                    'MUTUAL NON-DISCLOSURE AGREEMENT\n\n'
                    'This agreement is between the parties identified in the contract record. '
                    'Each party will protect Confidential Information and use it only for the agreed purpose.'
                ),
                'is_active': True,
            },
        )

        sample, created = Contract.objects.get_or_create(
            organization=org,
            title='Northstar Vendor Agreement',
            defaults={
                'contract_type': Contract.ContractType.VENDOR,
                'counterparty': 'Northstar Systems B.V.',
                'owner': users['mvp_owner'],
                'created_by': users['mvp_owner'],
                'value': 48000,
                'currency': Contract.Currency.EUR,
                'governing_law': 'The Netherlands',
                'start_date': timezone.localdate(),
                'end_date': timezone.localdate() + timedelta(days=180),
                'status': Contract.Status.DRAFT,
                'dpa_attached': True,
                'content': 'Vendor services agreement with a data processing addendum.',
            },
        )
        if created:
            log_action(
                users['mvp_owner'], AuditLog.Action.CREATE, 'Contract', sample.pk, str(sample),
                organization=org,
                changes={'event': 'demo.contract_seeded', 'status': sample.status},
            )

        pack, pack_created = DPAReviewPack.objects.get_or_create(
            organization=org,
            contract=sample,
            defaults={
                'created_by': users['mvp_owner'],
                'reviewer': users['mvp_reviewer'],
                'approval_status': DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
                'role_qualification_notes': 'Confirm processor role and international transfer safeguards.',
            },
        )
        if pack_created:
            DPARiskItem.objects.create(
                review_pack=pack,
                category=DPARiskItem.Category.TRANSFER,
                title='Transfer mechanism requires confirmation',
                description='The DPA does not yet identify the transfer mechanism for non-EEA processing.',
                severity=DPARiskItem.Severity.HIGH,
                confidence=DPARiskItem.Confidence.NEEDS_HUMAN_CHECK,
                owners='LEGAL,DPO_SECURITY',
                status=DPARiskItem.Status.OPEN,
            )

        Deadline.objects.get_or_create(
            contract=sample,
            title='Confirm subprocessor schedule',
            defaults={
                'description': 'Obtain and review the current subprocessor schedule before approval.',
                'deadline_type': Deadline.DeadlineType.CONTRACT,
                'priority': Deadline.Priority.HIGH,
                'due_date': timezone.localdate() + timedelta(days=14),
                'assigned_to': users['mvp_reviewer'],
                'created_by': users['mvp_owner'],
            },
        )

        # The Command Center reads persisted work items first.  Seed the
        # Northstar privacy review explicitly so the walkthrough opens on its
        # intended priority matter instead of an empty-state hero.
        CommandCenterWorkItem.objects.update_or_create(
            organization=org,
            source_type=CommandCenterWorkItem.SourceType.CONTRACT,
            source_model='Contract',
            source_object_id=sample.pk,
            defaults={
                'title': sample.title,
                'subtitle': 'Confirm the international transfer safeguards before approval.',
                'item_type': 'Vendor agreement',
                'stage': 'Privacy review',
                'status': CommandCenterWorkItem.Status.OPEN,
                'risk_level': Contract.RiskLevel.HIGH,
                'priority': CommandCenterWorkItem.Priority.HIGH,
                'owner': users['mvp_reviewer'],
                'contract': sample,
                'dpa_review_pack': pack,
                'due_at': timezone.now() + timedelta(days=14),
                'action_label': 'Review transfer safeguards',
                'flags': {
                    'contract_type': Contract.ContractType.VENDOR,
                    'risk_personality': 'Privacy risk',
                    'highest_risk_signal': 'Transfer mechanism requires confirmation.',
                    'blocking_issue': 'Transfer mechanism requires confirmation for non-EEA processing.',
                    'next_action': 'Review the DPA transfer safeguards.',
                    'current_stage': 'Privacy review',
                },
            },
        )

        self._seed_payrollminds_msa_path(org, users)

        self.stdout.write(self.style.SUCCESS(
            f'MVP demo ready: workspace={org.slug}, template={template.name}, password={DEMO_PASSWORD}'
        ))
        for username in users:
            self.stdout.write(f'  {username} / {DEMO_PASSWORD}')

    @staticmethod
    def _reset_workspace(org):
        """Remove only disposable records owned by the local MVP workspace.

        The seed is intentionally narrow: its workspace is fictional and local,
        while user accounts and immutable audit history are retained.  Clearing
        operational records prevents browser/acceptance-test data from becoming
        the priority item in a customer walkthrough.
        """
        CommandCenterRailItem.objects.filter(organization=org).delete()
        CommandCenterWorkItem.objects.filter(organization=org).delete()
        Deadline.objects.filter(contract__organization=org).delete()
        DPAReviewPack.objects.filter(organization=org).delete()
        Contract.objects.filter(organization=org).delete()

    def _seed_payrollminds_msa_path(self, org, users):
        reviewer = users['mvp_reviewer']
        for step, name in (
            ('LEGAL', 'Payrollminds MSA Legal reviewer'),
            ('FINANCE', 'Payrollminds MSA Finance reviewer'),
        ):
            ApprovalRule.objects.update_or_create(
                organization=org,
                name=name,
                defaults={
                    'trigger_type': ApprovalRule.TriggerType.CONTRACT_TYPE,
                    'trigger_value': Contract.ContractType.MSA,
                    'approval_step': step,
                    'approver_role': UserProfile.Role.SENIOR_ASSOCIATE,
                    'specific_approver': reviewer,
                    'sla_hours': 24,
                    'escalation_after_hours': 48,
                    'is_active': True,
                    'order': 10 if step == 'LEGAL' else 20,
                },
            )

        standard_values = self._northstar_msa_values(payment_terms='Net 30')
        exception_values = self._northstar_msa_values(
            client='Northstar Consulting B.V. - Exception',
            payment_terms='Net 45',
            reference='MSA-PAYROLLMINDS-EXCEPTION',
            special_conditions='Client requested Net 45 payment terms; Finance approval is required.',
        )
        for values in (standard_values, exception_values):
            title = f"MSA — {values['counterparty']}"
            if Contract.objects.filter(organization=org, title=title).exists():
                continue
            create_msa_workflow_instance(
                organization=org,
                user=users['mvp_owner'],
                cleaned_values=values,
            )

        approved_contract, created = Contract.objects.get_or_create(
            organization=org,
            title='Northstar Consulting B.V. — Approved obligation demo',
            defaults={
                'contract_type': Contract.ContractType.MSA,
                'counterparty': 'Northstar Consulting B.V.',
                'owner': users['mvp_owner'],
                'created_by': users['mvp_owner'],
                'value': 120000,
                'currency': Contract.Currency.EUR,
                'governing_law': 'Netherlands',
                'start_date': timezone.localdate(),
                'end_date': timezone.localdate() + timedelta(days=365),
                'status': Contract.Status.APPROVED,
                'lifecycle_stage': 'OBLIGATION_TRACKING',
                'content': 'Approved Payrollminds MSA used for manual obligation tracking demo.',
            },
        )
        Deadline.objects.get_or_create(
            contract=approved_contract,
            title='Review payroll service report',
            defaults={
                'description': 'Confirm the monthly service report was received from Northstar Consulting B.V.',
                'deadline_type': Deadline.DeadlineType.SLA,
                'priority': Deadline.Priority.MEDIUM,
                'due_date': timezone.localdate() + timedelta(days=30),
                'assigned_to': users['mvp_owner'],
                'created_by': users['mvp_owner'],
            },
        )
        if created:
            log_action(
                users['mvp_owner'], AuditLog.Action.CREATE, 'Contract', approved_contract.pk, str(approved_contract),
                organization=org,
                changes={'event': 'demo.approved_obligation_contract_seeded', 'status': approved_contract.status},
            )

    @staticmethod
    def _northstar_msa_values(
        *,
        client='Northstar Consulting B.V.',
        payment_terms='Net 30',
        reference='MSA-PAYROLLMINDS-STANDARD',
        special_conditions='Standard Payrollminds service terms.',
    ):
        today = timezone.localdate()
        return {
            'payrollminds_contracting_entity': 'Payrollminds B.V.',
            'counterparty': client,
            'client_contact_name': 'Nina van Dijk',
            'client_contact_email': 'nina.vandijk@northstar.example',
            'start_date': today + timedelta(days=14),
            'end_date': today + timedelta(days=379),
            'contract_owner': 'Demo Legal User',
            'business_unit': 'Payroll Operations',
            'internal_reference': reference,
            'value': 120000,
            'currency': Contract.Currency.EUR,
            'payment_terms': payment_terms,
            'initial_term': '12 months',
            'renewal_type': 'Manual renewal',
            'termination_notice_period': 60,
            'consultant_service_type': 'Payroll implementation and advisory services',
            'rate': 125,
            'travel_km_rate': 0.23,
            'administrative_fee': 1500,
            'services_description': 'Payroll implementation support, advisory services, and monthly payroll operations assistance.',
            'sow_required': True,
            'deliverables_defined': True,
            'acceptance_criteria_required': True,
            'worker_classification': 'Independent contractor',
            'payrollminds_professional_involved': True,
            'governing_law': 'Netherlands',
            'jurisdiction': 'Amsterdam',
            'liability_cap': 'Fees paid in the preceding 12 months',
            'confidentiality_period': '5 years',
            'ip_ownership': 'Provider',
            'personal_data_involved': True,
            'value_above_threshold_confirmed': False,
            'liability_cap_nonstandard': False,
            'services_involve_personal_data': True,
            'auto_renewal_included': False,
            'ip_ownership_nonstandard': False,
            'governing_law_nonpreferred': False,
            'client_paper': False,
            'special_conditions': special_conditions,
        }
