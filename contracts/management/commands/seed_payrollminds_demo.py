"""Seed a coherent Payrollminds buyer demo without touching other workspaces."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.middleware import log_action
from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    ContractVersion,
    Deadline,
    Document,
    DPAApprovalHistoryEntry,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
    SignatureRequest,
    UserProfile,
)


DEMO_PASSWORD = 'CLMOneMVP!2026'


def _pdf_bytes(title, lines):
    """Return a small valid PDF built with the standard library only."""
    def escape(value):
        return str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    content_lines = [
        'BT',
        '/F1 16 Tf',
        '72 760 Td',
        f'({escape(title)}) Tj',
        '/F1 10 Tf',
        '0 -28 Td',
    ]
    for line in lines:
        content_lines.extend((f'({escape(line)}) Tj', '0 -16 Td'))
    content_lines.append('ET')
    stream = '\n'.join(content_lines).encode('latin-1', errors='replace')

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream),
    ]

    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f'{index} 0 obj\n'.encode())
        output.extend(body)
        output.extend(b'\nendobj\n')

    xref_offset = len(output)
    output.extend(f'xref\n0 {len(objects) + 1}\n'.encode())
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_offset}\n%%EOF\n'.encode()
    )
    return bytes(output)


class Command(BaseCommand):
    help = 'Create or update the complete Payrollminds demo workspace.'

    def handle(self, *args, **options):
        User = get_user_model()
        now = timezone.now()
        today = timezone.localdate()
        organization, _ = Organization.objects.update_or_create(
            slug='payrollminds-demo',
            defaults={
                'name': 'Payrollminds Demo Workspace',
                'workspace_mode': Organization.WorkspaceMode.IN_HOUSE_CLM,
                'is_active': True,
                'require_mfa': False,
            },
        )
        users = {}
        for username, first_name, last_name, department, membership_role, profile_role in (
            (
                'payrollminds_admin', 'Alex', 'de Vries', 'Legal Operations',
                OrganizationMembership.Role.OWNER, UserProfile.Role.ADMIN,
            ),
            (
                'payrollminds_legal', 'Maya', 'Jansen', 'Legal',
                OrganizationMembership.Role.MEMBER, UserProfile.Role.SENIOR_ASSOCIATE,
            ),
            (
                'payrollminds_procurement', 'Noah', 'Smit', 'Procurement',
                OrganizationMembership.Role.MEMBER, UserProfile.Role.ASSOCIATE,
            ),
            (
                'payrollminds_finance', 'Sophie', 'Bakker', 'Finance',
                OrganizationMembership.Role.MEMBER, UserProfile.Role.ADMIN,
            ),
        ):
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@demo.clmone.local',
                    'is_active': True,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
            OrganizationMembership.objects.update_or_create(
                organization=organization,
                user=user,
                defaults={'role': membership_role, 'is_active': True},
            )
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'role': profile_role,
                    'department': department,
                    'is_active': True,
                },
            )
            users[username] = user

        records = (
            {
                'title': 'Payrollminds Master Services Agreement',
                'contract_type': Contract.ContractType.MSA,
                'counterparty': 'Atlas Workforce B.V.',
                'status': Contract.Status.ACTIVE,
                'stage': 'EXECUTED',
                'owner': 'payrollminds_legal',
                'value': 180000,
                'start': today - timedelta(days=120),
                'end': today + timedelta(days=18),
                'risk': Contract.RiskLevel.LOW,
                'content': (
                    'Executed enterprise payroll services agreement. Annual fees are EUR 180,000. '
                    'Renewal requires a decision 60 days before term end. Liability is capped at '
                    'twelve months of fees, subject to agreed data-protection carve-outs.'
                ),
                'extra': {
                    'governing_law': 'Netherlands',
                    'jurisdiction': 'Amsterdam',
                    'auto_renew': True,
                    'notice_period_days': 60,
                    'renewal_date': today + timedelta(days=18),
                    'dpa_attached': True,
                },
            },
            {
                'title': 'Atlas Workforce Order Confirmation 2026',
                'contract_type': Contract.ContractType.ORDER_CONFIRMATION,
                'counterparty': 'Atlas Workforce B.V.',
                'status': Contract.Status.IN_PROGRESS,
                'stage': 'APPROVAL',
                'owner': 'payrollminds_procurement',
                'value': 42000,
                'start': today + timedelta(days=14),
                'end': today + timedelta(days=379),
                'risk': Contract.RiskLevel.MEDIUM,
                'content': (
                    'Order confirmation under MSA-PM-2026-001 for payroll implementation and '
                    'managed service support in the Netherlands and Belgium. Finance approval '
                    'is required before signature.'
                ),
                'extra': {'governing_law': 'Netherlands', 'jurisdiction': 'Amsterdam'},
            },
            {
                'title': 'Consultancy Services Agreement — HRIS rollout',
                'contract_type': Contract.ContractType.CONSULTING,
                'counterparty': 'PeopleOps Advisory B.V.',
                'status': Contract.Status.IN_PROGRESS,
                'stage': 'INTERNAL_REVIEW',
                'owner': 'payrollminds_legal',
                'value': 96000,
                'start': today + timedelta(days=14),
                'end': today + timedelta(days=379),
                'risk': Contract.RiskLevel.MEDIUM,
                'content': (
                    'Consultancy support for the HRIS rollout across Payrollminds operating '
                    'entities, including discovery, configuration, testing, and go-live support.'
                ),
                'extra': {'governing_law': 'Netherlands', 'jurisdiction': 'Utrecht'},
            },
            {
                'title': 'Data Processing Agreement — Cloud payroll',
                'contract_type': Contract.ContractType.DPA,
                'counterparty': 'CloudPay Europe S.à r.l.',
                'status': Contract.Status.IN_PROGRESS,
                'stage': 'NEGOTIATION',
                'owner': 'payrollminds_legal',
                'value': None,
                'start': today,
                'end': today + timedelta(days=730),
                'risk': Contract.RiskLevel.HIGH,
                'content': (
                    'Payrollminds is controller and CloudPay Europe is processor for employee '
                    'identity, salary, tax, bank, and national-identifier data. The draft includes '
                    'a 24-hour breach notification, on-site audit rights, and a DPA liability '
                    'override that requires negotiation against the governing MSA.'
                ),
                'extra': {
                    'governing_law': 'Luxembourg',
                    'jurisdiction': 'Luxembourg',
                    'data_transfer_flag': True,
                    'scc_attached': True,
                },
            },
            {
                'title': 'Mutual NDA — FinTalent partnership',
                'contract_type': Contract.ContractType.NDA,
                'counterparty': 'FinTalent Group B.V.',
                'status': Contract.Status.IN_PROGRESS,
                'stage': 'DRAFTING',
                'owner': 'payrollminds_procurement',
                'value': None,
                'start': None,
                'end': None,
                'risk': Contract.RiskLevel.LOW,
                'content': (
                    'Mutual confidentiality agreement for early partnership discussions, '
                    'including candidate and customer information exchanged during diligence.'
                ),
                'extra': {'governing_law': 'Netherlands', 'jurisdiction': 'Rotterdam'},
            },
            {
                'title': 'Addendum — 2026 pricing and service levels',
                'contract_type': Contract.ContractType.AMENDMENT,
                'counterparty': 'Northstar Benefits B.V.',
                'status': Contract.Status.ACTIVE,
                'stage': 'RENEWAL',
                'owner': 'payrollminds_admin',
                'value': 12500,
                'start': today - timedelta(days=30),
                'end': today + timedelta(days=27),
                'risk': Contract.RiskLevel.LOW,
                'content': (
                    'Pricing and service-level addendum covering the 2026 plan year, including '
                    'monthly reporting, response times, and an annual indexation review.'
                ),
                'extra': {
                    'governing_law': 'Netherlands',
                    'jurisdiction': 'Amsterdam',
                    'notice_period_days': 30,
                },
            },
        )

        contracts = {}
        for record in records:
            contract, _ = Contract.objects.update_or_create(
                organization=organization,
                title=record['title'],
                defaults={
                    'contract_type': record['contract_type'],
                    'counterparty': record['counterparty'],
                    'status': record['status'],
                    'lifecycle_stage': record['stage'],
                    'owner': users[record['owner']],
                    'created_by': users['payrollminds_admin'],
                    'value': record['value'],
                    'currency': Contract.Currency.EUR,
                    'start_date': record['start'],
                    'end_date': record['end'],
                    'risk_level': record['risk'],
                    'content': record['content'],
                    'origin_kind': Contract.OriginKind.SEED,
                    'origin_channel': 'seed_payrollminds_demo',
                    'origin_reason': 'Payrollminds demo seed data',
                    **record['extra'],
                },
            )
            contracts[record['title']] = contract

        msa = contracts['Payrollminds Master Services Agreement']
        order_confirmation = contracts['Atlas Workforce Order Confirmation 2026']
        consultancy = contracts['Consultancy Services Agreement — HRIS rollout']
        dpa = contracts['Data Processing Agreement — Cloud payroll']
        nda = contracts['Mutual NDA — FinTalent partnership']
        addendum = contracts['Addendum — 2026 pricing and service levels']

        if order_confirmation.parent_contract_id != msa.pk:
            order_confirmation.parent_contract = msa
            order_confirmation.save(update_fields=['parent_contract', 'updated_at'])

        for contract, snapshots in (
            (
                msa,
                (
                    (1, Contract.Status.IN_PROGRESS, 'Initial negotiated draft', 'Initial commercial draft uploaded for legal review.'),
                    (2, Contract.Status.ACTIVE, msa.content, 'Executed terms and final commercial schedule.'),
                ),
            ),
            (
                order_confirmation,
                ((1, Contract.Status.IN_PROGRESS, order_confirmation.content, 'Order confirmation routed for Legal and Finance approval.'),),
            ),
            (
                dpa,
                ((1, Contract.Status.IN_PROGRESS, dpa.content, 'Counterparty DPA imported and privacy review opened.'),),
            ),
            (
                consultancy,
                ((1, Contract.Status.IN_PROGRESS, consultancy.content, 'First internal review draft.'),),
            ),
        ):
            for version_number, status, content, summary in snapshots:
                ContractVersion.objects.get_or_create(
                    contract=contract,
                    version_number=version_number,
                    defaults={
                        'title_snapshot': contract.title,
                        'status_snapshot': status,
                        'content_snapshot': content,
                        'change_summary': summary,
                        'changed_by': users['payrollminds_legal'],
                    },
                )

        msa_draft = self._document(
            organization, msa, users['payrollminds_legal'],
            title='Payrollminds MSA — negotiated draft',
            filename='payrollminds-msa-v1-negotiated-draft.pdf',
            version=1,
            status=Document.Status.DRAFT,
            lines=(
                'Counterparty: Atlas Workforce B.V.',
                'Version: 1 - negotiated draft',
                'Commercial terms under review by Payrollminds Legal.',
                'Annual contract value: EUR 180,000.',
            ),
        )
        msa_final = self._document(
            organization, msa, users['payrollminds_legal'],
            title='Payrollminds MSA — executed agreement',
            filename='payrollminds-msa-v2-executed.pdf',
            version=2,
            status=Document.Status.FINAL,
            parent=msa_draft,
            lines=(
                'Counterparty: Atlas Workforce B.V.',
                'Version: 2 - executed agreement',
                'Effective date: %s' % msa.start_date.isoformat(),
                'Annual contract value: EUR 180,000.',
                'Renewal decision due: %s' % msa.end_date.isoformat(),
            ),
        )
        order_document = self._document(
            organization, order_confirmation, users['payrollminds_procurement'],
            title='Atlas Workforce Order Confirmation 2026',
            filename='atlas-workforce-order-confirmation-2026.pdf',
            version=1,
            status=Document.Status.DRAFT,
            lines=(
                'Governing agreement: Payrollminds Master Services Agreement.',
                'Implementation and managed payroll services.',
                'Order value: EUR 42,000.',
                'Current route: Legal approved; Finance pending.',
            ),
        )
        dpa_document = self._document(
            organization, dpa, users['payrollminds_legal'],
            title='CloudPay Europe DPA — counterparty paper',
            filename='cloudpay-europe-dpa-counterparty-paper.pdf',
            version=1,
            status=Document.Status.DRAFT,
            lines=(
                'Payroll data processing for Payrollminds customers and employees.',
                'Breach notification: within 24 hours.',
                'Audit: on-site audit right on reasonable notice.',
                'Liability: DPA terms override conflicting MSA limitations.',
            ),
        )
        self._document(
            organization, consultancy, users['payrollminds_legal'],
            title='HRIS rollout consultancy agreement — internal draft',
            filename='hris-rollout-consultancy-draft.pdf',
            version=1,
            status=Document.Status.DRAFT,
            lines=(
                'Counterparty: PeopleOps Advisory B.V.',
                'Scope: discovery, configuration, testing, and go-live.',
                'Contract value: EUR 96,000.',
                'Current stage: internal review.',
            ),
        )

        ApprovalRequest.objects.update_or_create(
            organization=organization,
            contract=order_confirmation,
            approval_step='LEGAL',
            defaults={
                'status': ApprovalRequest.Status.APPROVED,
                'assigned_to': users['payrollminds_legal'],
                'decided_by': users['payrollminds_legal'],
                'decided_at': now - timedelta(days=1),
                'comments': 'Commercial and governing-agreement alignment confirmed.',
                'due_date': now + timedelta(days=1),
            },
        )
        ApprovalRequest.objects.update_or_create(
            organization=organization,
            contract=order_confirmation,
            approval_step='FINANCE',
            defaults={
                'status': ApprovalRequest.Status.PENDING,
                'assigned_to': users['payrollminds_finance'],
                'decided_by': None,
                'decided_at': None,
                'comments': 'Confirm implementation budget and 2026 cost centre.',
                'due_date': now + timedelta(days=2),
            },
        )
        ApprovalRequest.objects.update_or_create(
            organization=organization,
            contract=dpa,
            approval_step='PRIVACY',
            defaults={
                'status': ApprovalRequest.Status.PENDING,
                'assigned_to': users['payrollminds_legal'],
                'decided_by': None,
                'decided_at': None,
                'comments': 'Resolve open breach, audit, and liability positions.',
                'due_date': now + timedelta(days=3),
            },
        )

        SignatureRequest.objects.update_or_create(
            organization=organization,
            contract=msa,
            signer_email='contracting@atlasworkforce.example',
            defaults={
                'document': msa_final,
                'signer_name': 'Elise van Dijk',
                'signer_role': 'Commercial Director',
                'status': SignatureRequest.Status.SIGNED,
                'external_id': 'DEMO-ATLAS-MSA-2026-001',
                'esign_provider': 'demo',
                'sent_at': now - timedelta(days=122),
                'viewed_at': now - timedelta(days=121, hours=20),
                'signed_at': now - timedelta(days=120),
                'ip_address': '192.0.2.25',
                'order': 1,
                'created_by': users['payrollminds_admin'],
            },
        )

        review_pack, _ = DPAReviewPack.objects.update_or_create(
            organization=organization,
            contract=dpa,
            defaults={
                'reviewer': users['payrollminds_legal'],
                'role_qualification': DPAReviewPack.RoleQualification.CONTROLLER_PROCESSOR,
                'role_qualification_notes': 'Payrollminds acts as controller; CloudPay Europe acts as processor.',
                'subprocessors_involved': True,
                'data_subject_categories': 'Employees, contractors, directors, and payroll administrators.',
                'personal_data_categories': 'Identity, contact, employment, payroll, tax, bank, and benefits data.',
                'special_category_data': 'Absence and statutory leave data where required for payroll.',
                'processing_purposes': 'Payroll calculation, statutory reporting, payments, and employee support.',
                'processing_duration': 'Contract term plus legally required retention.',
                'retention_obligations': 'Delete or return within 30 days, subject to statutory payroll retention.',
                'systems_tools_vendors': 'CloudPay Europe payroll platform and approved subprocessors.',
                'has_employee_identity_data': True,
                'has_salary_wage_data': True,
                'has_tax_data': True,
                'has_social_security_data': True,
                'has_bank_account_data': True,
                'has_absence_leave_data': True,
                'has_employment_contract_data': True,
                'has_national_identifiers': True,
                'has_payslip_data': True,
                'has_cross_border_payroll_data': True,
                'subprocessor_general_authorization_allowed': True,
                'subprocessor_notification_period_days': 30,
                'transfers_outside_eea': True,
                'transfer_mechanism_present': True,
                'transfer_escalation_required': False,
                'transfer_notes': 'EU SCCs are attached; transfer impact evidence remains subject to annual review.',
                'security_encryption': True,
                'security_access_control': True,
                'security_mfa': True,
                'security_logging': True,
                'security_backup': True,
                'security_incident_response': True,
                'security_data_segregation': True,
                'security_measures_specific': True,
                'breach_notification_deadline_hours': 24,
                'breach_notification_realistic': False,
                'breach_notification_conflicts_msa': True,
                'breach_notification_notes': 'Move to without undue delay and no later than 48 hours.',
                'dsar_assistance_required': True,
                'dsar_assistance_deadline_days': 5,
                'audit_rights_onsite_allowed': True,
                'audit_rights_frequency_limited': False,
                'audit_third_party_reports_accepted': True,
                'audit_costs_addressed': False,
                'audit_conflicts_msa': True,
                'audit_notes': 'Use independent assurance first; reserve on-site audit for material incidents.',
                'deletion_return_deadline_days': 30,
                'deletion_legal_retention_conflict': True,
                'deletion_backup_addressed': True,
                'deletion_certification_required': True,
                'liability_uncapped': True,
                'liability_overrides_msa_cap': True,
                'liability_conflicts_standard_position': True,
                'liability_notes': 'DPA override conflicts with the MSA twelve-month fees cap.',
                'review_memo': (
                    'Three negotiation items remain before privacy approval: breach timing, '
                    'audit scope and costs, and preservation of the MSA liability framework.'
                ),
                'review_memo_generated_at': now,
                'last_analyzed_at': now,
                'approval_status': DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
                'created_by': users['payrollminds_admin'],
            },
        )
        review_pack.related_contracts.set([msa])
        review_pack.documents.set([dpa_document, msa_final])

        risks = (
            {
                'category': DPARiskItem.Category.BREACH_NOTIFICATION,
                'title': '24-hour breach notice is operationally unrealistic',
                'description': 'The counterparty draft requires a complete notice within 24 hours of awareness.',
                'severity': DPARiskItem.Severity.HIGH,
                'confidence': DPARiskItem.Confidence.HIGH,
                'owners': 'LEGAL,BUSINESS',
                'fallback_recommendation': 'Notify without undue delay and no later than 48 hours, with staged updates.',
                'evidence_text': 'Processor shall provide full breach notice within 24 hours.',
                'source_section': 'Security incident notification',
                'status': DPARiskItem.Status.OPEN,
                'detected_automatically': True,
            },
            {
                'category': DPARiskItem.Category.AUDIT,
                'title': 'Unrestricted on-site audit right',
                'description': 'The draft does not limit audit frequency, cost allocation, or use of assurance reports.',
                'severity': DPARiskItem.Severity.MEDIUM,
                'confidence': DPARiskItem.Confidence.HIGH,
                'owners': 'LEGAL,DPO_SECURITY',
                'fallback_recommendation': 'Use SOC 2 or ISO evidence first and permit one annual on-site audit for cause.',
                'evidence_text': 'Controller may audit processor facilities at any time on reasonable notice.',
                'source_section': 'Audit rights',
                'status': DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT,
                'detected_automatically': True,
            },
            {
                'category': DPARiskItem.Category.LIABILITY,
                'title': 'DPA overrides the MSA liability cap',
                'description': 'The DPA creates uncapped exposure and expressly overrides the negotiated MSA.',
                'severity': DPARiskItem.Severity.CRITICAL,
                'confidence': DPARiskItem.Confidence.HIGH,
                'owners': 'LEGAL,FINANCE',
                'fallback_recommendation': 'Preserve the MSA cap with a negotiated super-cap only for defined privacy breaches.',
                'evidence_text': 'The limitations of liability in the MSA do not apply to this DPA.',
                'related_contract_evidence_text': 'Aggregate liability is limited to fees paid in the preceding twelve months.',
                'source_section': 'Liability',
                'status': DPARiskItem.Status.ESCALATED,
                'detected_automatically': True,
                'is_cross_document_conflict': True,
                'conflict_type': 'DPA_MSA_LIABILITY_CAP',
            },
        )
        for risk in risks:
            DPARiskItem.objects.update_or_create(
                review_pack=review_pack,
                title=risk['title'],
                defaults=risk,
            )

        DPAApprovalHistoryEntry.objects.get_or_create(
            review_pack=review_pack,
            to_status=DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
            comment='Privacy review opened with three owned negotiation issues.',
            defaults={
                'from_status': DPAReviewPack.ApprovalStatus.DRAFT,
                'changed_by': users['payrollminds_legal'],
                'risk_counts_by_severity': {'CRITICAL': 1, 'HIGH': 1, 'MEDIUM': 1},
                'unresolved_blocker_count': 2,
            },
        )

        deadlines = (
            (
                msa, 'MSA renewal decision', Deadline.DeadlineType.RENEWAL,
                Deadline.Priority.HIGH, today + timedelta(days=18), users['payrollminds_legal'],
                'Decide whether to renew, renegotiate, or serve notice before the commercial window closes.',
            ),
            (
                dpa, 'Review next subprocessor notification', Deadline.DeadlineType.REGULATORY,
                Deadline.Priority.HIGH, today + timedelta(days=9), users['payrollminds_legal'],
                'Confirm the proposed payroll hosting subprocessor and transfer safeguards.',
            ),
            (
                consultancy, 'Approve HRIS discovery milestone', Deadline.DeadlineType.CLIENT,
                Deadline.Priority.MEDIUM, today + timedelta(days=30), users['payrollminds_procurement'],
                'Accept the discovery deliverable before configuration work begins.',
            ),
            (
                addendum, 'Review 2027 pricing indexation', Deadline.DeadlineType.PAYMENT,
                Deadline.Priority.MEDIUM, today + timedelta(days=27), users['payrollminds_finance'],
                'Validate the indexation formula and resulting annual budget impact.',
            ),
            (
                nda, 'Confirm NDA term before partnership launch', Deadline.DeadlineType.NDA_EXPIRY,
                Deadline.Priority.LOW, today + timedelta(days=60), users['payrollminds_procurement'],
                'Set the confidentiality period and surviving obligations before signature.',
            ),
        )
        for contract, title, deadline_type, priority, due_date, assignee, description in deadlines:
            Deadline.objects.update_or_create(
                contract=contract,
                title=title,
                defaults={
                    'description': description,
                    'deadline_type': deadline_type,
                    'priority': priority,
                    'due_date': due_date,
                    'reminder_days': 14,
                    'assigned_to': assignee,
                    'created_by': users['payrollminds_admin'],
                },
            )

        self._audit_once(
            organization, users['payrollminds_admin'], msa, AuditLog.Action.CREATE,
            'contract.demo_imported',
            {'source': 'Payrollminds buyer demo', 'document_id': msa_final.pk},
        )
        self._audit_once(
            organization, users['payrollminds_legal'], msa, AuditLog.Action.APPROVE,
            'contract.executed_evidence_recorded',
            {'signature_external_id': 'DEMO-ATLAS-MSA-2026-001'},
        )
        self._audit_once(
            organization, users['payrollminds_legal'], dpa, AuditLog.Action.UPDATE,
            'dpa.review_opened',
            {'review_pack_id': review_pack.pk, 'open_risk_count': 3},
        )

        self.stdout.write(self.style.SUCCESS(
            'Payrollminds demo ready: '
            f'{organization.slug} ({len(contracts)} contracts, '
            f'{organization.documents.count()} documents, '
            f'{organization.approval_requests.count()} approvals)'
        ))
        self.stdout.write(f'  payrollminds_admin / {DEMO_PASSWORD}')

    @staticmethod
    def _document(
        organization, contract, uploader, *, title, filename, version, status, lines, parent=None,
    ):
        document, _ = Document.objects.update_or_create(
            organization=organization,
            contract=contract,
            title=title,
            version=version,
            defaults={
                'document_type': Document.DocType.CONTRACT,
                'status': status,
                'description': 'Payrollminds demonstration source document.',
                'parent_document': parent,
                'uploaded_by': uploader,
                'is_confidential': True,
            },
        )
        if not document.file:
            document.file.save(filename, ContentFile(_pdf_bytes(title, lines)), save=True)
        return document

    @staticmethod
    def _audit_once(organization, user, contract, action, event_type, changes):
        if AuditLog.objects.filter(
            organization=organization,
            model_name='Contract',
            object_id=contract.pk,
            event_type=event_type,
        ).exists():
            return
        log_action(
            user,
            action,
            'Contract',
            contract.pk,
            contract.title,
            changes,
            organization=organization,
            event_type=event_type,
            actor_type=AuditLog.ActorType.HUMAN,
        )
