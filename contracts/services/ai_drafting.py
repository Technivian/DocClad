"""AI-assisted clause drafting service.

Uses a deterministic template library keyed on contract_type and clause_type —
no external LLM call required. Confidence scores reflect how well a template
matches the contract context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from contracts.models import ClauseRecommendation, Contract

# ---------------------------------------------------------------------------
# Template library
# ---------------------------------------------------------------------------

_CLAUSE_TEMPLATES: dict[str, dict[str, dict]] = {
    'NDA': {
        'CONFIDENTIALITY': {
            'text': (
                'Each party agrees to hold the other party\'s Confidential Information in strict '
                'confidence and not to disclose it to any third party without prior written consent. '
                'This obligation survives termination of this Agreement for a period of five (5) years.'
            ),
            'confidence': 0.95,
            'rationale': 'Standard NDA confidentiality clause with 5-year survival period.',
        },
        'GOVERNING_LAW': {
            'text': (
                'This Agreement shall be governed by and construed in accordance with the laws of '
                'the State of Delaware, without regard to its conflict of laws provisions.'
            ),
            'confidence': 0.85,
            'rationale': 'Delaware is a common governing law choice for commercial agreements.',
        },
        'TERMINATION': {
            'text': (
                'Either party may terminate this Agreement upon thirty (30) days written notice to '
                'the other party. Obligations of confidentiality shall survive termination.'
            ),
            'confidence': 0.90,
            'rationale': 'Standard 30-day termination notice with confidentiality survival.',
        },
    },
    'MSA': {
        'LIMITATION_OF_LIABILITY': {
            'text': (
                'In no event shall either party be liable for indirect, incidental, special, '
                'consequential, or punitive damages. Each party\'s total aggregate liability shall '
                'not exceed the fees paid in the twelve (12) months preceding the claim.'
            ),
            'confidence': 0.92,
            'rationale': 'Standard MSA liability cap tied to fees paid.',
        },
        'INDEMNIFICATION': {
            'text': (
                'Each party ("Indemnifying Party") shall defend, indemnify, and hold harmless the '
                'other party from and against any claims, damages, and expenses arising from the '
                'Indemnifying Party\'s breach of this Agreement or gross negligence.'
            ),
            'confidence': 0.88,
            'rationale': 'Mutual indemnification for breach and gross negligence.',
        },
        'DATA_PROTECTION': {
            'text': (
                'Each party shall comply with applicable data protection laws, including the GDPR '
                'where applicable. Processor obligations and data processing details shall be set '
                'forth in a separate Data Processing Agreement.'
            ),
            'confidence': 0.90,
            'rationale': 'GDPR-aligned data protection clause requiring a separate DPA.',
        },
        'PAYMENT_TERMS': {
            'text': (
                'Invoices are due and payable within thirty (30) days of invoice date. '
                'Late payments shall accrue interest at 1.5% per month on the outstanding balance.'
            ),
            'confidence': 0.85,
            'rationale': 'Net-30 payment terms with standard late-payment interest.',
        },
    },
    'EMPLOYMENT': {
        'CONFIDENTIALITY': {
            'text': (
                'Employee agrees to keep all proprietary information, trade secrets, and business '
                'strategies of the Employer strictly confidential during and after employment, '
                'for a period of three (3) years post-termination.'
            ),
            'confidence': 0.93,
            'rationale': 'Employee confidentiality with 3-year post-termination obligation.',
        },
        'IP_OWNERSHIP': {
            'text': (
                'All inventions, works of authorship, and developments created by Employee in the '
                'scope of employment shall be the sole property of the Employer. Employee hereby '
                'assigns all intellectual property rights therein to Employer.'
            ),
            'confidence': 0.90,
            'rationale': 'Standard work-for-hire IP assignment clause.',
        },
    },
    'VENDOR': {
        'LIMITATION_OF_LIABILITY': {
            'text': (
                'Vendor\'s total liability under this Agreement shall not exceed the amount paid '
                'by Client in the three (3) months preceding the event giving rise to the claim. '
                'Vendor shall not be liable for any indirect or consequential damages.'
            ),
            'confidence': 0.88,
            'rationale': 'Vendor liability cap capped at 3 months fees.',
        },
        'FORCE_MAJEURE': {
            'text': (
                'Neither party shall be liable for delays or failure to perform due to causes '
                'beyond its reasonable control, including acts of God, natural disasters, pandemic, '
                'government action, or failure of third-party suppliers.'
            ),
            'confidence': 0.87,
            'rationale': 'Standard force majeure clause covering common uncontrollable events.',
        },
    },
}

_DEFAULT_CLAUSES: dict[str, dict] = {
    'GOVERNING_LAW': {
        'text': (
            'This Agreement shall be governed by the laws of the applicable jurisdiction, without '
            'regard to conflicts of law principles.'
        ),
        'confidence': 0.70,
        'rationale': 'Generic governing law placeholder — specify jurisdiction.',
    },
    'DISPUTE_RESOLUTION': {
        'text': (
            'Any disputes arising under this Agreement shall be resolved through binding '
            'arbitration under the rules of the American Arbitration Association.'
        ),
        'confidence': 0.72,
        'rationale': 'AAA arbitration as dispute resolution mechanism.',
    },
    'WARRANTY': {
        'text': (
            'Each party represents and warrants that it has the full right, power, and authority '
            'to enter into and perform this Agreement.'
        ),
        'confidence': 0.80,
        'rationale': 'Standard authority and capacity warranty.',
    },
}

_SECTION_DRAFTS: dict[str, dict[str, str]] = {
    'NDA': {
        'recitals': (
            'WHEREAS, the parties wish to explore a potential business relationship and, in '
            'connection therewith, may disclose confidential information to each other;\n\n'
            'NOW, THEREFORE, in consideration of the mutual covenants herein, the parties agree as follows:'
        ),
        'definitions': (
            '"Confidential Information" means any non-public information disclosed by one party to '
            'the other, whether oral, written, or electronic, that is designated as confidential '
            'or that reasonably should be understood to be confidential given the context.'
        ),
    },
    'MSA': {
        'recitals': (
            'WHEREAS, Client wishes to obtain certain services from Provider, and Provider '
            'wishes to provide such services, subject to the terms and conditions set forth herein;\n\n'
            'NOW, THEREFORE, the parties agree as follows:'
        ),
        'definitions': (
            '"Services" means the professional services described in one or more Statements of '
            'Work executed under this Agreement.\n'
            '"Deliverables" means any work product created by Provider specifically for Client.\n'
            '"Confidential Information" means non-public business, technical, or financial information.'
        ),
    },
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AIClauseDraftingService:
    def suggest_clauses(
        self, contract_id: int, org
    ) -> list[ClauseRecommendation]:
        contract = Contract.objects.get(pk=contract_id, organization=org)
        contract_type = contract.contract_type
        type_templates = _CLAUSE_TEMPLATES.get(contract_type, {})

        # Merge type-specific + default clauses (type-specific wins)
        all_templates = {**_DEFAULT_CLAUSES, **type_templates}

        recommendations = []
        for clause_type, tmpl in all_templates.items():
            # Skip if recommendation already exists
            if ClauseRecommendation.objects.filter(
                contract=contract, clause_type=clause_type
            ).exists():
                continue
            rec = ClauseRecommendation.objects.create(
                contract=contract,
                clause_type=clause_type,
                recommendation_text=tmpl['text'],
                confidence=tmpl['confidence'],
                rationale=tmpl.get('rationale', ''),
            )
            recommendations.append(rec)
        return recommendations

    def list_recommendations(
        self, contract_id: int, org, accepted_only: bool = False
    ) -> list[ClauseRecommendation]:
        qs = ClauseRecommendation.objects.filter(
            contract_id=contract_id, contract__organization=org
        )
        if accepted_only:
            qs = qs.filter(accepted=True)
        return list(qs.order_by('-confidence'))

    def generate_draft_section(
        self, contract_id: int, section: str, org
    ) -> dict:
        contract = Contract.objects.get(pk=contract_id, organization=org)
        type_drafts = _SECTION_DRAFTS.get(contract.contract_type, {})
        fallback_drafts = _SECTION_DRAFTS.get('MSA', {})
        text = type_drafts.get(section) or fallback_drafts.get(section) or (
            f'[{section.upper()} — Customise this section for {contract.contract_type} agreements.]'
        )
        return {
            'contract_id': contract_id,
            'section': section,
            'draft_text': text,
            'contract_type': contract.contract_type,
        }

    def accept_clause(
        self, contract_id: int, recommendation_id: int, user, org
    ) -> ClauseRecommendation:
        rec = ClauseRecommendation.objects.get(
            pk=recommendation_id,
            contract_id=contract_id,
            contract__organization=org,
        )
        if rec.accepted:
            return rec
        rec.accepted = True
        rec.accepted_by = user
        rec.accepted_at = timezone.now()
        rec.save(update_fields=['accepted', 'accepted_by', 'accepted_at'])

        # Append clause text to contract content
        contract = rec.contract
        separator = '\n\n---\n\n'
        contract.content = (contract.content or '') + separator + rec.recommendation_text
        contract.save(update_fields=['content', 'updated_at'])
        return rec


def get_ai_drafting_service() -> AIClauseDraftingService:
    return AIClauseDraftingService()
