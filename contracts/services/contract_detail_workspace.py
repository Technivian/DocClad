"""Contract Detail workspace command model: tabs, review status, action gating."""
from __future__ import annotations

from django.urls import reverse

CONTRACT_DETAIL_TABS = (
    ('overview', 'Overview'),
    ('documents', 'Documents'),
    ('workflow', 'Workflow'),
    ('risks', 'Risks'),
    ('obligations', 'Obligations'),
    ('activity', 'Audit trail'),
)
CONTRACT_DETAIL_TAB_KEYS = {key for key, _ in CONTRACT_DETAIL_TABS}
CONTRACT_DETAIL_TAB_ALIASES = {
    'review': 'workflow',
    'approvals': 'workflow',
    'audit': 'activity',
    'audit-trail': 'activity',
    'audit_trail': 'activity',
}
WORKFLOW_SECTIONS = frozenset({'review', 'approvals', 'signatures'})


def contract_detail_workflow_url(contract_pk: int, *, section: str = 'review') -> str:
    """Deep link into the contract workflow tab at the right specialist section."""
    section = normalize_workflow_section(section)
    base = reverse('contracts:contract_detail', kwargs={'pk': contract_pk})
    return f'{base}?tab=workflow&section={section}'


def normalize_contract_detail_tab(raw_tab: str | None) -> str:
    key = (raw_tab or 'overview').strip().lower()
    key = CONTRACT_DETAIL_TAB_ALIASES.get(key, key)
    return key if key in CONTRACT_DETAIL_TAB_KEYS else 'overview'


def normalize_workflow_section(raw_section: str | None, *, raw_tab: str | None = None) -> str:
    """Preserve deep links to review/approvals via ?tab= or ?section=."""
    section = (raw_section or '').strip().lower()
    if section in WORKFLOW_SECTIONS:
        return section
    tab = (raw_tab or '').strip().lower()
    if tab in ('review', 'approvals'):
        return tab
    return 'review'

_AUDIT_FIELD_LABELS = {
    'title': 'Title',
    'content': 'Contract content',
    'status': 'Status',
    'lifecycle_stage': 'Lifecycle stage',
    'contract_type': 'Contract type',
    'counterparty': 'Counterparty',
    'paper_source': 'Paper source',
    'value': 'Value',
    'currency': 'Currency',
    'governing_law': 'Governing law',
    'jurisdiction': 'Jurisdiction',
    'risk_level': 'Risk level',
    'data_transfer_flag': 'Data transfer flag',
    'dpa_attached': 'DPA attached',
    'scc_attached': 'SCC attached',
    'start_date': 'Start date',
    'end_date': 'End date',
    'renewal_date': 'Renewal date',
    'auto_renew': 'Auto-renew',
    'notice_period_days': 'Notice period',
    'termination_notice_date': 'Termination notice date',
    'client_id': 'Client',
    'matter_id': 'Matter',
    'owner_id': 'Owner',
    'approval_step': 'Approver',
    'document_id': 'Document',
    'document_title': 'Document',
    'decision': 'Decision',
}

