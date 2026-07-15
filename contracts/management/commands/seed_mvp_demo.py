from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.middleware import log_action
from contracts.models import (
    AuditLog,
    Contract,
    ContractTemplate,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
    UserProfile,
)


DEMO_PASSWORD = 'CLMOneMVP!2026'


class Command(BaseCommand):
    help = 'Create an idempotent, realistic workspace for the MVP acceptance journey.'

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

        self.stdout.write(self.style.SUCCESS(
            f'MVP demo ready: workspace={org.slug}, template={template.name}, password={DEMO_PASSWORD}'
        ))
        for username in users:
            self.stdout.write(f'  {username} / {DEMO_PASSWORD}')
