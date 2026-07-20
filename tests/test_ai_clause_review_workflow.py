import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    AIExtractionSpan,
    AuditLog,
    ClauseTemplate,
    ClausePlaybook,
    Contract,
    ContractReviewFinding,
    Document,
    DocumentOCRReview,
    DocumentReviewRun,
    Organization,
    OrganizationMembership,
    OrgPolicy,
)


User = get_user_model()


def provider_client(payload):
    response = MagicMock()
    response.text = json.dumps(payload) if not isinstance(payload, str) else payload
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


@override_settings(
    GEMINI_AI_ENABLED=True,
    GEMINI_API_KEY='test-provider-key',
    GEMINI_MODEL='gemini-3.5-flash',
)
class AIClauseReviewWorkflowTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='AI Review Org', slug='ai-review-org')
        self.other_organization = Organization.objects.create(name='Other Org', slug='other-ai-org')
        self.reviewer = User.objects.create_user(
            username='ai_reviewer', password='testpass123', first_name='Riley', last_name='Reviewer',
        )
        self.outsider = User.objects.create_user(username='ai_outsider', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.reviewer,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.outsider,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        OrgPolicy.objects.create(organization=self.organization, ai_features_enabled=True)
        OrgPolicy.objects.create(organization=self.other_organization, ai_features_enabled=True)
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='Supplier agreement',
            contract_type=Contract.ContractType.VENDOR,
            status=Contract.Status.IN_PROGRESS,
            created_by=self.reviewer,
            owner=self.reviewer,
        )
        self.document = Document.objects.create(
            organization=self.organization,
            contract=self.contract,
            title='Supplier agreement.txt',
            document_type=Document.DocType.CONTRACT,
            uploaded_by=self.reviewer,
        )
        self.text = (
            'Governing Law. This agreement is governed by the laws of the Netherlands. '
            'Either party may terminate on thirty days written notice.'
        )
        DocumentOCRReview.objects.create(
            organization=self.organization,
            document=self.document,
            status=DocumentOCRReview.Status.VERIFIED,
            extracted_text=self.text,
            confidence_score='99.00',
            source='text-extraction',
        )
        self.approved_clause = ClauseTemplate.objects.create(
            organization=self.organization,
            title='Governing Law',
            content='This agreement is governed by the laws of the Netherlands.',
            fallback_content='The agreement is governed by Dutch law.',
            playbook_notes='Use the approved jurisdiction unless Legal signs off.',
            applicable_contract_types=Contract.ContractType.VENDOR,
            is_approved=True,
            approved_by=self.reviewer,
        )
        ClauseTemplate.objects.create(
            organization=self.other_organization,
            title='Governing Law - foreign tenant',
            content='Foreign tenant content.',
            is_approved=True,
            approved_by=self.outsider,
        )
        self.client.login(username='ai_reviewer', password='testpass123')
        self.url = reverse('contracts:contract_ai_extract_api', args=[self.contract.pk])

    @patch('contracts.services.ai_extraction._get_client')
    def test_explicit_post_extracts_verbatim_grounded_citation_and_audits(self, get_client):
        get_client.return_value = provider_client({
            'spans': [{
                'label': 'governing_law',
                'text': 'This agreement is governed by the laws of the Netherlands.',
                'confidence': 0.96,
                'risk_level': 'CLEAR',
                'rationale': 'The agreement specifies a governing jurisdiction.',
            }],
        })

        response = self.client.post(self.url, data='{}', content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['created'], 1)
        span = AIExtractionSpan.objects.get(document=self.document)
        self.assertEqual(span.span_text, 'This agreement is governed by the laws of the Netherlands.')
        self.assertEqual(span.source_template, self.approved_clause)
        self.assertEqual(span.organization, self.organization)
        self.assertEqual(span.extraction_model, 'gemini-3.5-flash')
        self.assertTrue(AuditLog.objects.filter(
            organization=self.organization,
            event_type='ai.clauses_extracted',
            object_id=self.contract.pk,
        ).exists())
        config = get_client.return_value.models.generate_content.call_args.kwargs['config']
        self.assertIsNotNone(config.response_schema)

    @patch('contracts.services.ai_extraction._get_client')
    def test_get_is_read_only_and_never_calls_provider(self, get_client):
        AIExtractionSpan.objects.create(
            document=self.document,
            organization=self.organization,
            label='termination',
            span_text='Either party may terminate on thirty days written notice.',
            start_char=self.text.index('Either party'),
            end_char=len(self.text),
            confidence='0.9100',
            extraction_model='gemini-3.5-flash',
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['spans']['span_count'], 1)
        get_client.assert_not_called()

    @patch('contracts.services.ai_extraction._get_client')
    def test_malformed_provider_response_preserves_previous_citations(self, get_client):
        existing = AIExtractionSpan.objects.create(
            document=self.document,
            organization=self.organization,
            label='termination',
            span_text='Either party may terminate on thirty days written notice.',
            start_char=self.text.index('Either party'),
            end_char=len(self.text),
            confidence='0.9100',
            extraction_model='gemini-3.5-flash',
        )
        get_client.return_value = provider_client('not-json')

        response = self.client.post(self.url, data='{}', content_type='application/json')

        self.assertEqual(response.status_code, 502)
        self.assertTrue(AIExtractionSpan.objects.filter(pk=existing.pk).exists())
        audit = AuditLog.objects.get(event_type='ai.clauses_extracted')
        self.assertEqual(audit.outcome, AuditLog.Outcome.FAILURE)

    def test_cross_tenant_contract_is_not_disclosed(self):
        self.client.logout()
        self.client.login(username='ai_outsider', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_workspace_policy_blocks_provider_call(self):
        policy = self.organization.policy
        policy.ai_features_enabled = False
        policy.save(update_fields=['ai_features_enabled'])
        with patch('contracts.services.ai_extraction._get_client') as get_client:
            response = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        get_client.assert_not_called()

    @override_settings(GEMINI_AI_ENABLED=False, GEMINI_API_KEY='')
    def test_unconfigured_provider_returns_actionable_service_state(self):
        response = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', response.json()['error'])

    def test_reviewer_can_confirm_citation_and_audit_is_immutable_evidence(self):
        span = AIExtractionSpan.objects.create(
            document=self.document,
            organization=self.organization,
            label='termination',
            span_text='Either party may terminate on thirty days written notice.',
            start_char=self.text.index('Either party'),
            end_char=len(self.text),
            confidence='0.9100',
            extraction_model='gemini-3.5-flash',
        )
        review_url = reverse(
            'contracts:ai_extraction_span_review_api', args=[self.contract.pk, span.pk],
        )

        response = self.client.post(
            review_url,
            data=json.dumps({'status': 'CONFIRMED'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        span.refresh_from_db()
        self.assertEqual(span.review_status, AIExtractionSpan.ReviewStatus.CONFIRMED)
        self.assertEqual(span.reviewed_by, self.reviewer)
        audit = AuditLog.objects.get(event_type='ai.clause_reviewed')
        self.assertEqual(audit.changes['previous_status'], 'PENDING')
        self.assertEqual(audit.changes['new_status'], 'CONFIRMED')

    def test_csrf_is_enforced_for_extraction(self):
        csrf_client = TestClient(enforce_csrf_checks=True)
        csrf_client.login(username='ai_reviewer', password='testpass123')
        response = csrf_client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_contract_workspace_exposes_governed_review_state(self):
        # Intentional product change (tabbed contract workspace): review copy lives
        # on ?tab=review. Assert current governed copy, not retired "AI-assisted" label.
        detail = reverse('contracts:contract_detail', args=[self.contract.pk])
        response = self.client.get(f'{detail}?tab=review')
        self.assertContains(response, 'Contract review')
        self.assertContains(response, 'subject to human review')
        self.assertContains(response, 'Open review workspace')
        self.assertContains(response, reverse('contracts:contract_review_workspace', args=[self.contract.pk]))

    def test_review_workspace_and_finding_actions_are_human_governed(self):
        span = AIExtractionSpan.objects.create(
            document=self.document,
            organization=self.organization,
            label='termination',
            span_text='Either party may terminate on thirty days written notice.',
            start_char=self.text.index('Either party'),
            end_char=len(self.text),
            confidence='0.9100',
            extraction_model='gemini-3.5-flash',
            risk_level=AIExtractionSpan.RiskLevel.RISK,
        )
        run = DocumentReviewRun.objects.create(
            organization=self.organization,
            contract=self.contract,
            document=self.document,
            status=DocumentReviewRun.Status.READY,
            current_step='Review ready',
            progress_steps=[{'label': 'Review ready', 'status': 'active'}],
            governance_sources={'message': 'No approved playbook matched. This review uses general analysis and requires full human review.'},
        )
        finding = ContractReviewFinding.objects.create(
            review_run=run,
            contract=self.contract,
            document=self.document,
            source_span=span,
            title='AI review — termination needs review',
            severity=ContractReviewFinding.Severity.HIGH,
            source_clause='Termination',
            source_excerpt=span.span_text,
            explanation='The notice period needs human review.',
            confidence=span.confidence,
            assigned_reviewer=self.reviewer,
        )
        workspace = self.client.get(reverse('contracts:contract_review_workspace', args=[self.contract.pk]))
        self.assertContains(workspace, 'dc-ds-workspace--record')
        self.assertContains(workspace, 'Review workspace')
        self.assertContains(workspace, 'No approved contract playbook matched')
        self.assertContains(workspace, span.span_text)
        self.assertContains(workspace, 'dc-ds-button dc-ds-button--primary')

        action_url = reverse('contracts:contract_review_finding_action_api', args=[self.contract.pk, finding.pk])
        rejected = self.client.post(action_url, data=json.dumps({'action': 'dismiss'}), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        accepted = self.client.post(action_url, data=json.dumps({'action': 'accept'}), content_type='application/json')
        self.assertEqual(accepted.status_code, 200)
        finding.refresh_from_db()
        self.assertEqual(finding.status, ContractReviewFinding.Status.IN_PROGRESS)
        self.assertTrue(AuditLog.objects.filter(event_type='ai.review_finding_updated', object_id=finding.pk).exists())

    def test_incomplete_review_is_truthful_and_surfaces_resolvable_blockers(self):
        self.contract.contract_type = Contract.ContractType.OTHER
        self.contract.counterparty = ''
        self.contract.status = Contract.Status.IN_PROGRESS
        self.contract.lifecycle_stage = Contract.LifecycleStage.INTERNAL_REVIEW
        self.contract.save(update_fields=['contract_type', 'counterparty', 'status', 'lifecycle_stage', 'updated_at'])
        DocumentReviewRun.objects.create(
            organization=self.organization,
            contract=self.contract,
            document=self.document,
            status=DocumentReviewRun.Status.READY,
            current_step='Review ready',
        )

        response = self.client.get(reverse('contracts:contract_review_workspace', args=[self.contract.pk]))

        self.assertContains(response, 'Needs input')
        self.assertContains(response, 'Internal review')
        self.assertContains(response, 'Resolve review blockers')
        self.assertContains(response, 'AI review could not be completed. The document preview failed, no approved playbook was matched and required contract information needs confirmation.')
        self.assertContains(response, 'Document preview unavailable')
        self.assertContains(response, 'Document preview')
        self.assertContains(response, 'Counterparty')
        self.assertContains(response, 'Contract type')
        self.assertContains(response, 'Governing law')
        self.assertContains(response, 'Not yet generated')
        self.assertContains(response, 'Not reviewed. Findings will appear after the review blockers are resolved and AI analysis completes.')
        self.assertContains(response, 'dc-ds-workspace__surface')
        self.assertContains(response, 'dc-ds-workspace__tabs')
        self.assertNotContains(response, 'Critical findings')
        self.assertNotContains(response, 'AI review ready')
        self.assertNotContains(response, 'page-wrap review-workspace')
        self.assertNotContains(response, 'class="review-action')

    def test_clear_review_requires_explicit_human_confirmation_before_approval(self):
        playbook = ClausePlaybook.objects.create(
            organization=self.organization,
            name='Vendor agreement review',
            created_by=self.reviewer,
        )
        self.contract.counterparty = 'Acme Corp'
        self.contract.governing_law = 'Netherlands'
        self.contract.value = '5000.00'
        self.contract.save(update_fields=['counterparty', 'governing_law', 'value', 'updated_at'])
        DocumentReviewRun.objects.create(
            organization=self.organization,
            contract=self.contract,
            document=self.document,
            status=DocumentReviewRun.Status.READY,
            current_step='Review ready',
            extracted_metadata={
                'governing_law_confirmed': True,
                'value_confirmed': True,
                'payment_terms_confirmed': True,
            },
            governance_sources={
                'ai_analysis_completed': True,
                'selected_playbook_id': playbook.pk,
            },
        )
        response = self.client.post(reverse('contracts:contract_review_confirm_api', args=[self.contract.pk]))
        self.assertEqual(response.status_code, 200)
        approval = ApprovalRequest.objects.get(contract=self.contract)
        self.assertEqual(approval.approval_step, 'Human confirmation: AI review outcome')
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(self.contract.lifecycle_stage, Contract.LifecycleStage.APPROVAL)
        self.assertTrue(AuditLog.objects.filter(event_type='ai.review_human_confirmation_requested').exists())