def build_overview_progress(
    contract,
    *,
    lifecycle_path: list[dict],
    next_milestone: dict | None,
    current_blockers: list[str],
    later_workflow_requirements: list[str],
) -> dict:
    """Compact Progress panel model for the Overview command page."""
    compact_keys = (
        'DRAFTING',
        'INTERNAL_REVIEW',
        'NEGOTIATION',
        'APPROVAL',
        'SIGNATURE',
        'EXECUTED',
    )
    compact_labels = {
        'DRAFTING': 'Drafting',
        'INTERNAL_REVIEW': 'Internal Review',
        'NEGOTIATION': 'Negotiation',
        'APPROVAL': 'Approval',
        'SIGNATURE': 'Signature',
        'EXECUTED': 'Executed',
    }
    stage = contract.lifecycle_stage or 'DRAFTING'
    # Collapse post-execution tracking into the final compact step.
    if stage in ('OBLIGATION_TRACKING', 'RENEWAL'):
        mapped = 'EXECUTED'
    elif stage not in compact_keys:
        mapped = 'DRAFTING'
    else:
        mapped = stage
    try:
        current_index = compact_keys.index(mapped)
    except ValueError:
        current_index = 0

    compact_steps = []
    for index, key in enumerate(compact_keys):
        if index < current_index:
            state = 'done'
        elif index == current_index:
            state = 'current'
        else:
            state = 'upcoming'
        compact_steps.append({'key': key, 'label': compact_labels[key], 'state': state})

    current = next((step for step in lifecycle_path if step['state'] == 'current'), None)
    upcoming = next((step for step in lifecycle_path if step['state'] == 'upcoming'), None)
    blocking = current_blockers[0] if current_blockers else (
        later_workflow_requirements[0] if later_workflow_requirements else None
    )
    return {
        'current_stage': (current or {}).get('label') or contract.get_lifecycle_stage_display(),
        'next_stage': (upcoming or {}).get('label') or '—',
        'next_milestone': next_milestone,
        'blocking_item': blocking,
        'signature_requirement': next(
            (
                item for item in later_workflow_requirements
                if 'approv' in item.lower() or 'signature' in item.lower()
            ),
            later_workflow_requirements[0] if later_workflow_requirements else None,
        ),
        'compact_steps': compact_steps,
        'lifecycle_path': lifecycle_path,
    }


REVIEW_NOT_STARTED = 'Not started'
REVIEW_IN_PROGRESS = 'In progress'
REVIEW_NEEDS_REFRESH = 'Needs refresh'
REVIEW_COMPLETE = 'Complete'


def contract_detail_tab_url(contract_pk: int, tab: str) -> str:
    tab = normalize_contract_detail_tab(tab)
    base = reverse('contracts:contract_detail', kwargs={'pk': contract_pk})
    if tab == 'overview':
        return base
    return f'{base}?tab={tab}'


def build_contract_detail_tabs(contract_pk: int, active_tab: str) -> list[dict]:
    active = normalize_contract_detail_tab(active_tab)
    return [
        {
            'key': key,
            'label': label,
            'url': contract_detail_tab_url(contract_pk, key),
            'active': key == active,
            'panel_id': f'contract-tab-{key}',
        }
        for key, label in CONTRACT_DETAIL_TABS
    ]


def build_workflow_section_tabs(contract_pk: int, section: str) -> list[dict]:
    """Secondary Workflow sections (Review findings / Approvals). Not lifecycle stages."""
    active = section if section in WORKFLOW_SECTIONS else 'review'
    base = contract_detail_tab_url(contract_pk, 'workflow')
    sep = '&' if '?' in base else '?'
    return [
        {
            'key': 'review',
            'label': 'Review findings',
            'url': f'{base}{sep}section=review',
            'active': active == 'review',
        },
        {
            'key': 'approvals',
            'label': 'Approvals',
            'url': f'{base}{sep}section=approvals',
            'active': active in ('approvals', 'signatures'),
        },
    ]


def contract_operations_hub_tabs(*, active: str = 'repository') -> list[dict]:
    """Shared Contract operations hub links (Repository / My Work / Approvals / Signatures)."""
    tabs = (
        ('repository', 'All contracts', 'contracts:repository'),
        ('my_work', 'My Work', 'contracts:my_work'),
        ('approvals', 'Approvals', 'contracts:approval_request_list'),
        ('signatures', 'Signatures', 'contracts:signature_request_list'),
    )
    return [
        {
            'key': key,
            'label': label,
            'url': reverse(route),
            'active': key == active,
        }
        for key, label, route in tabs
    ]


def derive_contract_review_status(
    *,
    has_documents: bool,
    review_completed: bool,
    check_is_current: bool,
    has_grounded_check: bool,
    has_uploaded_review: bool,
) -> tuple[str, str]:
    """Return (status label, legacy badge class) for Contract review."""
    if not has_documents:
        return REVIEW_NOT_STARTED, 'badge-gray'
    started = has_grounded_check or has_uploaded_review or review_completed
    if not started:
        return REVIEW_NOT_STARTED, 'badge-gray'
    if has_grounded_check and not check_is_current:
        return REVIEW_NEEDS_REFRESH, 'badge-yellow'
    if review_completed or check_is_current:
        return REVIEW_COMPLETE, 'badge-green'
    return REVIEW_IN_PROGRESS, 'badge-yellow'


