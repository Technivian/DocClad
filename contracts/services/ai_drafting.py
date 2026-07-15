"""AI clause drafting service — uses Google Gemini Flash to generate and suggest contract clauses."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types
from django.utils import timezone

from contracts.models import ClauseRecommendation, Contract

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"  # compatibility alias; runtime value comes from settings

def get_drafting_model() -> str:
    from django.conf import settings
    return getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash')

_SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_type": {
                        "type": "string",
                        "description": "Short ALL_CAPS identifier, e.g. GOVERNING_LAW",
                    },
                    "recommendation_text": {
                        "type": "string",
                        "description": "Professionally drafted clause text ready to insert",
                    },
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "rationale": {
                        "type": "string",
                        "description": "One sentence explaining why this clause matters",
                    },
                },
                "required": ["clause_type", "recommendation_text", "confidence", "rationale"],
            },
        }
    },
    "required": ["clauses"],
}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        from django.conf import settings
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


class AIClauseDraftingService:
    def suggest_clauses(self, contract_id: int, org) -> list[ClauseRecommendation]:
        contract = Contract.objects.get(pk=contract_id, organization=org)

        context_parts = [
            f"Contract type: {contract.contract_type}",
            f"Title: {contract.title}",
        ]
        if contract.content:
            context_parts.append(f"Existing content (excerpt):\n{contract.content[:3000]}")
        context = "\n".join(context_parts)

        prompt = (
            "You are a legal drafting assistant. Generate recommended clauses for the following contract.\n\n"
            f"{context}\n\n"
            "Suggest 3-7 essential clauses appropriate for this contract type. "
            "For each clause provide:\n"
            "  clause_type          - a short ALL_CAPS identifier (e.g. GOVERNING_LAW, INDEMNIFICATION)\n"
            "  recommendation_text  - professionally drafted clause text ready to insert verbatim\n"
            "  confidence           - how strongly this clause is recommended (0.7-1.0)\n"
            "  rationale            - one sentence explaining why this clause matters for this contract type\n\n"
            "Do not duplicate clauses that already appear in the existing content."
        )

        response = _get_client().models.generate_content(
            model=get_drafting_model(),
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json'),
        )

        data = json.loads(response.text)
        recommendations: list[ClauseRecommendation] = []

        for item in data.get("clauses", []):
            clause_type = (item.get("clause_type") or "").strip().upper()
            if not clause_type:
                continue
            if ClauseRecommendation.objects.filter(
                contract=contract, clause_type=clause_type
            ).exists():
                continue
            rec = ClauseRecommendation.objects.create(
                contract=contract,
                clause_type=clause_type,
                recommendation_text=item.get("recommendation_text", ""),
                confidence=round(float(item.get("confidence", 0.8)), 4),
                rationale=item.get("rationale", ""),
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
        return list(qs.order_by("-confidence"))

    def generate_draft_section(self, contract_id: int, section: str, org) -> dict:
        contract = Contract.objects.get(pk=contract_id, organization=org)

        prompt = (
            f"You are a legal drafting assistant. Draft the '{section}' section for the following contract.\n\n"
            f"Contract type: {contract.contract_type}\n"
            f"Title: {contract.title}\n\n"
            f"Write a professional, clear '{section}' section appropriate for this {contract.contract_type} agreement. "
            "Output only the section text — no preamble, no commentary, no headings."
        )

        response = _get_client().models.generate_content(
            model=get_drafting_model(),
            contents=prompt,
        )

        draft_text = (
            response.text.strip()
            if response.text
            else f"[{section.upper()} — draft unavailable]"
        )

        return {
            "contract_id": contract_id,
            "section": section,
            "draft_text": draft_text,
            "contract_type": contract.contract_type,
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
        rec.save(update_fields=["accepted", "accepted_by", "accepted_at"])

        contract = rec.contract
        separator = "\n\n---\n\n"
        contract.content = (contract.content or "") + separator + rec.recommendation_text
        contract.save(update_fields=["content", "updated_at"])
        return rec


def get_ai_drafting_service() -> AIClauseDraftingService:
    return AIClauseDraftingService()
