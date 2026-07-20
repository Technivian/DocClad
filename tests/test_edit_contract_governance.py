"""Regression coverage for Edit contract details governance UX."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Contract, ContractVersion, Organization, OrganizationMembership
from contracts.services.contract_edit_governance import (
    GOVERNED_CHANGE_WARNING,
    contract_is_governance_locked,
    risk_state_for_contract,
)


User = get_user_model()


class EditContractGovernanceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='edit-owner', password='testpass123')
        self.org = Organization.objects.create(name='Edit Org', slug='edit-org', require_mfa=False)
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client.login(username='edit-owner', password='testpass123')
        self.draft = Contract.objects.create(
            organization=self.org,
            title='Draft MSA',
            contract_type=Contract.ContractType.MSA,
            counterparty='Acme',
            content='body',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage='DRAFTING',
            owner=self.user,
            created_by=self.user,
            risk_level=Contract.RiskLevel.LOW,
        )
        self.approved = Contract.objects.create(
            organization=self.org,
            title='Approved MSA',
            contract_type=Contract.ContractType.MSA,
            counterparty='Northstar',
            content='approved body',
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            owner=self.user,
            created_by=self.user,
            risk_level=Contract.RiskLevel.MEDIUM,
            value=120000,
            governing_law='Delaware',
            jurisdiction='Delaware',
        )

    def _form_data(self, contract, **overrides):
        data = {
            'title': contract.title,
            'contract_type': contract.contract_type,
            'counterparty': contract.counterparty,
            'content': contract.content,
            'owner': contract.owner_id,
            'governing_law': contract.governing_law or 'Delaware',
            'jurisdiction': contract.jurisdiction or 'Delaware',
            'currency': contract.currency or Contract.Currency.USD,
            'value': contract.value or '',
            'language': contract.language or 'en',
            'paper_source': contract.paper_source or '',
        }
        data.update(overrides)
        return data

    def test_edit_page_renames_and_hides_intake_language(self):
        response = self.client.get(reverse('contracts:contract_update', args=[self.approved.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Edit contract details', content)
        self.assertIn('Save changes', content)
        self.assertNotIn('Contract intake', content)
        self.assertNotIn('Required to create', content)
        self.assertNotIn('Save draft', content)
        self.assertNotIn('>Readiness<', content)
        self.assertNotIn('Required now', content)
        self.assertNotIn('Risk not assessed', content)
        self.assertTrue(response.context['hide_app_footer'])
        self.assertIn('cform-bottom-actions', content)
        self.assertIn("stickyActions.classList.toggle('is-docked-hidden', topActionsVisible);", content)

    def test_edit_rail_shows_contract_state_and_risk(self):
        response = self.client.get(reverse('contracts:contract_update', args=[self.approved.pk]))
        content = response.content.decode()
        self.assertIn('Contract state', content)
        self.assertIn('Current stage', content)
        self.assertIn('Change impact', content)
        self.assertIn('Risk reassessment', content)
        self.assertIn('Approval impact', content)
        self.assertIn('Validation issues', content)
        self.assertIn('Medium risk', content)
        self.assertIn('Create new version', content)
        self.assertIn('Create amendment', content)

    def test_approved_record_locks_governed_fields(self):
        self.assertTrue(contract_is_governance_locked(self.approved))
        response = self.client.get(reverse('contracts:contract_update', args=[self.approved.pk]))
        form = response.context['form']
        self.assertTrue(form.governed_fields_readonly)
        self.assertTrue(form.fields['contract_type'].disabled)
        self.assertTrue(form.fields['counterparty'].disabled)
        self.assertFalse(form.fields['owner'].disabled)
        self.assertFalse(form.fields['title'].disabled)

    def test_metadata_save_does_not_overwrite_governed_fields(self):
        response = self.client.post(
            reverse('contracts:contract_update', args=[self.approved.pk]),
            self._form_data(
                self.approved,
                title='Renamed Approved MSA',
                counterparty='Should Not Stick',
                value='999999',
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.approved.refresh_from_db()
        self.assertEqual(self.approved.title, 'Renamed Approved MSA')
        self.assertEqual(self.approved.counterparty, 'Northstar')
        self.assertEqual(str(self.approved.value), '120000.00')

    def test_create_new_version_unlocks_revision(self):
        response = self.client.post(
            reverse('contracts:contract_update', args=[self.approved.pk]),
            {'create_new_version': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContractVersion.objects.filter(contract=self.approved).count(), 1)
        unlocked = self.client.get(reverse('contracts:contract_update', args=[self.approved.pk]))
        self.assertFalse(unlocked.context['form'].governed_fields_readonly)
        self.assertContains(unlocked, GOVERNED_CHANGE_WARNING)

    def test_draft_edit_still_allows_in_place_governed_changes(self):
        response = self.client.post(
            reverse('contracts:contract_update', args=[self.draft.pk]),
            self._form_data(self.draft, counterparty='Updated Co', governing_law='England'),
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.counterparty, 'Updated Co')
        self.assertEqual(self.draft.governing_law, 'England')

    def test_risk_state_vocabulary(self):
        incomplete = Contract.objects.create(
            organization=self.org,
            title='No risk',
            contract_type=Contract.ContractType.NDA,
            counterparty='X',
            content='c',
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.EXECUTED,
            owner=self.user,
            created_by=self.user,
            risk_level='',
        )
        state = risk_state_for_contract(incomplete)
        self.assertEqual(state['key'], 'reassessment_required')
        self.assertEqual(state['label'], 'Risk reassessment required')
        calculated = risk_state_for_contract(self.approved)
        self.assertEqual(calculated['key'], 'calculated')
        self.assertIn('Medium', calculated['label'])