def build_lifecycle_command_label(contract, *, has_documents: bool) -> tuple[str, str]:
    """Composite lifecycle label for the contract command header.

    Returns (label, legacy badge class). Special cases keep status/stage
    language consistent across repository and detail surfaces.
    """
    from contracts.models import Contract

    status = contract.status
    stage = contract.lifecycle_stage

    if status == Contract.Status.IN_PROGRESS and not has_documents:
        return 'In progress · Intake incomplete', 'badge-yellow'

    if status == Contract.Status.ACTIVE and stage in (
        Contract.LifecycleStage.EXECUTED,
        Contract.LifecycleStage.OBLIGATION_TRACKING,
        'EXECUTED',
        'OBLIGATION_TRACKING',
    ):
        return 'Active · Obligation tracking', 'badge-green'

    status_label = contract.get_status_display()
    stage_label = contract.get_lifecycle_stage_display()
    if stage == 'OBLIGATION_TRACKING':
        stage_label = 'Obligation tracking'
    badge_class = {
        Contract.Status.IN_PROGRESS: 'badge-blue',
        Contract.Status.ACTIVE: 'badge-green',
        Contract.Status.EXPIRED: 'badge-yellow',
        Contract.Status.TERMINATED: 'badge-red',
        Contract.Status.CANCELLED: 'badge-gray',
        Contract.Status.ARCHIVED: 'badge-gray',
    }.get(status, 'badge-gray')
    return f'{status_label} · Currently in {stage_label}', badge_class


def format_contract_audit_activity_detail(changes, *, event_type: str | None = None) -> str:
    """Human detail for activity feed rows: field, document, decision, or workflow."""
    changes = changes or {}
    event = changes.get('event') or event_type or ''

    if event in ('contract.approval_chain_reordered',):
        return 'Approval chain order updated.'
    if event in ('contract_created', 'contract.created'):
        return 'Contract record created.'
    if event in ('contract.grounded_check_completed',):
        return 'Grounded contract review check completed.'
    if event in ('ai.uploaded_contract_review',):
        finding_count = changes.get('finding_count')
        if finding_count is not None:
            return f'Contract review recorded with {finding_count} finding(s).'
        return 'Contract review evidence recorded.'
    if 'document_title' in changes or 'document_id' in changes:
        title = changes.get('document_title') or changes.get('document_id')
        return f'Document affected: {title}.'
    if changes.get('decision'):
        return f'Decision recorded: {changes["decision"]}.'
    if event and event.startswith('contract.') and 'status' not in changes:
        label = event.replace('contract.', '').replace('_', ' ')
        return f'Workflow event: {label}.'

    parts = []
    for key, value in changes.items():
        if key in ('event', 'risk_assessment', 'finding_count', 'review_status'):
            continue
        if not isinstance(value, dict):
            continue
        if 'before' not in value and 'after' not in value:
            continue
        label = _AUDIT_FIELD_LABELS.get(key, key.replace('_', ' ').title())
        before = value.get('before')
        after = value.get('after')
        if key == 'content':
            parts.append(f'{label} updated.')
            continue
        before_label = '—' if before in (None, '') else before
        after_label = '—' if after in (None, '') else after
        if isinstance(before_label, dict) or isinstance(after_label, dict):
            parts.append(f'{label} updated.')
        else:
            parts.append(f'{label} changed from {before_label} to {after_label}.')
    if parts:
        return ' '.join(parts[:3])
    if event:
        return f'Workflow event: {event.replace(".", " ").replace("_", " ")}.'
    return 'Recorded in the audit trail.'


