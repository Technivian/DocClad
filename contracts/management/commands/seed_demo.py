"""Sub-block D3: curated, idempotent demo data for a 15-minute walkthrough.

Creates ONE fictional organization ("CLM One Demo Firm", slug clmone-demo)
with realistic, coherent data spanning the whole contract lifecycle: no real
personal data (fictional counterparties, .example email addresses per
RFC 2606), no QA debris, deterministic (fixed titles/usernames so automated
tests can rely on them), safe to rerun, and scoped so it never touches any
other organization's data.

Distinct from contracts/management/commands/seed_data.py (an older, simpler
dev-convenience seeder with hardcoded weak passwords 'admin123'/'password123'
— left as-is; not touched by this Sub-block D3 addition) and from
tests/*.py fixtures (created per-TestCase, torn down per-TestCase, never
persisted). This command's records live in a real (if local) database and
are meant to be looked at by a human running a demo.
"""
import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from config.db_safety import is_running_on_deployed_platform
from contracts.middleware import log_action
from contracts.models import (
    ApprovalRequest,
    AuditLog,
    ClauseTemplate,
    Contract,
    Counterparty,
    Deadline,
    Notification,
    Organization,
    OrganizationMembership,
    SignatureRequest,
    UserProfile,
)
from contracts.services.starter_content import ensure_org_starter_content

User = get_user_model()

DEMO_ORG_SLUG = 'clmone-demo'
DEMO_ORG_NAME = 'CLM One Demo Firm'
DEMO_EMAIL_DOMAIN = 'clmone-demo.example'  # RFC 2606 reserved TLD — never a real, deliverable address
# Local-only demo login; overridable via env var so it is never a hardcoded
# secret literal callers must trust. This organization only ever exists in a
# local/non-production database (see the production refusal check below).
DEMO_PASSWORD = os.environ.get('DEMO_SEED_PASSWORD', 'clmone-demo-2026!')

DEMO_USERS = [
    # (username, first, last, profile_role, org_role)
    ('demo_admin', 'Alex', 'Morgan', UserProfile.Role.ADMIN, OrganizationMembership.Role.OWNER),
    ('demo_partner', 'Jordan', 'Blake', UserProfile.Role.PARTNER, OrganizationMembership.Role.ADMIN),
    ('demo_associate', 'Casey', 'Reyes', UserProfile.Role.SENIOR_ASSOCIATE, OrganizationMembership.Role.MEMBER),
    ('demo_paralegal', 'Riley', 'Chen', UserProfile.Role.PARALEGAL, OrganizationMembership.Role.MEMBER),
]

DEMO_COUNTERPARTIES = [
    ('Northwind Logistics LLC', 'LLC', 'Delaware, USA'),
    ('Bluefin Analytics GmbH', 'CORPORATION', 'Germany'),
    ('Harborlight Media Partners', 'PARTNERSHIP', 'England & Wales'),
    ('Cedarview Facilities Ltd', 'CORPORATION', 'Ontario, Canada'),
    ('Solstice Cloud Systems Inc', 'CORPORATION', 'California, USA'),
]

# (title, contract_type, status, risk_level, days_from_today_start,
#  days_from_today_end, renewal_in_days_or_None, auto_renew, value, counterparty_idx)
DEMO_CONTRACTS = [
    ('Master Service Agreement — Northwind Logistics', 'MSA', 'ACTIVE', 'MEDIUM', -400, 330, 300, True, Decimal('185000'), 0),
    ('Mutual NDA — Bluefin Analytics', 'NDA', 'ACTIVE', 'LOW', -60, 305, None, False, None, 1),
    ('Statement of Work — Phase 2 Rollout', 'SOW', 'ACTIVE', 'MEDIUM', -30, 60, None, False, Decimal('72000'), 4),
    ('Vendor Agreement — Cedarview Facilities', 'VENDOR', 'ACTIVE', 'LOW', -200, 25, 20, True, Decimal('48000'), 3),
    ('License Agreement — Analytics Platform', 'LICENSE', 'ACTIVE', 'MEDIUM', -500, 15, 10, True, Decimal('96000'), 1),
    ('Partnership Agreement — Harborlight Media', 'PARTNERSHIP', 'ACTIVE', 'HIGH', -150, 215, None, False, Decimal('250000'), 2),
    ('Employment Agreement — VP Engineering', 'EMPLOYMENT', 'ACTIVE', 'LOW', -90, None, None, False, None, -1),
    ('Lease Agreement — Regional Office', 'LEASE', 'ACTIVE', 'MEDIUM', -700, 665, 635, True, Decimal('310000'), 3),
    ('Master Service Agreement — Solstice Cloud (renewing)', 'MSA', 'ACTIVE', 'MEDIUM', -350, 12, 5, True, Decimal('142000'), 4),
    ('NDA — Prospective Partner Discussions', 'NDA', 'IN_PROGRESS', 'LOW', None, None, None, False, None, 2),
    ('Statement of Work — Data Migration (draft)', 'SOW', 'IN_PROGRESS', 'MEDIUM', None, None, None, False, Decimal('54000'), 0),
    ('Settlement Agreement — Vendor Dispute', 'SETTLEMENT', 'IN_PROGRESS', 'HIGH', None, None, None, False, Decimal('18000'), 3),
    ('Vendor Agreement — Legacy Support (expired)', 'VENDOR', 'EXPIRED', 'LOW', -730, -30, None, False, Decimal('22000'), 1),
    ('MSA — Discontinued Supplier', 'MSA', 'TERMINATED', 'MEDIUM', -600, -100, None, False, Decimal('60000'), 2),
    ('SOW — Q1 Consulting Engagement (completed)', 'SOW', 'ACTIVE', 'LOW', -200, -30, None, False, Decimal('35000'), 4),
    ('Amendment — Northwind MSA Extension', 'AMENDMENT', 'IN_PROGRESS', 'MEDIUM', None, None, None, False, None, 0),
]

