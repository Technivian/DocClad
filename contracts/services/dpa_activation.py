from django.db import transaction

from contracts.middleware import log_action
from contracts.models import ApprovalRequest, AuditLog, Contract, DPAReviewPack


@transaction.atomic
def ensure_dpa_review_pack(contract, actor=None, *, request=None):
    """Create the single persisted DPA review pack when a contract enables DPA review."""
    if not contract.dpa_attached:
        return None, False

    contract = Contract.objects.select_for_update().get(pk=contract.pk)
    latest_reviewer_id = (
        ApprovalRequest.objects.filter(contract=contract)
        .exclude(assigned_to__isnull=True)
        .order_by('-created_at')
        .values_list('assigned_to_id', flat=True)
        .first()
    )
    pack = DPAReviewPack.objects.filter(
        organization=contract.organization,
        contract=contract,
    ).order_by('created_at', 'pk').first()
    created = pack is None
    if created:
        pack = DPAReviewPack.objects.create(
            organization=contract.organization,
            contract=contract,
            created_by=actor if getattr(actor, 'is_authenticated', False) else None,
            reviewer_id=latest_reviewer_id,
        )
    if not created and not pack.reviewer_id and latest_reviewer_id:
        pack.reviewer_id = latest_reviewer_id
        pack.save(update_fields=['reviewer', 'updated_at'])
    if created:
        log_action(
            actor,
            AuditLog.Action.CREATE,
            'DPAReviewPack',
            object_id=pack.pk,
            object_repr=str(pack),
            organization=contract.organization,
            request=request,
            event_type='dpa.review_enabled',
            changes={
                'event': 'dpa.review_enabled',
                'contract_id': contract.pk,
                'previous_state': None,
                'new_state': pack.approval_status,
                'reviewer_id': pack.reviewer_id,
            },
        )
    return pack, created
