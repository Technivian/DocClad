"""Seed a Payrollminds DPA Review Pack demo scenario.

Creates: the Payrollminds counterparty, a DPA contract with realistic
clause text (deliberately containing several real review issues — a
contradictory subprocessor authorization model, a non-EEA subprocessor
with no transfer mechanism, vague security language, an unrealistic
4-hour breach notification deadline, chargeable DSAR assistance,
unlimited-frequency on-site audit rights, a deletion deadline that
conflicts with statutory payroll retention, and DPA liability language
that overrides the MSA cap) — a non-EEA Subprocessor, a TransferRecord,
the DPAReviewPack itself, and the 12 default DPA playbook positions.

Idempotent: safe to re-run, matches existing rows by natural keys instead
of creating duplicates.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from contracts.models import (
    Contract,
    Counterparty,
    DPAPlaybookPosition,
    DPAReviewPack,
    Organization,
    Subprocessor,
    TransferRecord,
)

User = get_user_model()

DPA_CONTENT = """DATA PROCESSING AGREEMENT

This Data Processing Agreement ("DPA") is entered into between the Client
("Controller") and Payrollminds B.V. ("Processor") and forms part of the
Master Service Agreement between the parties for payroll, HR, tax, and
benefits administration services.

1. ROLES OF THE PARTIES
Client is the Controller of Personal Data processed under this DPA.
Payrollminds is the Processor and shall process Personal Data only on
Client's documented instructions. Payrollminds may engage subprocessors
as set out in Section 4.

2. PROCESSING DESCRIPTION
Categories of data subjects: Client's current and former employees and
contractors. Categories of Personal Data processed include employee name,
employee ID, date of birth, salary and wage data, tax ID and income tax
withholding data, national insurance number and social security data,
bank account and IBAN details for salary payment, pension and retirement
benefit enrollment data, sick leave and annual leave records, employment
contract terms, national identification number, payroll correction and
retroactive adjustment history, and payslip data. Processing purpose:
payroll calculation, tax withholding, benefits administration, and
payslip generation. Processing duration: for the term of the MSA plus any
statutory retention period.

3. SUBPROCESSORS
Payrollminds may engage subprocessors under a general authorization
without case-by-case approval, provided Payrollminds notifies Client of
any new subprocessor. Notwithstanding the foregoing, Client's prior
written approval is also required before any new subprocessor is engaged
that will access payroll data.

4. INTERNATIONAL TRANSFERS
Payrollminds uses a payroll calculation subprocessor located in the
United States for overflow processing capacity.

5. SECURITY MEASURES
Payrollminds shall implement appropriate technical and organizational
measures, including encryption of data at rest and regular backup of
payroll records, to protect Personal Data against unauthorized access.

6. BREACH NOTIFICATION
Payrollminds shall notify Client within 4 hours of becoming aware of a
Personal Data Breach affecting Client's Personal Data.

7. ASSISTANCE WITH DATA SUBJECT REQUESTS
Payrollminds shall assist Client in responding to data subject requests.
Such assistance shall be provided at Payrollminds' reasonable costs where
the request requires substantial engineering or manual effort.

8. AUDIT RIGHTS
Client may conduct an on-site audit of Payrollminds' processing
facilities and systems relating to this DPA upon reasonable notice.

9. DELETION AND RETURN
Upon termination, Payrollminds shall delete or return all Personal Data
within 30 days, except that payroll and tax records subject to statutory
retention requirements shall be retained for the applicable statutory
period.