DEMO_CLAUSE_TEMPLATES = [
    ('Standard Mutual Confidentiality', 'Confidentiality', False,
     'Each party shall protect the other’s confidential information with the same degree of care it uses for its own confidential information, and in no event less than reasonable care.'),
    ('Data Processing Addendum Reference', 'Data Protection', True,
     'Where Processor processes Personal Data on behalf of Controller, the parties shall execute a Data Processing Addendum consistent with applicable data protection law.'),
    ('Limitation of Liability — Direct Damages Cap', 'Limitation of Liability', False,
     'Except for breaches of confidentiality or indemnification obligations, each party’s aggregate liability shall not exceed the fees paid in the twelve (12) months preceding the claim.'),
]


class Command(BaseCommand):
    help = 'Creates one curated, idempotent demo organization for a 15-minute walkthrough (Sub-block D3).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete and recreate this demo organization’s own records (never touches any other organization).',
        )

    def handle(self, *args, **options):
        if is_running_on_deployed_platform():
            raise CommandError(
                'seed_demo refuses to run on the deployed platform — this command creates '
                'fictional, non-production demo data and must only be used locally.'
            )

        org, created = Organization.objects.get_or_create(
            slug=DEMO_ORG_SLUG, defaults={'name': DEMO_ORG_NAME},
        )

        if not created and not options['reset']:
            self.stdout.write(self.style.WARNING(
                f'"{DEMO_ORG_NAME}" already exists (org id {org.id}). '
                'Re-run with --reset to delete and recreate its own records, or use it as-is.'
            ))
            return

        if not created and options['reset']:
            self._reset_org_records(org)

        users = self._create_users(org)
        ensure_org_starter_content(org)  # clause categories, retention policy, approval rule, base counterparties
        counterparties = self._create_counterparties(org)
        contracts = self._create_contracts(org, users, counterparties)
        self._create_clause_templates(org, users['demo_partner'])
        self._create_approvals(org, contracts, users)
        self._create_signature_activity(org, contracts, users)
        self._create_deadlines(org, contracts, users)
        self._create_notifications(users)
        self._write_audit_trail(org, contracts, users)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded "{DEMO_ORG_NAME}" (org id {org.id}): '
            f'{len(users)} users, {len(counterparties)} counterparties, {len(contracts)} contracts.'
        ))
        self.stdout.write(
            'Log in with any of: ' + ', '.join(u[0] for u in DEMO_USERS) +
            ' (password: value of DEMO_SEED_PASSWORD env var, or the command’s documented local-only default).'
        )

    # ---- teardown (scoped strictly to this one demo org) -------------------

    def _reset_org_records(self, org):
        """Deletes only this demo organization's own records — never touches
        any other organization, satisfying 'does not delete arbitrary
        existing data'.

        Deliberately does NOT touch AuditLog: it is an append-only,
        tamper-evident chain by design (contracts/models.py
        AuditLogQuerySet.delete() raises AuditWriteError) — a demo reset is
        itself a real event worth keeping a record of, not something that
        should (or even can) erase prior audit history.
        """
        Contract.objects.filter(organization=org).delete()
        Counterparty.objects.filter(organization=org).delete()
        ClauseTemplate.objects.filter(organization=org).delete()
        Notification.objects.filter(recipient__organization_memberships__organization=org).delete()
        OrganizationMembership.objects.filter(organization=org).delete()

    # ---- users ---------------------------------------------------------

    def _create_users(self, org):
        users = {}
        for username, first, last, profile_role, org_role in DEMO_USERS:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@{DEMO_EMAIL_DOMAIN}',
                    'first_name': first,
                    'last_name': last,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.email = f'{username}@{DEMO_EMAIL_DOMAIN}'
            user.first_name, user.last_name = first, last
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': profile_role})
            OrganizationMembership.objects.update_or_create(
                organization=org, user=user, defaults={'role': org_role, 'is_active': True},
            )
            users[username] = user
        return users

    # ---- counterparties --------------------------------------------------

    def _create_counterparties(self, org):
        counterparties = []
        for name, entity_type, jurisdiction in DEMO_COUNTERPARTIES:
            cp, _ = Counterparty.objects.get_or_create(
                organization=org, name=name,
                defaults={'entity_type': entity_type, 'jurisdiction': jurisdiction, 'is_active': True},
            )
            counterparties.append(cp)
        return counterparties

    # ---- contracts ---------------------------------------------------------

    def _create_contracts(self, org, users, counterparties):
        today = date.today()
        creator = users['demo_associate']
        contracts = []
        for (title, ctype, status, risk, start_offset, end_offset, renewal_offset,
             auto_renew, value, cp_idx) in DEMO_CONTRACTS:
            contract, _ = Contract.objects.update_or_create(
                organization=org, title=title,
                defaults={
                    'contract_type': ctype,
                    'status': status,
                    'risk_level': risk,
                    'counterparty': counterparties[cp_idx].name if cp_idx >= 0 else '',
                    'value': value,
                    'currency': 'USD',
                    'governing_law': 'State of Delaware',
                    'jurisdiction': 'Delaware',
                    'start_date': today + timedelta(days=start_offset) if start_offset is not None else None,
                    'end_date': today + timedelta(days=end_offset) if end_offset is not None else None,
                    'renewal_date': today + timedelta(days=renewal_offset) if renewal_offset is not None else None,
                    'auto_renew': auto_renew,
                    'notice_period_days': 30 if auto_renew else None,
                    'created_by': creator,
                    'lifecycle_stage': self._lifecycle_stage_for(title, status),
                    'origin_kind': Contract.OriginKind.SEED,
                    'origin_channel': 'seed_demo',
                    'origin_reason': 'Demo seed data',
                },
            )
            contracts.append(contract)
        return contracts

    @staticmethod
    def _lifecycle_stage_for(title, status):
        # Prefer title-driven stage for in-progress demos so the walkthrough
        # still shows drafting / approval / review variety under one record status.
        by_title = {
            'NDA — Prospective Partner Discussions': 'DRAFTING',
            'Statement of Work — Data Migration (draft)': 'DRAFTING',
            'Settlement Agreement — Vendor Dispute': 'APPROVAL',
            'Amendment — Northwind MSA Extension': 'INTERNAL_REVIEW',
            'SOW — Q1 Consulting Engagement (completed)': 'OBLIGATION_TRACKING',
        }
        if title in by_title:
            return by_title[title]
        return {
            'IN_PROGRESS': 'DRAFTING',
            'ACTIVE': 'OBLIGATION_TRACKING',
            'EXPIRED': 'RENEWAL',
            'TERMINATED': 'OBLIGATION_TRACKING',
            'CANCELLED': 'DRAFTING',
            'ARCHIVED': 'OBLIGATION_TRACKING',
        }.get(status, 'DRAFTING')

    # ---- clause library ------------------------------------------------

    def _create_clause_templates(self, org, author):
        from contracts.models import ClauseCategory

        for title, category_name, is_mandatory, content in DEMO_CLAUSE_TEMPLATES:
            category, _ = ClauseCategory.objects.get_or_create(organization=org, name=category_name)
            ClauseTemplate.objects.update_or_create(
                organization=org, title=title,
                defaults={
                    'category': category, 'content': content,
                    'is_mandatory': is_mandatory, 'is_approved': True,
                    'created_by': author,
                },
            )

    # ---- approvals — one of each valid state --------------------------------

    def _create_approvals(self, org, contracts, users):
        by_title = {c.title: c for c in contracts}
        specs = [
            ('Master Service Agreement — Northwind Logistics', 'LEGAL', ApprovalRequest.Status.PENDING, 'demo_partner', 3),
            ('NDA — Prospective Partner Discussions', 'LEGAL', ApprovalRequest.Status.APPROVED, 'demo_partner', -2),
            ('Settlement Agreement — Vendor Dispute', 'FINANCE', ApprovalRequest.Status.ESCALATED, 'demo_admin', -1),
            ('Statement of Work — Data Migration (draft)', 'LEGAL', ApprovalRequest.Status.REJECTED, 'demo_associate', -5),
        ]
        for title, step, status, assignee_username, due_offset in specs:
            contract = by_title[title]
            ApprovalRequest.objects.update_or_create(
                organization=org, contract=contract, approval_step=step,
                defaults={
                    'status': status,
                    'assigned_to': users[assignee_username],
                    'due_date': timezone.now() + timedelta(days=due_offset),
                    'comments': 'Seeded demo approval for walkthrough purposes.',
                },
            )

    # ---- signature activity ------------------------------------------------

    def _create_signature_activity(self, org, contracts, users):
        by_title = {c.title: c for c in contracts}
        specs = [
            ('Master Service Agreement — Northwind Logistics', 'Dana Whitfield', 'General Counsel', SignatureRequest.Status.SIGNED, -14),
            ('Vendor Agreement — Cedarview Facilities', 'Priya Nandakumar', 'VP Operations', SignatureRequest.Status.VIEWED, -2),
            ('Amendment — Northwind MSA Extension', 'Sam Okafor', 'Director', SignatureRequest.Status.SENT, -1),
        ]
        for title, signer_name, signer_role, status, sent_offset in specs:
            contract = by_title[title]
            sent_at = timezone.now() + timedelta(days=sent_offset)
            SignatureRequest.objects.update_or_create(
                organization=org, contract=contract, signer_email=f'{signer_name.split()[0].lower()}@{DEMO_EMAIL_DOMAIN}',
                defaults={
                    'signer_name': signer_name, 'signer_role': signer_role, 'status': status,
                    'sent_at': sent_at,
                    'signed_at': sent_at + timedelta(days=1) if status == SignatureRequest.Status.SIGNED else None,
                    'viewed_at': sent_at + timedelta(hours=6) if status in (SignatureRequest.Status.VIEWED, SignatureRequest.Status.SIGNED) else None,
                    'esign_provider': 'documenso',
                    'created_by': users['demo_associate'],
                },
            )

    # ---- deadlines / obligations --------------------------------------------

    def _create_deadlines(self, org, contracts, users):
        by_title = {c.title: c for c in contracts}
        today = date.today()
        specs = [
            ('Renewal decision — Solstice Cloud MSA', 'RENEWAL', 'HIGH', 5, 'Master Service Agreement — Solstice Cloud (renewing)', False),
            ('Notice deadline — Cedarview Facilities', 'RENEWAL', 'MEDIUM', 20, 'Vendor Agreement — Cedarview Facilities', False),
            ('Quarterly compliance review', 'REGULATORY', 'MEDIUM', 10, None, False),
            ('Overdue: settlement payment follow-up', 'PAYMENT', 'CRITICAL', -3, 'Settlement Agreement — Vendor Dispute', False),
            ('Completed: legacy vendor close-out', 'CONTRACT', 'LOW', -15, 'Vendor Agreement — Legacy Support (expired)', True),
        ]
        for title, dtype, priority, due_offset, contract_title, is_completed in specs:
            Deadline.objects.update_or_create(
                title=title,
                defaults={
                    'deadline_type': dtype,
                    'priority': priority,
                    'due_date': today + timedelta(days=due_offset),
                    'contract': by_title[contract_title] if contract_title else None,
                    'assigned_to': users['demo_paralegal'],
                    'is_completed': is_completed,
                    'completed_at': timezone.now() if is_completed else None,
                },
            )

    # ---- notifications -----------------------------------------------------

    def _create_notifications(self, users):
        admin = users['demo_admin']
        specs = [
            (Notification.NotificationType.APPROVAL, 'Approval needed', 'Master Service Agreement — Northwind Logistics is waiting for your review.'),
            (Notification.NotificationType.DEADLINE, 'Upcoming renewal', 'Solstice Cloud MSA renews in 5 days.'),
            (Notification.NotificationType.CONTRACT, 'Contract signed', 'Northwind Logistics MSA has been fully executed.'),
        ]
        for ntype, title, message in specs:
            Notification.objects.get_or_create(
                recipient=admin, notification_type=ntype, title=title,
                defaults={'message': message},
            )

    # ---- audit trail ---------------------------------------------------

    def _write_audit_trail(self, org, contracts, users):
        for contract in contracts[:5]:
            log_action(
                users['demo_associate'], AuditLog.Action.CREATE, 'Contract',
                object_id=contract.id, object_repr=contract.title,
                organization=org, changes={'event': 'demo_seed_contract_created'},
            )
        approved = ApprovalRequest.objects.filter(
            organization=org, status=ApprovalRequest.Status.APPROVED,
        ).select_related('contract').first()
        if approved:
            log_action(
                users['demo_partner'], AuditLog.Action.APPROVE, 'ApprovalRequest',
                object_id=approved.id, object_repr=f'{approved.contract.title} ({approved.approval_step})',
                organization=org, changes={'event': 'demo_seed_approval_approved'},
            )