def get_submit_readiness(
    *,
    can_edit: bool,
    status,
    has_documents: bool,
    review_status: str,
    has_reviewer_choices: bool,
) -> dict:
    """Whether Submit for review is allowed, plus missing requirements."""
    from contracts.models import Contract

    missing = []
    draft_eligible = can_edit and status == Contract.Status.IN_PROGRESS
    if not draft_eligible:
        return {
            'ready': False,
            'draft_eligible': False,
            'missing': missing,
        }
    if not has_documents:
        missing.append('Attach a source document.')
    if review_status != REVIEW_COMPLETE:
        if review_status == REVIEW_NOT_STARTED:
            missing.append('Run contract review.')
        elif review_status == REVIEW_NEEDS_REFRESH:
            missing.append('Refresh contract review so it matches the current document.')
        else:
            missing.append('Complete contract review.')
    if not has_reviewer_choices:
        missing.append('Add an eligible workspace reviewer who is not the contract owner.')
    return {
        'ready': not missing,
        'draft_eligible': True,
        'missing': missing,
    }


def build_contract_command(
    *,
    contract,
    has_documents: bool,
    review_status: str,
    review_badge_class: str,
    review_finding_count: int,
    high_risk_findings: list,
    open_findings: list,
    can_decide_approval: bool,
    open_approval,
    can_submit_for_review: bool,
    can_route_for_signature: bool,
    can_edit: bool,
    lifecycle_guidance: dict,
    pending_approvals: list,
    approval_requests: list,
    signature_routing_blockers: list[str],
    risk_label: str,
    risk_badge_class: str,
) -> dict:
    """Build primary action, next-action copy, and current vs later blockers."""
    pk = contract.pk
    current_blockers: list[str] = []
    later_workflow_requirements: list[str] = list(signature_routing_blockers)

    if not has_documents and can_edit:
        primary_action = {
            'label': 'Attach source document',
            'target': '#contract-attach-dialog',
            'mode': 'dialog',
            'key': 'attach',
        }
        next_action = 'Attach a source document before contract review or submission can proceed.'
        current_blockers.append('Attach a source document before review or submission can proceed.')
    elif high_risk_findings:
        primary_action = {
            'label': 'Resolve blockers',
            'target': contract_detail_tab_url(pk, 'risks'),
            'mode': 'link',
            'key': 'resolve_risks',
        }
        next_action = 'Resolve open high-risk findings before this contract can advance.'
        for finding in high_risk_findings:
            current_blockers.append(finding.title)
        # High-risk signature prerequisite is a current blocker when it applies.
        risk_sig = 'Resolve high or critical open risk findings before signature routing.'
        if risk_sig in later_workflow_requirements:
            later_workflow_requirements = [b for b in later_workflow_requirements if b != risk_sig]
            if risk_sig not in current_blockers:
                current_blockers.append(risk_sig)
    elif can_decide_approval and open_approval:
        primary_action = {
            'label': 'Record review decision',
            'target': contract_detail_tab_url(pk, 'approvals'),
            'mode': 'link',
            'key': 'decide',
        }
        next_action = 'Record the outstanding approval decision.'
    elif can_submit_for_review:
        primary_action = {
            'label': 'Submit for review',
            'target': contract_detail_tab_url(pk, 'approvals'),
            'mode': 'link',
            'key': 'submit',
        }
        next_action = 'Select a reviewer and submit this contract for review.'
    elif can_route_for_signature:
        primary_action = {
            'label': 'Prepare signature request',
            'target': reverse('contracts:signature_request_create'),
            'mode': 'link',
            'key': 'signature',
        }
        next_action = 'Prepare the approved agreement for signature.'
        current_blockers = []
        later_workflow_requirements = []
    else:
        from contracts.models import Contract as ContractModel

        in_obligation_command = (
            contract.status == ContractModel.Status.ACTIVE
            and contract.lifecycle_stage in (
                ContractModel.LifecycleStage.EXECUTED,
                ContractModel.LifecycleStage.OBLIGATION_TRACKING,
            )
        )
        if in_obligation_command:
            primary_action = {
                'label': 'View obligations',
                'target': contract_detail_tab_url(pk, 'obligations'),
                'mode': 'link',
                'key': 'obligations',
            }
            next_action = 'Track upcoming obligations and renewals for this active contract.'
            current_blockers = []
        else:
            primary_action = {
                'label': 'Run review',
                'target': contract_detail_tab_url(pk, 'review'),
                'mode': 'link',
                'key': 'run_review',
            }
            if review_status == REVIEW_NEEDS_REFRESH:
                next_action = 'Refresh contract review so findings match the current document.'
                current_blockers.append(
                    'Refresh contract review so findings match the current document.',
                )
            elif review_status == REVIEW_IN_PROGRESS:
                next_action = 'Complete contract review before submitting for approval.'
                current_blockers.append('Complete contract review before submitting for approval.')
            elif not has_documents:
                next_action = lifecycle_guidance.get('action') or 'Attach a source document to begin.'
                current_blockers.append('Attach a source document before review or submission can proceed.')
            else:
                next_action = 'Run contract review before submitting for approval.'
                current_blockers.append('Run contract review before submitting for approval.')

    from contracts.models import ApprovalRequest

    if pending_approvals:
        approval_label, approval_badge_class = f'{len(pending_approvals)} approval(s) pending', 'badge-yellow'
    elif approval_requests and all(
        approval.status == ApprovalRequest.Status.APPROVED for approval in approval_requests
    ):
        approval_label, approval_badge_class = 'Approvals complete', 'badge-green'
    elif approval_requests:
        approval_label, approval_badge_class = 'Approval action required', 'badge-yellow'
    else:
        approval_label, approval_badge_class = 'Not requested', 'badge-gray'

    lifecycle_label, lifecycle_badge_class = build_lifecycle_command_label(
        contract, has_documents=has_documents,
    )
    # Attach is only a header CTA when it blocks progress; other keys stay contextual.
    show_primary_action = primary_action['key'] != 'attach' or bool(current_blockers)
    if primary_action['key'] == 'obligations' and not current_blockers:
        # Obligation tracking is informational — keep Edit only in the header.
        show_primary_action = False

    return {
        'review_label': review_status,
        'review_badge_class': review_badge_class,
        'review_finding_count': review_finding_count,
        'risk_label': risk_label,
        'risk_badge_class': risk_badge_class,
        'next_action': next_action,
        'primary_action': primary_action,
        'show_primary_action': show_primary_action,
        'lifecycle_label': lifecycle_label,
        'lifecycle_badge_class': lifecycle_badge_class,
        'approval_label': approval_label,
        'approval_badge_class': approval_badge_class,
        'pending_approval_count': len(pending_approvals),
        'current_blockers': current_blockers,
        'later_workflow_requirements': later_workflow_requirements,
    }


