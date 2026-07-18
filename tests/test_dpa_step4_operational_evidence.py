from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership


User = get_user_model()


class DpaStep4OperationalEvidenceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Step 4 Evidence', slug='step-4-evidence')
        self.user = User.objects.create_user(username='step4-owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client = Client()
        self.client.login(username='step4-owner', password='testpass123!')
        session = self.client.session
        session['dpa_intake_v1'] = {
            'organization_id': self.organization.pk,
            'step': 4,
            'values': {
                'counterparty': 'Evidence Processor',
                'contract_owner': 'Step Four Owner',
                'start_date': '2026-09-01',
                'processing_purpose': 'Hosted payroll services.',
                'personal_data_categories': 'Contact details',
                'data_subjects': 'Employees',
                'personal_data_involved': True,
                'subprocessors_used': False,
                'cross_border_transfer': False,
                'transfer_mechanism': 'None',
            },
        }
        session.save()

    def _payload(self, **overrides):
        payload = {
            'action': 'continue',
            'step': '4',
            'step4_security_measures_provided': 'yes',
            'step4_security_assurance_available': 'yes',
            'step4_encryption_confirmed': 'yes',
            'step4_access_controls_mfa_confirmed': 'yes',
            'step4_privacy_contact_name': 'Pat Privacy',
            'step4_privacy_contact_role': 'Privacy Officer',
            'step4_privacy_contact_email': 'privacy@example.test',
            'step4_breach_notification_commitment': 'approved_standard',
            'step4_governing_law_mode': 'manual',
            'step4_governing_law': 'Netherlands',
            'step4_audit_rights_position': 'accepted',
            'step4_deletion_return_position': 'accepted',
            'step4_dpa_liability_position': 'accepted',
        }
        payload.update(overrides)
        return payload

    def test_step4_replaces_legacy_legal_authoring_controls(self):
        response = self.client.get(f'{reverse("contracts:dpa_workflow_builder")}?step=4')
        self.assertContains(response, 'Security documentation upload')
        self.assertContains(response, 'Breach-notification commitment')
        self.assertContains(response, 'Standard DPA liability position accepted?')
        self.assertNotContains(response, 'Fallback liability position')
        self.assertNotContains(response, 'Breach notification window (hours)')

    def test_standard_answers_continue_to_review_with_clear_positions(self):
        response = self.client.post(reverse('contracts:dpa_workflow_builder'), self._payload())
        self.assertRedirects(response, reverse('contracts:dpa_workflow_review'))
        facts = self.client.session['dpa_intake_v1']['values']['_dpa_step4']
        self.assertEqual(facts['breach_notification_commitment'], 'approved_standard')
        self.assertTrue(all(item['status'] == 'accepted' for item in facts['positions'].values()))

    def test_deviation_requires_wording_and_derives_legal_review(self):
        payload = self._payload(
            step4_breach_notification_commitment='48_hours',
            step4_audit_rights_position='deviation',
            step4_audit_rights_wording='Processor proposes annual remote-only audit evidence.',
        )
        response = self.client.post(reverse('contracts:dpa_workflow_builder'), payload)
        self.assertRedirects(response, reverse('contracts:dpa_workflow_review'))
        review = self.client.get(reverse('contracts:dpa_workflow_review'))
        self.assertContains(review, 'Breach-notification term deviates from playbook')
        self.assertContains(review, 'Legal review required')

    def test_missing_security_evidence_is_derived_not_authored(self):
        response = self.client.post(reverse('contracts:dpa_workflow_builder'), self._payload(
            step4_security_measures_provided='no',
        ))
        self.assertRedirects(response, reverse('contracts:dpa_workflow_review'))
        review = self.client.get(reverse('contracts:dpa_workflow_review'))
        self.assertContains(review, 'Security evidence missing')
        self.assertContains(review, 'Legal review required')

    def test_uncertain_security_answer_is_derived_not_authored(self):
        response = self.client.post(reverse('contracts:dpa_workflow_builder'), self._payload(
            step4_encryption_confirmed='not_sure',
        ))
        self.assertRedirects(response, reverse('contracts:dpa_workflow_review'))
        review = self.client.get(reverse('contracts:dpa_workflow_review'))
        self.assertContains(review, 'Security evidence missing')
        self.assertContains(review, 'Legal review required')
