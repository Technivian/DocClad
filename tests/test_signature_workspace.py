from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import ApprovalRequest, AuditLog, Contract, Organization, OrganizationMembership, SignatureRequest


User = get_user_model()


class SignatureWorkspaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='signature-owner',
            email='signature-owner@example.com',
            password='testpass123',
        )
        self.admin = User.objects.create_user(
            username='signature-admin',
            email='signature-admin@example.com',
            password='testpass123',
        )
        self.member = User.objects.create_user(
            username='signature-member',
            email='signature-member@example.com',
            password='testpass123',
        )
        self.org = Organization.objects.create(name='Signature Org', slug='signature-org')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )

        self.queue_contract = Contract.objects.create(
            organization=self.org,
            title='Queue Contract',
            content='Queue contract content',
            created_by=self.owner,
        )
        self.queue_requests = [
            SignatureRequest.objects.create(
                organization=self.org,
                contract=self.queue_contract,
                signer_name='Signer One',
                signer_email='one@example.com',
                signer_role='CEO',
                status=SignatureRequest.Status.PENDING,
                order=1,
                created_by=self.owner,
            ),
            SignatureRequest.objects.create(
                organization=self.org,
                contract=self.queue_contract,
                signer_name='Signer Two',
                signer_email='two@example.com',
                signer_role='CFO',
                status=SignatureRequest.Status.SENT,
                order=2,
                sent_at=timezone.now() - timedelta(days=1),
                created_by=self.owner,
            ),
            SignatureRequest.objects.create(
                organization=self.org,
                contract=self.queue_contract,
                signer_name='Signer Three',
                signer_email='three@example.com',
                signer_role='GC',
                status=SignatureRequest.Status.VIEWED,
                order=3,
                sent_at=timezone.now() - timedelta(days=2),
                viewed_at=timezone.now() - timedelta(days=1),
                created_by=self.owner,
            ),
        ]

        self.audit_contract = Contract.objects.create(
            organization=self.org,
            title='Audit Contract',
            content='Audit contract content',
            created_by=self.owner,
        )
        self.lifecycle_contract = Contract.objects.create(
            organization=self.org,
            title='Lifecycle Contract',
            content='Lifecycle contract content',
            created_by=self.owner,
        )
        self.lifecycle_request = SignatureRequest.objects.create(
            organization=self.org,
            contract=self.lifecycle_contract,
            signer_name='Lifecycle Signer',
            signer_email='audit@example.com',
            signer_role='Signer',
            status=SignatureRequest.Status.PENDING,
            order=1,
            created_by=self.owner,
        )

        self.cancel_contract = Contract.objects.create(
            organization=self.org,
            title='Cancel Contract',
            content='Cancel contract content',
            created_by=self.owner,
        )
        self.cancel_request = SignatureRequest.objects.create(
            organization=self.org,
            contract=self.cancel_contract,
            signer_name='Cancel Signer',
            signer_email='cancel@example.com',
            signer_role='Signer',
            status=SignatureRequest.Status.PENDING,
            order=1,
            created_by=self.owner,
        )

        self.retry_contract = Contract.objects.create(
            organization=self.org,
            title='Retry Contract',
            content='Retry contract content',
            created_by=self.owner,
        )
        self.retry_request = SignatureRequest.objects.create(
            organization=self.org,
            contract=self.retry_contract,
            signer_name='Retry Signer',
            signer_email='retry@example.com',
            signer_role='Signer',
            status=SignatureRequest.Status.DECLINED,
            order=1,
            external_id='provider-123',
            declined_at=timezone.now() - timedelta(days=2),
            decline_reason='Provider rejected the request',
            created_by=self.owner,
        )

    def test_signature_queue_renders_packet_metrics_and_actions(self):
        self.client.login(username='signature-owner', password='testpass123')
        response = self.client.get(reverse('contracts:signature_request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Signature Workspace')
        self.assertContains(response, 'Packet Queue')
        self.assertContains(response, 'Queue Contract')
        self.assertContains(response, '3 total')
        self.assertContains(response, 'Open')
        self.assertContains(response, 'Resend')
        self.assertContains(response, 'Cancel')

    def test_signature_packet_detail_renders_progress_and_timeline(self):
        self.client.login(username='signature-owner', password='testpass123')
        response = self.client.get(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': self.queue_contract.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Packet Progress')
        self.assertContains(response, 'Timeline')
        self.assertContains(response, 'Signer 1')
        self.assertContains(response, 'Signer 2')
        self.assertContains(response, 'Signer 3')
        self.assertContains(response, 'Current position')

    def test_signature_packet_creation_writes_audit_entry(self):
        self.audit_contract.status = Contract.Status.IN_PROGRESS
        self.audit_contract.lifecycle_stage = Contract.LifecycleStage.SIGNATURE
        self.audit_contract.save(update_fields=['status', 'lifecycle_stage', 'updated_at'])
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.audit_contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.APPROVED,
            assigned_to=self.admin,
        )
        self.client.login(username='signature-owner', password='testpass123')
        create_response = self.client.post(
            reverse('contracts:signature_request_create'),
            data={
                'contract': self.audit_contract.pk,
                'document': '',
                'signer_name': 'New Signer',
                'signer_email': 'new@example.com',
                'signer_role': 'CEO',
                'status': SignatureRequest.Status.PENDING,
                'order': 1,
            },
        )
        self.assertEqual(create_response.status_code, 302)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='SignaturePacket',
                object_id=self.audit_contract.pk,
                changes__event='signature_packet_created',
            ).exists()
        )

    def test_signature_packet_creation_rejects_unapproved_contract(self):
        self.client.login(username='signature-owner', password='testpass123')
        response = self.client.post(
            reverse('contracts:signature_request_create'),
            data={
                'contract': self.audit_contract.pk,
                'signer_name': 'Blocked Signer',
                'signer_email': 'blocked@example.com',
                'status': SignatureRequest.Status.PENDING,
                'order': 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'before signature routing')
        self.assertFalse(SignatureRequest.objects.filter(contract=self.audit_contract).exists())

    def test_signature_packet_send_and_complete_write_audit_entries(self):
        self.client.login(username='signature-owner', password='testpass123')
        send_url = reverse('contracts:signature_request_transition', args=[self.lifecycle_request.pk, SignatureRequest.Status.SENT])
        complete_url = reverse('contracts:signature_request_transition', args=[self.lifecycle_request.pk, SignatureRequest.Status.SIGNED])

        first_response = self.client.post(send_url)
        self.assertEqual(first_response.status_code, 302)
        self.lifecycle_request.refresh_from_db()
        self.assertEqual(self.lifecycle_request.status, SignatureRequest.Status.SENT)

        second_response = self.client.post(complete_url)
        self.assertEqual(second_response.status_code, 302)
        self.lifecycle_request.refresh_from_db()
        self.assertEqual(self.lifecycle_request.status, SignatureRequest.Status.SIGNED)

        events = list(
            AuditLog.objects.filter(model_name='SignaturePacket', object_id=self.lifecycle_contract.pk)
            .values_list('changes__event', flat=True)
        )
        self.assertIn('signature_packet_sent', events)
        self.assertIn('signature_packet_completed', events)

    def test_signature_packet_resend_cancel_and_retry_write_audit_entries(self):
        self.client.login(username='signature-owner', password='testpass123')

        resend_request = self.queue_requests[1]
        resend_url = reverse('contracts:signature_packet_resend', kwargs={'contract_pk': self.queue_contract.pk})
        resend_response = self.client.post(resend_url)
        self.assertEqual(resend_response.status_code, 302)
        resend_request.refresh_from_db()
        self.assertIsNotNone(resend_request.sent_at)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='SignaturePacket',
                object_id=self.queue_contract.pk,
                changes__event='signature_packet_resend',
            ).exists()
        )

        cancel_url = reverse('contracts:signature_packet_cancel', kwargs={'contract_pk': self.cancel_contract.pk})
        cancel_response = self.client.post(cancel_url)
        self.assertEqual(cancel_response.status_code, 302)
        self.cancel_request.refresh_from_db()
        self.assertEqual(self.cancel_request.status, SignatureRequest.Status.CANCELLED)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='SignaturePacket',
                object_id=self.cancel_contract.pk,
                changes__event='signature_packet_cancel',
            ).exists()
        )

        retry_url = reverse('contracts:signature_packet_retry', kwargs={'contract_pk': self.retry_contract.pk})
        retry_response = self.client.post(retry_url)
        self.assertEqual(retry_response.status_code, 302)
        self.retry_request.refresh_from_db()
        self.assertEqual(self.retry_request.status, SignatureRequest.Status.PENDING)
        self.assertEqual(self.retry_request.external_id, '')
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='SignaturePacket',
                object_id=self.retry_contract.pk,
                changes__event='signature_packet_retry',
            ).exists()
        )

    def test_signature_packet_tenant_isolation(self):
        other_org = Organization.objects.create(name='Other Signature Org', slug='other-signature-org')
        other_user = User.objects.create_user(username='other-signature-user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=other_org,
            user=other_user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        other_contract = Contract.objects.create(
            organization=other_org,
            title='Other Contract',
            created_by=other_user,
        )
        SignatureRequest.objects.create(
            organization=other_org,
            contract=other_contract,
            signer_name='Other Signer',
            signer_email='other@example.com',
            status=SignatureRequest.Status.PENDING,
            order=1,
            created_by=other_user,
        )

        self.client.login(username='signature-owner', password='testpass123')
        response = self.client.get(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': other_contract.pk}))
        self.assertEqual(response.status_code, 404)
