"""PAR-APR-001 — Approval Requirement / Decision canonical model tests."""

from __future__ import annotations

import hashlib

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from contracts.models import (
    ApprovalDecision,
    ApprovalRequirement,
    ApprovalRequest,
    AuditLog,
    Contract,
    Document,
    Organization,
    OrganizationMembership,
)
from contracts.services.approval_canonical import (
    EVENT_DECISION_RECORDED,
    EVENT_REQUIREMENT_CREATED,
    EVENT_REQUIREMENT_INVALIDATED,
    create_approval_requirement,
    invalidate_open_requirements_for_contract,
    record_approval_decision,
)
from contracts.services.approval_workflow import ApprovalAccessDenied, ApprovalWorkflowService, authorize_approval_actor
from contracts.services.document_version_service import create_document_version


User = get_user_model()


class ApprovalCanonicalTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='APR Org', slug='apr-org')
        self.owner = User.objects.create_user(username='apr-owner', password='pass12345')
        self.reviewer = User.objects.create_user(username='apr-reviewer', password='pass12345')
        self.other_org = Organization.objects.create(name='Other APR', slug='other-apr')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.reviewer, role=OrganizationMembership.Role.ADMIN, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='APR Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            owner=self.owner,
            created_by=self.owner,
        )
        self.doc, self.doc_ver = create_document_version(
            organization=self.org,
            title='APR Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=SimpleUploadedFile('apr.txt', b'apr-bytes', content_type='text/plain'),
            uploaded_by=self.owner,
            source='manual_upload',
        )

    def test_requirement_creation_binds_document_version(self):
        req = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            authority_basis='manual',
            actor=self.owner,
        )
        self.assertEqual(req.document_version_id, self.doc_ver.pk)
        self.assertFalse(req.document_version_missing)
        self.assertEqual(req.contract_status_at_open, Contract.Status.IN_PROGRESS)
        self.assertTrue(AuditLog.objects.filter(event_type=EVENT_REQUIREMENT_CREATED).exists())

    def test_decision_is_immutable_and_binds_state(self):
        legacy = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )
        req = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            legacy_request=legacy,
            actor=self.owner,
        )
        decision = record_approval_decision(req, action='approve', actor=self.reviewer, comments='LGTM')
        self.assertEqual(decision.outcome, ApprovalDecision.Outcome.APPROVED)
        self.assertEqual(decision.document_version_id, self.doc_ver.pk)
        self.assertEqual(req.status, ApprovalRequirement.Status.SATISFIED)
        decision.comments = 'tampered'
        with self.assertRaises(Exception):
            decision.save()
        self.assertTrue(AuditLog.objects.filter(event_type=EVENT_DECISION_RECORDED).exists())

    def test_reject_and_return_create_distinct_outcomes(self):
        for action, outcome, status in [
            ('reject', ApprovalDecision.Outcome.REJECTED, ApprovalRequirement.Status.REJECTED),
            ('request_changes', ApprovalDecision.Outcome.RETURNED, ApprovalRequirement.Status.RETURNED),
        ]:
            contract = Contract.objects.create(
                organization=self.org,
                title=f'C-{action}',
                contract_type=Contract.ContractType.MSA,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage=Contract.LifecycleStage.APPROVAL,
                owner=self.owner,
                created_by=self.owner,
            )
            req = create_approval_requirement(
                organization=self.org,
                contract=contract,
                approval_step='LEGAL',
                assigned_to=self.reviewer,
                actor=self.owner,
            )
            record_approval_decision(req, action=action, actor=self.reviewer, comments=f'{action} note')
            decision = req.decisions.get()
            self.assertEqual(decision.outcome, outcome)
            req.refresh_from_db()
            self.assertEqual(req.status, status)

    def test_workflow_service_records_canonical_decision(self):
        legacy = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='FINANCE',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )
        create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='FINANCE',
            assigned_to=self.reviewer,
            legacy_request=legacy,
            actor=self.owner,
        )
        svc = ApprovalWorkflowService()
        svc.approve(legacy.pk, self.reviewer, comments='Approved via service')
        self.assertEqual(ApprovalDecision.objects.filter(requirement__legacy_request=legacy).count(), 1)
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, ApprovalRequest.Status.APPROVED)

    def test_delegation_attributed_on_decision(self):
        delegate = User.objects.create_user(username='apr-delegate', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=delegate, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        legacy = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
            delegated_to=delegate,
        )
        req = legacy.canonical_requirement
        req.delegated_to = delegate
        req.save(update_fields=['delegated_to', 'updated_at'])
        decision = record_approval_decision(req, action='approve', actor=delegate, comments='Delegated OK')
        self.assertTrue(decision.acting_under_delegation)
        self.assertEqual(decision.authority_holder_id, self.reviewer.pk)

    def test_material_document_change_invalidates_open_requirements(self):
        legacy = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )
        req = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            legacy_request=legacy,
            actor=self.owner,
        )
        _doc2, ver2 = create_document_version(
            organization=self.org,
            title='APR Doc v2',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=SimpleUploadedFile('v2.txt', b'v2', content_type='text/plain'),
            uploaded_by=self.owner,
            source='document_edit',
            derived_from_document=self.doc,
            parent_document=self.doc,
            supersede_prior=True,
        )
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequirement.Status.INVALIDATED)
        self.assertTrue(req.decisions.filter(outcome=ApprovalDecision.Outcome.REVOKED).exists())
        self.assertTrue(AuditLog.objects.filter(event_type=EVENT_REQUIREMENT_INVALIDATED).exists())

    def test_queryset_update_blocked_on_decision(self):
        req = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            actor=self.owner,
        )
        record_approval_decision(req, action='approve', actor=self.reviewer, comments='ok')
        decision = req.decisions.get()
        from contracts.services.approval_canonical import ApprovalCanonicalError
        with self.assertRaises(ApprovalCanonicalError):
            ApprovalDecision.objects.filter(pk=decision.pk).update(comments='bad')

    def test_cross_tenant_decision_forbidden(self):
        other_user = User.objects.create_user(username='other-apr', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.other_org, user=other_user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        legacy = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )
        with self.assertRaises(ApprovalAccessDenied):
            authorize_approval_actor(legacy, other_user, action='approve')

    def test_legacy_request_save_creates_requirement(self):
        ar = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='PRIVACY',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )
        self.assertTrue(hasattr(ar, 'canonical_requirement'))
        self.assertEqual(ar.canonical_requirement.approval_step, 'PRIVACY')

    def test_multiple_decisions_allowed_on_reopened_requirement_episode(self):
        req1 = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            actor=self.owner,
        )
        record_approval_decision(req1, action='request_changes', actor=self.reviewer, comments='fix it')
        req2 = create_approval_requirement(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.reviewer,
            actor=self.owner,
        )
        record_approval_decision(req2, action='approve', actor=self.reviewer, comments='fixed')
        self.assertEqual(ApprovalDecision.objects.filter(requirement__contract=self.contract).count(), 2)