def assert_contract_submit_ready(contract, *, review_status: str | None = None) -> None:
    """Raise ValueError when document / Contract review requirements are incomplete."""
    from contracts.models import AuditLog, Document

    has_documents = Document.objects.filter(contract=contract, is_deleted=False).exists()
    if not has_documents:
        raise ValueError('Attach a source document before submitting for review.')

    if review_status is None:
        check_log = AuditLog.objects.filter(
            organization=contract.organization,
            model_name='Contract',
            object_id=contract.pk,
            event_type='contract.grounded_check_completed',
        ).order_by('-timestamp').first()
        check_is_current = bool(check_log and check_log.timestamp >= contract.updated_at)
        document_ids = list(
            Document.objects.filter(contract=contract, is_deleted=False).values_list('pk', flat=True)
        )
        uploaded_ai_review = (
            AuditLog.objects.filter(
                organization=contract.organization,
                model_name='Document',
                object_id__in=document_ids,
                event_type='ai.uploaded_contract_review',
            ).order_by('-timestamp').first()
            if document_ids else None
        )
        review_changes = (uploaded_ai_review.changes if uploaded_ai_review else {}) or {}
        review_completed = review_changes.get('review_status') == 'completed'
        review_status, _ = derive_contract_review_status(
            has_documents=True,
            review_completed=review_completed,
            check_is_current=check_is_current,
            has_grounded_check=bool(check_log),
            has_uploaded_review=bool(uploaded_ai_review),
        )

    if review_status != REVIEW_COMPLETE:
        if review_status == REVIEW_NEEDS_REFRESH:
            raise ValueError('Refresh contract review so it matches the current document before submitting.')
        if review_status == REVIEW_IN_PROGRESS:
            raise ValueError('Complete contract review before submitting for review.')
        raise ValueError('Run contract review before submitting for review.')
