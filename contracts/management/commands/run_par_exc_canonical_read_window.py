"""Execute the bounded PAR-EXC-001 canonical-read observation in a non-prod DB."""
from __future__ import annotations

import json
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from contracts.models import Contract, Organization, OrganizationMembership
from contracts.services.exception_canonical_read import resolve_canonical_applicability
from contracts.services.exception_dual_write import AUTHORIZED_SOURCES, mirror_legacy_exception


class Command(BaseCommand):
    help = 'Run the six-path, non-production PAR-EXC-001 canonical-read observation.'

    def handle(self, *args, **options):
        if os.getenv('CLMONE_OPERATOR_ENV') != 'par-exc-001-canonical-read-authority':
            raise CommandError('This command is restricted to par-exc-001-canonical-read-authority.')
        if not settings.EXCEPTION_CANONICAL_READ_ENABLED or (
            settings.EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST != 'controlled-pilot-org'
        ):
            raise CommandError('Canonical-read flag and exact allowlist are required.')

        User = get_user_model()
        org, _ = Organization.objects.get_or_create(name='Controlled Pilot', slug='controlled-pilot-org')
        owner, _ = User.objects.get_or_create(username='par-exc-operator')
        OrganizationMembership.objects.get_or_create(
            organization=org, user=owner,
            defaults={'role': OrganizationMembership.Role.OWNER, 'is_active': True},
        )
        contract, _ = Contract.objects.get_or_create(
            organization=org, title='PAR-EXC canonical-read observation',
            defaults={
                'contract_type': Contract.ContractType.MSA,
                'status': Contract.Status.IN_PROGRESS,
                'lifecycle_stage': Contract.LifecycleStage.NEGOTIATION,
                'owner': owner, 'created_by': owner, 'content': 'controlled observation',
            },
        )
        now = timezone.now()
        privileges = {
            'KEEP_EXCEPTION': ['policy.deviation'], 'ACCEPTED_RISK': ['risk.accept'],
            'AI_EXCEPTION': [], 'CONFLICT_CHECK_WAIVER': ['policy.deviation'],
            'DEADLINE_DEFER': ['deadline.extend'],
            'DPA_APPROVE_WITH_BLOCKERS': ['approval.defer_blocker'],
        }
        results = {}
        for index, source in enumerate(sorted(AUTHORIZED_SOURCES), start=1):
            correlation_id = f'{source}:operator:{index}:window'
            outcome = 'NONE' if source == 'AI_EXCEPTION' else 'APPROVED'
            req, _ = mirror_legacy_exception(
                source=source, organization=org, actor=owner, owner=owner,
                title=f'{source} controlled observation', reason='Controlled non-production observation.',
                scope_object_model='OperatorWindow', scope_object_id=index,
                correlation_id=correlation_id, outcome=outcome, contract=contract,
                granted_privileges=privileges[source], starts_at=now,
                expires_at=now + timedelta(days=1),
            )
            resolution = resolve_canonical_applicability(
                organization=org, source=source, correlation_id=correlation_id,
                legacy_applicable=True, privilege_token=(privileges[source] or [''])[0], actor=owner,
            )
            results[source] = {
                'correlated': bool(req), 'canonical_used': resolution.canonical_used,
                'applicable': resolution.applicable, 'privilege_granted': resolution.privilege_granted,
                'ai_submitted_without_decision': source == 'AI_EXCEPTION' and not resolution.applicable,
            }
        miss = resolve_canonical_applicability(
            organization=org, source='KEEP_EXCEPTION', correlation_id='KEEP_EXCEPTION:operator:missing',
            legacy_applicable=True, actor=owner,
        )
        self.stdout.write(json.dumps({
            'environment': os.environ['CLMONE_OPERATOR_ENV'],
            'flags_during': {
                'EXCEPTION_CANONICAL_READ_ENABLED': settings.EXCEPTION_CANONICAL_READ_ENABLED,
                'EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST': settings.EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST,
                'EXCEPTION_DUAL_WRITE_ENABLED': settings.EXCEPTION_DUAL_WRITE_ENABLED,
                'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST': settings.EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST,
            },
            'paths': results,
            'legacy_fallback_on_miss': (not miss.canonical_used and miss.applicable),
            'permissions_changed': False,
            'pass': all(v['canonical_used'] for v in results.values()) and results['AI_EXCEPTION']['ai_submitted_without_decision'] and (not miss.canonical_used and miss.applicable),
        }, sort_keys=True))
