from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from contracts.models import (
    ApprovalRequirement,
    Organization,
    OrganizationMembership,
    SignaturePacket,
)
from contracts.services.canonical_workflow_runtime import (
    CanonicalWorkflowError,
    ExistingWorkspacePublicationPolicy,
    archive_contract_record,
    create_draft_workflow_version,
    create_final_nda_document_version,
    create_signature_packet,
    create_workflow_definition,
    dispatch_signature_packet,
    export_contract_record,
    launch_nda_workflow_instance,
    open_nda_approval_requirement,
    promote_contract_record,
    publish_workflow_version,
    record_nda_approval,
    record_signature_evidence,
)


User = get_user_model()


def nda_configuration():
    return {
        'steps': [
            {'id': 'intake', 'kind': 'INTAKE'},
            {'id': 'document', 'kind': 'DOCUMENT'},
            {'id': 'approval', 'kind': 'APPROVAL'},
            {'id': 'signature', 'kind': 'SIGNATURE'},
            {'id': 'archive', 'kind': 'ARCHIVE'},
        ],
    }


class CanonicalWorkflowNDAServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Canonical Org', slug='canonical-org')
        self.owner = User.objects.create_user(username='canonical-owner', password='pw')
        self.approver = User.objects.create_user(username='canonical-approver', password='pw')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.owner, role=OrganizationMembership.Role.OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.approver, role=OrganizationMembership.Role.MEMBER,
        )
        self.definition = create_workflow_definition(
            organization=self.organization, key='nda-standard', name='NDA standard', actor=self.owner,
        )
        self.version = create_draft_workflow_version(
            definition=self.definition, configuration=nda_configuration(), actor=self.owner,
        )
        self.version = publish_workflow_version(
            version=self.version, actor=self.owner, policy=ExistingWorkspacePublicationPolicy(),
        )

    def _launch(self, title='Acme NDA'):
        with override_settings(
            CANONICAL_NDA_RUNTIME_ENABLED=True,
            CANONICAL_NDA_RUNTIME_ORG_ALLOWLIST=str(self.organization.pk),
        ):
            return launch_nda_workflow_instance(
                version=self.version, actor=self.owner, title=title, launch_rationale='controlled test',
            )

    def _final_document(self, instance, text=b'final NDA'):
        return create_final_nda_document_version(
            instance=instance,
            actor=self.owner,
            title='Final NDA',
            file=SimpleUploadedFile('nda.txt', text, content_type='text/plain'),
        )

    def test_published_configuration_is_immutable_and_launches_are_pinned(self):
        instance_one = self._launch()
        self.version.configuration = {'steps': []}
        with self.assertRaises(CanonicalWorkflowError):
            self.version.save()

        next_version = create_draft_workflow_version(
            definition=self.definition, configuration=nda_configuration(), actor=self.owner,
        )
        next_version = publish_workflow_version(
            version=next_version, actor=self.owner, policy=ExistingWorkspacePublicationPolicy(),
        )
        self.assertEqual(instance_one.workflow_version_id, self.version.pk)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, self.version.State.SUPERSEDED)
        with override_settings(
            CANONICAL_NDA_RUNTIME_ENABLED=True,
            CANONICAL_NDA_RUNTIME_ORG_ALLOWLIST=str(self.organization.pk),
        ):
            instance_two = launch_nda_workflow_instance(
                version=next_version, actor=self.owner, title='New NDA', launch_rationale='new published version',
            )
        self.assertEqual(instance_two.workflow_version_id, next_version.pk)

    def test_runtime_is_disabled_without_explicit_workspace_activation(self):
        with self.assertRaises(CanonicalWorkflowError):
            launch_nda_workflow_instance(
                version=self.version, actor=self.owner, title='Disabled', launch_rationale='must fail closed',
            )

    def test_end_to_end_chain_requires_immutable_bound_evidence(self):
        instance = self._launch()
        document_version = self._final_document(instance)
        requirement = open_nda_approval_requirement(
            instance=instance, actor=self.owner, approval_step='LEGAL', assigned_to=self.approver,
        )
        decision = record_nda_approval(requirement=requirement, actor=self.approver)
        self.assertEqual(decision.document_version_id, document_version.pk)
        packet = create_signature_packet(instance=instance, actor=self.owner)
        dispatch_signature_packet(packet=packet, actor=self.owner)
        evidence = record_signature_evidence(
            packet=packet, actor=self.owner, event_id='provider-event-1', event_type='signed',
            evidence_payload={'certificate': 'retained'},
        )
        self.assertEqual(packet.status, SignaturePacket.Status.SIGNED)
        self.assertEqual(
            record_signature_evidence(
                packet=packet, actor=self.owner, event_id='provider-event-1', event_type='signed',
                evidence_payload={'certificate': 'retained'},
            ).pk,
            evidence.pk,
        )
        record = promote_contract_record(instance=instance, packet=packet, actor=self.owner)
        self.assertEqual(record.document_version_id, document_version.pk)
        self.assertEqual(record.workflow_version_id, instance.workflow_version_id)
        self.assertEqual(instance.status, instance.Status.COMPLETED)
        archive_contract_record(record=record, actor=self.owner)
        exported = export_contract_record(record=record, actor=self.approver)
        self.assertEqual(exported['document_version_id'], document_version.pk)

    def test_material_change_invalidates_approval_and_active_signature_packet(self):
        instance = self._launch()
        self._final_document(instance, b'v1')
        requirement = open_nda_approval_requirement(
            instance=instance, actor=self.owner, approval_step='LEGAL', assigned_to=self.approver,
        )
        record_nda_approval(requirement=requirement, actor=self.approver)
        packet = create_signature_packet(instance=instance, actor=self.owner)
        dispatch_signature_packet(packet=packet, actor=self.owner)
        self._final_document(instance, b'v2')
        requirement.refresh_from_db()
        packet.refresh_from_db()
        self.assertEqual(requirement.status, ApprovalRequirement.Status.INVALIDATED)
        self.assertEqual(packet.status, SignaturePacket.Status.CANCELLED)

    def test_locked_document_allows_tombstone_metadata_without_content_mutation(self):
        instance = self._launch()
        document_version = self._final_document(instance)
        document = document_version.document_row
        original_hash = document.file_hash
        document.is_deleted = True
        document.save(update_fields=['is_deleted', 'updated_at'])
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)
        self.assertEqual(document.file_hash, original_hash)

    def test_cross_tenant_export_denies_without_returning_record_metadata(self):
        instance = self._launch()
        document_version = self._final_document(instance)
        requirement = open_nda_approval_requirement(
            instance=instance, actor=self.owner, approval_step='LEGAL', assigned_to=self.approver,
        )
        record_nda_approval(requirement=requirement, actor=self.approver)
        packet = create_signature_packet(instance=instance, actor=self.owner)
        dispatch_signature_packet(packet=packet, actor=self.owner)
        record_signature_evidence(packet=packet, actor=self.owner, event_id='provider-event-2', event_type='signed')
        record = promote_contract_record(instance=instance, packet=packet, actor=self.owner)
        other_org = Organization.objects.create(name='Other Canonical Org', slug='other-canonical-org')
        other_user = User.objects.create_user(username='other-canonical-user', password='pw')
        OrganizationMembership.objects.create(
            organization=other_org, user=other_user, role=OrganizationMembership.Role.OWNER,
        )
        with self.assertRaises(PermissionDenied):
            export_contract_record(record=record, actor=other_user)
        self.assertEqual(record.document_version_id, document_version.pk)
