"""Tests for AI-assisted clause drafting service and API."""
import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.utils import timezone


def _make_contract(id=1, contract_type='NDA', org=None):
    c = MagicMock()
    c.pk = id
    c.contract_type = contract_type
    c.title = 'Test NDA'
    c.content = ''
    c.organization = org or MagicMock()
    return c


def _make_rec(id=1, clause_type='CONFIDENTIALITY', accepted=False, confidence=0.9,
              accepted_by=None, accepted_at=None, created_at=None):
    r = MagicMock()
    r.pk = id
    r.clause_type = clause_type
    r.recommendation_text = 'Sample clause text.'
    r.confidence = confidence
    r.rationale = 'Test rationale.'
    r.accepted = accepted
    r.accepted_by = accepted_by
    r.accepted_at = accepted_at
    r.created_at = created_at
    return r


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestAIClauseDraftingService(SimpleTestCase):

    @patch('contracts.services.ai_drafting.Contract')
    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_suggest_clauses_nda_creates_recommendations(self, MockRec, MockContract):
        org = MagicMock()
        contract = _make_contract(contract_type='NDA')
        MockContract.objects.get.return_value = contract
        MockRec.objects.filter.return_value.exists.return_value = False
        MockRec.objects.create.return_value = _make_rec()
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.suggest_clauses(1, org)
        # NDA has 3 type-specific + defaults = multiple clauses
        self.assertGreater(MockRec.objects.create.call_count, 0)

    @patch('contracts.services.ai_drafting.Contract')
    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_suggest_clauses_skips_existing(self, MockRec, MockContract):
        org = MagicMock()
        contract = _make_contract(contract_type='NDA')
        MockContract.objects.get.return_value = contract
        MockRec.objects.filter.return_value.exists.return_value = True  # all exist
        MockRec.objects.create.return_value = _make_rec()
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.suggest_clauses(1, org)
        MockRec.objects.create.assert_not_called()
        self.assertEqual(result, [])

    @patch('contracts.services.ai_drafting.Contract')
    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_suggest_clauses_uses_defaults_for_unknown_type(self, MockRec, MockContract):
        org = MagicMock()
        contract = _make_contract(contract_type='OTHER')
        MockContract.objects.get.return_value = contract
        MockRec.objects.filter.return_value.exists.return_value = False
        MockRec.objects.create.return_value = _make_rec()
        from contracts.services.ai_drafting import AIClauseDraftingService, _DEFAULT_CLAUSES
        svc = AIClauseDraftingService()
        svc.suggest_clauses(1, org)
        # Should create at least the default clauses
        self.assertGreaterEqual(MockRec.objects.create.call_count, len(_DEFAULT_CLAUSES))

    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_list_recommendations(self, MockRec):
        org = MagicMock()
        recs = [_make_rec(id=1), _make_rec(id=2)]
        MockRec.objects.filter.return_value.order_by.return_value = recs
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.list_recommendations(1, org)
        self.assertEqual(result, recs)

    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_list_recommendations_accepted_only(self, MockRec):
        org = MagicMock()
        MockRec.objects.filter.return_value.filter.return_value.order_by.return_value = []
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        svc.list_recommendations(1, org, accepted_only=True)
        MockRec.objects.filter.return_value.filter.assert_called_once_with(accepted=True)

    @patch('contracts.services.ai_drafting.Contract')
    def test_generate_draft_section_nda_recitals(self, MockContract):
        org = MagicMock()
        contract = _make_contract(contract_type='NDA')
        MockContract.objects.get.return_value = contract
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.generate_draft_section(1, 'recitals', org)
        self.assertEqual(result['section'], 'recitals')
        self.assertIn('WHEREAS', result['draft_text'])

    @patch('contracts.services.ai_drafting.Contract')
    def test_generate_draft_section_unknown_section_returns_placeholder(self, MockContract):
        org = MagicMock()
        contract = _make_contract(contract_type='NDA')
        MockContract.objects.get.return_value = contract
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.generate_draft_section(1, 'nonexistent_section', org)
        self.assertIn('nonexistent_section'.upper(), result['draft_text'])

    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    @patch('contracts.services.ai_drafting.timezone')
    def test_accept_clause_marks_accepted(self, mock_tz, MockRec):
        org = MagicMock()
        rec = _make_rec(id=1, accepted=False)
        rec.contract = _make_contract()
        rec.contract.content = ''
        MockRec.objects.get.return_value = rec
        mock_tz.now.return_value = MagicMock()
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        user = MagicMock()
        result = svc.accept_clause(1, 1, user, org)
        self.assertTrue(result.accepted)
        self.assertEqual(result.accepted_by, user)
        rec.save.assert_called_once()
        rec.contract.save.assert_called_once()

    @patch('contracts.services.ai_drafting.ClauseRecommendation')
    def test_accept_clause_idempotent_if_already_accepted(self, MockRec):
        org = MagicMock()
        rec = _make_rec(id=1, accepted=True)
        rec.contract = _make_contract()
        MockRec.objects.get.return_value = rec
        from contracts.services.ai_drafting import AIClauseDraftingService
        svc = AIClauseDraftingService()
        result = svc.accept_clause(1, 1, MagicMock(), org)
        rec.save.assert_not_called()


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class TestAIClauseApi(SimpleTestCase):

    def _req(self, method='GET', body=None, qs=None):
        req = MagicMock()
        req.method = method
        req.body = json.dumps(body).encode() if body else b''
        req.GET = qs or {}
        req.user = MagicMock()
        req.user.is_authenticated = True
        return req

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_ai_drafting_service')
    def test_suggest_clauses_returns_201(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        rec = _make_rec(created_at=None, accepted_by=None, accepted_at=None)
        mock_svc = MagicMock()
        mock_svc.suggest_clauses.return_value = [rec]
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import ai_suggest_clauses_api
        resp = ai_suggest_clauses_api(self._req(method='POST'), contract_id=1)
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertEqual(data['created'], 1)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_ai_drafting_service')
    def test_list_recommendations(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        rec = _make_rec(created_at=None, accepted_by=None, accepted_at=None)
        mock_svc = MagicMock()
        mock_svc.list_recommendations.return_value = [rec]
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import ai_clause_recommendations_api
        resp = ai_clause_recommendations_api(self._req(), contract_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['recommendations']), 1)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_ai_drafting_service')
    @patch('contracts.api.views.ClauseRecommendation')
    def test_accept_clause(self, MockRec, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        rec = _make_rec(id=1, accepted=True, created_at=None, accepted_by=None, accepted_at=None)
        mock_svc = MagicMock()
        mock_svc.accept_clause.return_value = rec
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import ai_accept_clause_api
        resp = ai_accept_clause_api(self._req(method='POST'), contract_id=1, recommendation_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertTrue(data['recommendation']['accepted'])

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_ai_drafting_service')
    def test_draft_section(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        mock_svc = MagicMock()
        mock_svc.generate_draft_section.return_value = {
            'contract_id': 1, 'section': 'recitals',
            'draft_text': 'WHEREAS ...', 'contract_type': 'NDA',
        }
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import ai_draft_section_api
        resp = ai_draft_section_api(self._req(method='POST', body={'section': 'recitals'}), contract_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['section'], 'recitals')
