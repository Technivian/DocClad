import datetime
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    ContractTemplate,
    Deadline,
    Document,
    DPAApprovalHistoryEntry,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
)
from contracts.services.contract_lifecycle import (
    ContractTransitionError,
    get_contract_lifecycle_service,
)


User = get_user_model()


class MVPVerticalSliceTests(TestCase):
    password = 'MVP-test-pass!2026'

    def setUp(self):
        self.org = Organization.objects.create(name='MVP Workspace', slug='mvp-workspace')
        self.admin = User.objects.create_user('mvp_test_admin', password=self.password)
        self.owner = User.objects.create_user('mvp_test_owner', password=self.password)
        self.reviewer = User.objects.create_user('mvp_test_reviewer', password=self.password)
        for user, role in (
            (self.admin, OrganizationMembership.Role.OWNER),
            (self.owner, OrganizationMembership.Role.MEMBER),
            (self.reviewer, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.template = ContractTemplate.objects.create(
            name='Approved MVP NDA',
            contract_type=Contract.ContractType.NDA,
            body='APPROVED NDA TEMPLATE BODY',
            is_active=True,
        )

    def contract_form_data(self, **overrides):
        data = {
            'title': 'Acme Mutual NDA',
            'contract_type': Contract.ContractType.NDA,
            'content': self.template.body,
            'status': Contract.Status.IN_PROGRESS,
            'counterparty': 'Acme B.V.',
            'owner': self.owner.pk,
            'value': '125000.00',
            'currency': Contract.Currency.EUR,
            'governing_law': 'The Netherlands',
            'jurisdiction': 'Amsterdam',
            'language': 'English',
            'risk_level': Contract.RiskLevel.LOW,
            'lifecycle_stage': 'DRAFTING',
            'start_date': '2026-08-01',
            'end_date': '2027-08-01',
            'notice_period_days': '30',
        }
        data.update(overrides)
        return data

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=self.password))

    def prepare_contract_for_submit(self, contract, actor):
        if not contract.documents.filter(is_deleted=False).exists():
            Document.objects.create(
                organization=self.org,
                title=f'{contract.title} source',
                document_type=Document.DocType.CONTRACT,
                version=1,
                contract=contract,
                uploaded_by=actor,
                file=SimpleUploadedFile('source.txt', b'agreement body', content_type='text/plain'),
            )
        self.client.post(
            reverse('contracts:contract_ai_assistant', args=[contract.pk]),
            data='{"prompt": "ready for review"}',
            content_type='application/json',
        )

    def test_required_acceptance_journey_updates_every_persisted_surface(self):
        self.login(self.owner)

        picker = self.client.get(
            reverse('contracts:contract_create') + f'?template={self.template.pk}'
        )
        self.assertEqual(picker.status_code, 200)
        self.assertContains(picker, self.template.body)

        create = self.client.post(
            reverse('contracts:contract_create') + f'?template={self.template.pk}',
            self.contract_form_data(),
        )
        self.assertEqual(create.status_code, 302)
        contract = Contract.objects.get(title='Acme Mutual NDA')
        self.assertEqual(contract.organization, self.org)
        self.assertEqual(contract.owner, self.owner)
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.content, self.template.body)

        repository = self.client.get(
            reverse('contracts:contracts_api'),
            {'q': 'Acme Mutual', 'status': Contract.Status.IN_PROGRESS, 'sort': 'title'},
        )
        self.assertEqual(repository.status_code, 200)
        self.assertEqual(repository.json()['total_count'], 1)
        self.assertEqual(repository.json()['contracts'][0]['id'], str(contract.pk))
        self.assertEqual(self.client.get(reverse('contracts:contract_detail', args=[contract.pk])).status_code, 200)

        self.prepare_contract_for_submit(contract, self.owner)
        submitted = self.client.post(
            reverse('contracts:contract_submit_for_review', args=[contract.pk]),
            {'reviewer_id': self.reviewer.pk, 'comment': 'Please check confidentiality scope.'},
        )
        self.assertEqual(submitted.status_code, 302)
        first_approval = ApprovalRequest.objects.get(contract=contract)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.APPROVAL)
        self.assertEqual(first_approval.assigned_to, self.reviewer)

        forbidden = self.client.post(
            reverse('contracts:approval_request_changes_api', args=[first_approval.pk]),
            data=json.dumps({'comments': 'Owner cannot review own agreement.'}),
            content_type='application/json',
        )
        self.assertEqual(forbidden.status_code, 403)

        self.login(self.reviewer)
        changes = self.client.post(
            reverse(
                'contracts:contract_approval_decision',
                args=[contract.pk, first_approval.pk, 'request-changes'],
            ),
            {'comment': 'Narrow the residual confidentiality period.'},
        )
        self.assertEqual(changes.status_code, 302)
        contract.refresh_from_db()
        first_approval.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.DRAFTING)
        self.assertEqual(first_approval.status, ApprovalRequest.Status.CHANGES_REQUESTED)

        self.login(self.owner)
        self.prepare_contract_for_submit(contract, self.owner)
        resubmitted = self.client.post(
            reverse('contracts:contract_submit_for_review', args=[contract.pk]),
            {'reviewer_id': self.reviewer.pk, 'comment': 'Updated to a two-year residual period.'},
        )
        self.assertEqual(resubmitted.status_code, 302)
        second_approval = ApprovalRequest.objects.filter(contract=contract).latest('created_at')

        self.login(self.reviewer)
        approved = self.client.post(
            reverse(
                'contracts:contract_approval_decision',
                args=[contract.pk, second_approval.pk, 'approve'],
            ),
            {'comment': 'Approved after requested amendment.'},
        )
        self.assertEqual(approved.status_code, 302)
        contract.refresh_from_db()
        second_approval.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.SIGNATURE)
        self.assertEqual(contract.approved_by, self.reviewer)
        self.assertEqual(second_approval.status, ApprovalRequest.Status.APPROVED)

        self.login(self.owner)
        deadline_create = self.client.post(reverse('contracts:deadline_create'), {
            'title': 'Destroy confidential material',
            'description': 'Confirm deletion at contract expiry.',
            'deadline_type': Deadline.DeadlineType.CONTRACT,
            'priority': Deadline.Priority.HIGH,
            'due_date': '2027-08-01',
            'reminder_days': '30',
            'contract': contract.pk,
            'assigned_to': self.owner.pk,
        })
        self.assertEqual(deadline_create.status_code, 302)
        obligation = Deadline.objects.get(contract=contract, title='Destroy confidential material')
        edited = self.client.post(reverse('contracts:deadline_update', args=[obligation.pk]), {
            'title': 'Destroy confidential material',
            'description': 'Confirm deletion and written certification at contract expiry.',
            'deadline_type': Deadline.DeadlineType.CONTRACT,
            'priority': Deadline.Priority.CRITICAL,
            'due_date': '2027-08-01',
            'due_time': '',
            'reminder_days': '45',
            'matter': '',
            'contract': contract.pk,
            'assigned_to': self.owner.pk,
        })
        self.assertEqual(edited.status_code, 302)
        obligation.refresh_from_db()
        self.assertEqual(obligation.priority, Deadline.Priority.CRITICAL)

        disposable = Deadline.objects.create(
            contract=contract,
            title='Disposable checkpoint',
            deadline_type=Deadline.DeadlineType.INTERNAL,
            due_date=datetime.date(2027, 7, 1),
            created_by=self.owner,
        )
        deleted = self.client.post(reverse('contracts:deadline_delete', args=[disposable.pk]))
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(Deadline.objects.filter(pk=disposable.pk).exists())

        complete = self.client.post(reverse('contracts:deadline_complete', args=[obligation.pk]))
        self.assertEqual(complete.status_code, 302)
        obligation.refresh_from_db()
        self.assertTrue(obligation.is_completed)
        self.assertEqual(obligation.completed_by, self.owner)

        unlock = self.client.post(
            reverse('contracts:contract_update', args=[contract.pk]),
            {'create_new_version': '1'},
        )
        self.assertEqual(unlock.status_code, 302)
        enable_dpa = self.client.post(
            reverse('contracts:contract_update', args=[contract.pk]),
            self.contract_form_data(dpa_attached='on'),
        )
        self.assertEqual(enable_dpa.status_code, 302)
        pack = DPAReviewPack.objects.get(contract=contract)
        self.assertEqual(pack.reviewer, self.reviewer)

        self.login(self.reviewer)
        risk_response = self.client.post(
            reverse('contracts:dpa_risk_item_create', args=[pack.pk]),
            data=json.dumps({
                'title': 'Subprocessor list unresolved',
                'description': 'The current subprocessor schedule is not attached.',
                'severity': DPARiskItem.Severity.HIGH,
            }),
            content_type='application/json',
        )
        self.assertEqual(risk_response.status_code, 201)
        risk = DPARiskItem.objects.get(pk=risk_response.json()['risk_id'])
        note = self.client.post(
            reverse('contracts:dpa_risk_item_add_note', args=[risk.pk]),
            data=json.dumps({'note': 'Accept only after the schedule is supplied.'}),
            content_type='application/json',
        )
        self.assertEqual(note.status_code, 200)
        under_review = self.client.post(
            reverse('contracts:dpa_review_set_approval_status', args=[pack.pk]),
            data=json.dumps({'status': DPAReviewPack.ApprovalStatus.UNDER_REVIEW, 'comment': 'Privacy review opened.'}),
            content_type='application/json',
        )
        self.assertEqual(under_review.status_code, 200)
        dpa_decision = self.client.post(
            reverse('contracts:dpa_review_set_approval_status', args=[pack.pk]),
            data=json.dumps({'status': DPAReviewPack.ApprovalStatus.APPROVED, 'comment': 'Approved with tracked follow-up.'}),
            content_type='application/json',
        )
        self.assertEqual(dpa_decision.status_code, 200)
        pack.refresh_from_db()
        self.assertEqual(pack.approval_status, DPAReviewPack.ApprovalStatus.APPROVED)
        self.assertEqual(DPAApprovalHistoryEntry.objects.filter(review_pack=pack).count(), 2)

        repository = self.client.get(reverse('contracts:repository'))
        self.assertNotContains(repository, 'Total contracts')
        self.assertNotContains(repository, 'Awaiting action')
        self.assertNotContains(repository, 'Expiring soon')
        self.assertContains(self.client.get(reverse('contracts:obligations_workspace')), 'Destroy confidential material')
        dpa_dashboard = self.client.get(reverse('contracts:dpa_review_pack_list'))
        self.assertEqual(dpa_dashboard.context['total_packs'], 1)
        self.assertEqual(dpa_dashboard.context['pending_approval_count'], 0)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

        contract_activity = self.client.get(reverse('contracts:contract_detail', args=[contract.pk]))
        self.assertGreaterEqual(len(contract_activity.context['activity_entries']), 10)
        events = set(AuditLog.objects.filter(organization=self.org).values_list('changes__event', flat=True))
        self.assertTrue({
            'contract_created',
            'approval.submitted',
            'approval_request_changes_succeeded',
            'approval_approve_succeeded',
            'deadline.created',
            'deadline.updated',
            'deadline.deleted',
            'deadline.completed',
            'dpa.review_enabled',
            'dpa_risk_item.created',
            'dpa_approval_status_changed',
        }.issubset(events))

    def test_uploaded_agreement_creates_contract_document_and_metadata_atomically(self):
        self.login(self.owner)
        response = self.client.post(reverse('contracts:document_upload_api'), {
            'create_contract': '1',
            'title': 'Uploaded Acme Services Agreement',
            'contract_type': Contract.ContractType.MSA,
            'counterparty': 'Acme Inc.',
            'owner_id': self.owner.pk,
            'value': '90000',
            'currency': Contract.Currency.USD,
            'start_date': '2026-09-01',
            'end_date': '2028-09-01',
            'governing_law': 'State of Delaware',
            'file': SimpleUploadedFile('acme.pdf', b'%PDF-1.4 demo agreement', content_type='application/pdf'),
        })
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        contract = Contract.objects.get(pk=payload['contract_id'])
        document = Document.objects.get(pk=payload['document_id'])
        self.assertEqual(document.contract, contract)
        self.assertEqual(contract.owner, self.owner)
        self.assertEqual(contract.counterparty, 'Acme Inc.')
        self.assertEqual(str(contract.value), '90000.00')
        self.assertTrue(document.file_hash)
        self.assertEqual(document.organization, self.org)
        self.assertEqual(
            payload['contract_review_url'],
            reverse('contracts:contract_review_workspace', args=[contract.pk]),
        )

    def test_tenant_authorization_csrf_and_invalid_transition_are_server_enforced(self):
        other_org = Organization.objects.create(name='Other Workspace', slug='other-workspace')
        outsider = User.objects.create_user('mvp_outsider', password=self.password)
        OrganizationMembership.objects.create(
            organization=other_org,
            user=outsider,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        contract = Contract.objects.create(
            organization=self.org,
            title='Tenant Secret',
            contract_type=Contract.ContractType.NDA,
            counterparty='Secret Co',
            owner=self.owner,
            created_by=self.owner,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2027, 1, 1),
            governing_law='The Netherlands',
        )
        self.login(outsider)
        self.assertEqual(self.client.get(reverse('contracts:contract_detail', args=[contract.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse('contracts:contract_submit_for_review', args=[contract.pk]),
                {'reviewer_id': outsider.pk},
            ).status_code,
            404,
        )

        with self.assertRaises(ContractTransitionError):
            get_contract_lifecycle_service().transition(contract, Contract.Status.ACTIVE, self.owner)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.post(
            reverse('contracts:contract_submit_for_review', args=[contract.pk]),
            {'reviewer_id': self.reviewer.pk},
        )
        self.assertEqual(response.status_code, 403)