10. LIABILITY
Notwithstanding the limitation of liability in the Agreement, Payrollminds'
liability for any breach of this DPA relating to Personal Data shall be
uncapped. Payrollminds shall indemnify Client for losses arising from a
Personal Data Breach caused by Payrollminds' failure to comply with this
DPA.
"""

DEFAULT_PLAYBOOK_POSITIONS = [
    (DPAPlaybookPosition.Topic.PROCESSOR_ROLE_WORDING,
     'Payrollminds is Processor only; Client is Controller. No joint- or independent-controller language.',
     '"Client is the Controller and Payrollminds is the Processor of Personal Data processed under this DPA."',
     'Joint/independent-controller wording shifts liability and notice obligations onto Payrollminds.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.CONTROLLER_INSTRUCTIONS,
     'Payrollminds processes only on Client\'s documented instructions, with a right to flag instructions it believes are unlawful.',
     '"Payrollminds shall process Personal Data only on Client\'s documented instructions, and shall promptly inform Client if, in its opinion, an instruction infringes applicable data protection law."',
     'Without this clause Payrollminds can be forced to execute an unlawful instruction.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.SUBPROCESSOR_AUTHORIZATION,
     'General authorization with a fixed notice period and client objection right — never case-by-case prior approval, which conflicts with Payrollminds\' delivery model.',
     '"Payrollminds may engage subprocessors under a general written authorization, subject to 30 days\' prior notice and Client\'s right to object on reasonable grounds."',
     'Case-by-case prior approval is operationally incompatible with a multi-tenant payroll platform.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.INTERNATIONAL_TRANSFERS,
     'Any non-EEA processing location must have an identified transfer mechanism before go-live.',
     '"Transfers of Personal Data outside the EEA shall be subject to Standard Contractual Clauses (or another valid transfer mechanism) executed prior to such transfer taking place."',
     'Cross-border payroll transfer without a mechanism is a direct GDPR Chapter V violation.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.SCC,
     'Use the EU Commission\'s 2021 modular SCCs (Module 2, Controller-to-Processor) as the default transfer mechanism.',
     '', 'Older/non-standard SCC versions may not satisfy current regulatory guidance.', 'DPO_SECURITY'),
    (DPAPlaybookPosition.Topic.BREACH_NOTIFICATION,
     'Notify without undue delay and in any event within 72 hours of becoming aware — never same-day/same-hour deadlines.',
     '"Payrollminds shall notify Client without undue delay and in any event within 72 hours after becoming aware of a Personal Data Breach."',
     'Sub-24-hour deadlines are frequently missed in practice and create contractual breach exposure on top of the incident itself.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.AUDIT_RIGHTS,
     'Accept third-party certification (SOC 2 / ISO 27001) reports in lieu of on-site audits; on-site limited to once per year with reasonable notice and cost allocation addressed.',
     '"Client may audit Payrollminds\' compliance no more than once per calendar year, on 30 days\' notice; Payrollminds\' provision of a current SOC 2 Type II or ISO 27001 report shall satisfy this obligation absent a confirmed security incident."',
     'Unlimited/on-demand audit rights create unbounded operational burden across Payrollminds\' full client base.', 'DELIVERY'),
    (DPAPlaybookPosition.Topic.DELETION_RETURN,
     'Deletion/return deadline must carve out data Payrollminds is legally required to retain under tax/employment law.',
     '"...except that Payrollminds may retain Personal Data to the extent required by applicable statutory retention obligations, and shall delete such data upon expiry of the applicable retention period."',
     'A flat deletion deadline with no statutory carve-out conflicts with payroll/tax record-keeping law.', 'DELIVERY'),
    (DPAPlaybookPosition.Topic.DSAR_ASSISTANCE,
     'DSAR assistance is included in standard fees for reasonable-effort requests; only genuinely exceptional requests may be chargeable, and only with prior Business sign-off.',
     '"Payrollminds shall provide reasonable assistance with data subject requests at no additional charge, except for requests requiring extraordinary effort, which shall be chargeable only following Client\'s prior written agreement to the associated cost."',
     'Open-ended "reasonable costs" language creates unbudgeted, disputable charges.', 'BUSINESS'),
    (DPAPlaybookPosition.Topic.SECURITY_MEASURES,
     'Security measures must be itemized (encryption, access control, MFA, logging, backup, incident response, segregation) in an Annex, not described generically.',
     '', 'Vague "appropriate measures" language cannot be audited or enforced.', 'DPO_SECURITY'),
    (DPAPlaybookPosition.Topic.LIABILITY,
     'DPA liability stays within the MSA\'s liability cap; no uncapped or DPA-specific override of the MSA limitation of liability.',
     '"Nothing in this DPA increases or removes the limitation of liability set out in the Agreement."',
     'An uncapped DPA liability clause defeats the commercial risk allocation negotiated in the MSA.', 'LEGAL'),
    (DPAPlaybookPosition.Topic.CLIENT_DATA_ACCURACY,
     'Client is responsible for the accuracy of payroll input data it provides; Payrollminds is not liable for processing errors caused by inaccurate Client-supplied data.',
     '"Client is solely responsible for the accuracy and completeness of Personal Data it provides to Payrollminds for processing."',
     'Without this, Payrollminds could be held liable for payroll errors caused by Client\'s own data entry mistakes.', 'BUSINESS'),
]


class Command(BaseCommand):
    help = 'Seed a Payrollminds DPA Review Pack demo scenario (counterparty, DPA contract, subprocessor, transfer record, review pack, playbook).'

    def add_arguments(self, parser):
        parser.add_argument('--organization-slug', default='clmone-demo')
        parser.add_argument('--created-by-username', default='demo_admin')

    def handle(self, *args, **options):
        org_slug = options['organization_slug']
        organization = Organization.objects.filter(slug=org_slug).first()
        if organization is None:
            self.stderr.write(self.style.ERROR(f'Organization with slug "{org_slug}" not found.'))
            return

        created_by = User.objects.filter(username=options['created_by_username']).first()

        counterparty, _ = Counterparty.objects.get_or_create(
            organization=organization, name='Payrollminds',
            defaults={
                'entity_type': Counterparty.EntityType.CORPORATION,
                'jurisdiction': 'Netherlands',
                'notes': 'Payroll, HR, tax, and benefits administration processor — handles sensitive payroll/HR/tax/salary/employee/banking data.',
            },
        )

        contract, created = Contract.objects.get_or_create(
            organization=organization, title='Data Processing Agreement — Payrollminds',
            defaults={
                'contract_type': Contract.ContractType.DPA,
                'content': DPA_CONTENT,
                'status': 'IN_REVIEW',
                'counterparty': 'Payrollminds',
                'client': None,
                'data_transfer_flag': True,
                'dpa_attached': True,
                'created_by': created_by,
            },
        )
        if not created and not contract.content:
            contract.content = DPA_CONTENT
            contract.save(update_fields=['content'])

        subprocessor, _ = Subprocessor.objects.get_or_create(
            organization=organization, name='Payrollminds US Overflow Processing LLC',
            defaults={
                'service_type': 'Payroll calculation overflow capacity',
                'country': 'United States',
                'is_eu_based': False,
                'dpa_in_place': True,
                'scc_in_place': False,
                'risk_level': 'HIGH',
                'data_categories': 'Salary, tax, and bank account data for overflow payroll runs',
                'created_by': created_by,
            },
        )

        transfer_record, _ = TransferRecord.objects.get_or_create(
            organization=organization, title='Payrollminds US overflow processing transfer',
            defaults={
                'source_country': 'Netherlands',
                'destination_country': 'United States',
                'transfer_mechanism': TransferRecord.TransferMechanism.SCC,
                'data_categories': 'Salary, tax, bank account data',
                'subprocessor': subprocessor,
                'contract': contract,
                'tia_completed': False,
                'created_by': created_by,
            },
        )

        review_pack, _ = DPAReviewPack.objects.get_or_create(
            organization=organization, contract=contract,
            defaults={'counterparty': counterparty, 'created_by': created_by},
        )
        review_pack.subprocessors.add(subprocessor)
        review_pack.transfer_records.add(transfer_record)

        for topic, position, fallback, risk_note, owner in DEFAULT_PLAYBOOK_POSITIONS:
            DPAPlaybookPosition.objects.get_or_create(
                organization=None, topic=topic,
                defaults={'our_position': position, 'fallback_language': fallback, 'risk_if_deviated': risk_note, 'owner': owner},
            )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded Payrollminds DPA scenario for "{organization.name}": '
            f'contract #{contract.pk}, review pack #{review_pack.pk}.'
        ))
