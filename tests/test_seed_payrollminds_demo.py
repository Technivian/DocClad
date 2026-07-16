"""Regression coverage for the coherent Payrollminds buyer-demo workspace."""
import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from contracts.models import (
    ApprovalRequest,
    Contract,
    ContractVersion,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    SignatureRequest,
)


class PayrollmindsDemoSeedTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix='clmone-payrollminds-demo-')
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def test_seed_is_idempotent_and_creates_a_complete_contract_story(self):
        call_command('seed_payrollminds_demo')
        call_command('seed_payrollminds_demo')

        organization = Organization.objects.get(slug='payrollminds-demo')
        self.assertEqual(organization.contracts.count(), 6)
        self.assertEqual(organization.documents.count(), 5)
        self.assertEqual(
            ContractVersion.objects.filter(contract__organization=organization).count(),
            5,
        )
        self.assertEqual(
            Deadline.objects.filter(contract__organization=organization).count(),
            5,
        )

        msa = organization.contracts.get(title='Payrollminds Master Services Agreement')
        order_confirmation = organization.contracts.get(
            title='Atlas Workforce Order Confirmation 2026',
        )
        self.assertEqual(order_confirmation.parent_contract, msa)
        self.assertEqual(msa.linked_contracts.count(), 1)

        msa_documents = list(msa.documents.order_by('version'))
        self.assertEqual([document.version for document in msa_documents], [1, 2])
        self.assertEqual(msa_documents[1].parent_document, msa_documents[0])
        self.assertEqual(msa_documents[1].status, msa_documents[1].Status.FINAL)
        with msa_documents[1].file.open('rb') as uploaded:
            self.assertEqual(uploaded.read(5), b'%PDF-')

        signature = SignatureRequest.objects.get(
            organization=organization,
            contract=msa,
        )
        self.assertEqual(signature.status, SignatureRequest.Status.SIGNED)
        self.assertEqual(signature.document, msa_documents[1])
        self.assertTrue(signature.external_id)

        approvals = {
            approval.approval_step: approval
            for approval in ApprovalRequest.objects.filter(
                organization=organization,
                contract=order_confirmation,
            )
        }
        self.assertEqual(approvals['LEGAL'].status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(approvals['FINANCE'].status, ApprovalRequest.Status.PENDING)
        self.assertNotEqual(
            approvals['FINANCE'].assigned_to,
            order_confirmation.created_by,
        )

        dpa = organization.contracts.get(contract_type=Contract.ContractType.DPA)
        review_pack = DPAReviewPack.objects.get(contract=dpa)
        self.assertEqual(
            review_pack.approval_status,
            DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
        )
        self.assertEqual(list(review_pack.related_contracts.all()), [msa])
        self.assertEqual(review_pack.documents.count(), 2)
        self.assertEqual(review_pack.risk_items.count(), 3)
        self.assertEqual(
            review_pack.risk_items.filter(
                severity=DPARiskItem.Severity.CRITICAL,
                is_cross_document_conflict=True,
            ).count(),
            1,
        )

        self.assertEqual(
            organization.audit_logs.filter(event_type='contract.demo_imported').count(),
            1,
        )
        self.assertEqual(
            organization.audit_logs.filter(event_type='dpa.review_opened').count(),
            1,
        )
