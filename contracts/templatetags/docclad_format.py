"""Shared human-readable formatting filters.

Consolidates the presentation rules that were previously duplicated (or
missing) in individual templates — currency, ISO datetime strings, enum-style
labels, audit event descriptions, and short durations. New templates should
use these instead of formatting values inline.
"""
import re
from decimal import Decimal, InvalidOperation

from django import template
from django.template.defaultfilters import date as date_filter
from django.utils.dateparse import parse_date, parse_datetime

register = template.Library()

_CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'CHF': 'Fr',
    'CAD': 'C$',
    'AUD': 'A$',
}

# Closed, stable set of model names this app writes to AuditLog.model_name —
# see contracts/middleware.py:log_action. Unknown values fall back to a
# generic PascalCase-to-words split so a new model never renders as raw
# CamelCase, even before this map is updated.
_OBJECT_TYPE_LABELS = {
    'ApprovalRequest': 'approval',
    'ClauseTemplate': 'clause template',
    'Client': 'client',
    'ConflictCheck': 'conflict check',
    'Contract': 'contract',
    'ContractAI': 'AI review',
    'Deadline': 'deadline',
    'Document': 'document',
    'DSARRequest': 'data subject request',
    'ESignEvent': 'signature event',
    'Invoice': 'invoice',
    'Matter': 'matter',
    'NegotiationThread': 'negotiation note',
    'Notification': 'notification',
    'Organization': 'organization',
    'OrganizationInvitation': 'team invitation',
    'OrganizationMembership': 'team membership',
    'OrganizationSCIMGroup': 'SCIM group',
    'RetentionExecution': 'retention run',
    'Session': 'session',
    'SignaturePacket': 'signature packet',
    'SignatureRequest': 'signature request',
    'TimeEntry': 'time entry',
    'TrustAccount': 'trust account',
    'TrustTransaction': 'trust transaction',
    'UserProfile': 'profile',
}

_ACRONYMS = {'ai', 'mfa', 'sso', 'saml', 'scim', 'dsar', 'api', 'id', 'url', 'crm', 'dpa', 'scc', 'ip'}
_PASCAL_SPLIT_RE = re.compile(r'(?<!^)(?=[A-Z])')

# Canonical semantic vocabulary (design-system Phase 2 — badges, status,
# empty states). This is the single source of truth for "what does each
# status word mean, visually" — every *_BADGES map below must resolve to one
# of these eight names. Values are the legacy `badge-*` class this semantic
# name currently renders as; CANONICAL_BADGE_TONE gives the .dc-ds-badge--*
# tone a future migration should use instead. Both point at the same
# underlying --status-*-fg/--status-*-bg tokens in docclad-tokens.css, so
# switching a template from one to the other is a pure markup change with no
# colour drift. Not wired into any *_BADGES map yet — this documents and
# tests the mapping ahead of any page migration, it does not perform one.
LEGACY_BADGE_CLASS = {
    'success': 'badge-green',
    'information': 'badge-blue',
    'warning': 'badge-yellow',
    'danger': 'badge-red',
    'neutral': 'badge-gray',
    'pending': 'badge-yellow',
    'inactive': 'badge-gray',
    'not_applicable': 'badge-gray',
}
CANONICAL_BADGE_TONE = {
    'success': 'dc-ds-badge--success',
    'information': 'dc-ds-badge--progress',
    'warning': 'dc-ds-badge--attention',
    'danger': 'dc-ds-badge--danger',
    'neutral': 'dc-ds-badge--neutral',
    'pending': 'dc-ds-badge--attention',
    'inactive': 'dc-ds-badge--neutral',
    'not_applicable': 'dc-ds-badge--neutral',
}
assert LEGACY_BADGE_CLASS.keys() == CANONICAL_BADGE_TONE.keys()

# Complete Contract.Status → badge variant map. Color is semantic, never
# decorative: green = healthy/terminal-good, yellow = waiting on someone,
# blue = in-flight process, red = expired/terminated, gray = neutral/inert.
# Every status must have an entry — an unmapped status rendering gray is a
# defect, not a fallback.
_STATUS_BADGES = {
    'DRAFT': 'badge-gray',
    'PENDING': 'badge-yellow',
    'IN_REVIEW': 'badge-blue',
    'APPROVED': 'badge-blue',
    'ACTIVE': 'badge-green',
    'COMPLETED': 'badge-green',
    'EXPIRED': 'badge-red',
    'TERMINATED': 'badge-red',
    'CANCELLED': 'badge-gray',
}

# Contract.lifecycle_stage -> a simplified 6-value chip vocabulary for
# compact table contexts (the work queue's "Stage" column) — a per-row
# lifecycle dot-track is legible in a dedicated lifecycle section but reads
# as noise repeated down a table; a plain status chip reads faster there.
# The full 9-stage detail (with dots) is still used on the contract detail
# page via {% stage_dots %} — this is a compact-context alternative, not a
# replacement of the richer view.
_LIFECYCLE_STAGE_LABELS = {
    'DRAFTING': 'Draft',
    'INTERNAL_REVIEW': 'Legal Review',
    'NEGOTIATION': 'Legal Review',
    'APPROVAL': 'Approval',
    'SIGNATURE': 'Signature',
    'EXECUTED': 'Active',
    'OBLIGATION_TRACKING': 'Active',
    'RENEWAL': 'Renewal',
    'ARCHIVED': 'Archived',
}
_LIFECYCLE_STAGE_BADGES = {
    'DRAFTING': 'badge-gray',
    'INTERNAL_REVIEW': 'badge-green',
    'NEGOTIATION': 'badge-green',
    'APPROVAL': 'badge-gray',
    'SIGNATURE': 'badge-gray',
    'EXECUTED': 'badge-green',
    'OBLIGATION_TRACKING': 'badge-green',
    'RENEWAL': 'badge-yellow',
    'ARCHIVED': 'badge-gray',
}

_PHASE_BADGES = {
    'intake': 'badge-gray',
    'beoordeling': 'badge-yellow',
    'matching': 'badge-purple',
    'plaatsing': 'badge-blue',
    'actief': 'badge-green',
    'afgerond': 'badge-green',
}

# ApprovalRequest.status -> badge variant. A separate map from
# _STATUS_BADGES (Contract) on purpose: the two fields use an overlapping
# vocabulary ('APPROVED') with different semantics — a Contract in
# APPROVED status is still mid-flight (blue), but an ApprovalRequest
# decision of APPROVED is a positive, terminal outcome (green).
_APPROVAL_STATUS_BADGES = {
    'PENDING': 'badge-yellow',
    'APPROVED': 'badge-green',
    'REJECTED': 'badge-red',
    'ESCALATED': 'badge-purple',
}

# ApprovalRequest.status -> canonical .dc-ds-badge--* tone, for pages
# migrated onto design_system/status_badge.html (Phase 4). PENDING/APPROVED/
# REJECTED map onto the 8-name semantic vocabulary (attention/success/
# danger); ESCALATED deliberately uses --special rather than --danger —
# ARCHITECTURE.md's Phase 2 audit notes reserve --special for exactly this
# "rare/escalated" consumer, distinct from a plain blocking/danger state.
# Kept separate from CANONICAL_BADGE_TONE (which only covers the 8-name
# vocabulary) rather than folding ESCALATED into 'danger' and losing that
# distinction.
_APPROVAL_STATUS_BADGE_TONE = {
    'PENDING': 'attention',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'ESCALATED': 'special',
}

# Document.status -> badge variant.
_DOCUMENT_STATUS_BADGES = {
    'DRAFT': 'badge-gray',
    'REVIEW': 'badge-yellow',
    'APPROVED': 'badge-blue',
    'FINAL': 'badge-green',
    'ARCHIVED': 'badge-gray',
}

# Client.status -> badge variant.
_CLIENT_STATUS_BADGES = {
    'ACTIVE': 'badge-green',
    'INACTIVE': 'badge-gray',
    'PROSPECTIVE': 'badge-blue',
    'FORMER': 'badge-gray',
}

# LegalTask.status -> badge variant.
_TASK_STATUS_BADGES = {
    'PENDING': 'badge-yellow',
    'IN_PROGRESS': 'badge-blue',
    'COMPLETED': 'badge-green',
    'CANCELLED': 'badge-gray',
}

# LegalTask.priority -> badge variant (URGENT/HIGH share the most severe
# treatment; there is no separate "critical" tier on the model).
_TASK_PRIORITY_BADGES = {
    'URGENT': 'badge-red',
    'HIGH': 'badge-red',
    'MEDIUM': 'badge-yellow',
    'LOW': 'badge-green',
}

# DPARiskItem.severity -> badge variant.
_DPA_SEVERITY_BADGES = {
    'CRITICAL': 'badge-red',
    'HIGH': 'badge-red',
    'MEDIUM': 'badge-yellow',
    'LOW': 'badge-green',
}

# DPAReviewPack.approval_status -> badge variant.
_DPA_APPROVAL_BADGES = {
    'DRAFT': 'badge-gray',
    'UNDER_REVIEW': 'badge-blue',
    'ESCALATED': 'badge-purple',
    'APPROVED': 'badge-green',
    'REJECTED': 'badge-red',
}

# DPARiskItem.owners is a comma-separated list of Owner codes (a risk can be
# jointly owned, e.g. "LEGAL,DPO_SECURITY") — not a Django choice field, so
# there is no get_owners_display() to call. Mirrors DPARiskItem.Owner.choices.
_DPA_OWNER_LABELS = {
    'LEGAL': 'Legal',
    'HEAD_LEGAL': 'Head of Legal',
    'DPO_SECURITY': 'DPO/Security',
    'BUSINESS': 'Business',
    'FINANCE': 'Finance',
    'DELIVERY': 'Delivery',
}

# RiskLog.status was modeled with Dutch display labels ('In opvolging',
# 'Afgerond') from an earlier localized build — the model's own
# get_status_display() cannot be used in the UI without leaking that Dutch
# chrome. This map (and risk_status_label below) is the English override;
# changing the model's TextChoices labels is out of scope here, so the raw
# key is translated at the presentation layer instead.
_RISK_STATUS_BADGES = {
    'OPEN': 'badge-yellow',
    'IN_PROGRESS': 'badge-blue',
    'RESOLVED': 'badge-green',
}
_RISK_STATUS_LABELS = {
    'OPEN': 'Open',
    'IN_PROGRESS': 'In Progress',
    'RESOLVED': 'Resolved',
}

# SignatureRequest.status -> badge variant.
_SIGNATURE_STATUS_BADGES = {
    'PENDING': 'badge-gray',
    'SENT': 'badge-yellow',
    'VIEWED': 'badge-blue',
    'SIGNED': 'badge-green',
    'DECLINED': 'badge-red',
    'EXPIRED': 'badge-red',
    'CANCELLED': 'badge-gray',
}

# Contract.risk_level -> badge variant (same LOW/MEDIUM/HIGH/CRITICAL scale
# already used elsewhere, kept as its own map since it's a distinct field).
_CONTRACT_RISK_BADGES = {
    'LOW': 'badge-green',
    'MEDIUM': 'badge-yellow',
    'HIGH': 'badge-red',
    'CRITICAL': 'badge-red',
}

# ApprovalRequest.approval_step is a free CharField copied from whichever
# ApprovalRule triggered it — it has no Django choices of its own, so
# without this map the raw rule code (e.g. 'LEGAL') would leak into the UI.
# Mirrors ApprovalRule.approval_step's choices verbatim.
_APPROVAL_STEP_LABELS = {
    'LEGAL': 'Legal Review',
    'FINANCE': 'Finance Review',
    'PRIVACY': 'Privacy Review',
    'EXECUTIVE': 'Executive Approval',
    'COMPLIANCE': 'Compliance Review',
}

# Canonical lifecycle path shown on the contract detail page. Order matters:
# it is the position of contract.lifecycle_stage in this list that decides
# which steps render as done/current/upcoming.
_LIFECYCLE_PATH = [
    ('DRAFTING', 'Drafting'),
    ('INTERNAL_REVIEW', 'Internal Review'),
    ('NEGOTIATION', 'Negotiation'),
    ('APPROVAL', 'Approval'),
    ('SIGNATURE', 'Signature'),
    ('EXECUTED', 'Executed'),
    ('OBLIGATION_TRACKING', 'Obligation Tracking'),
    ('RENEWAL', 'Renewal'),
    ('ARCHIVED', 'Archived'),
]


@register.filter
def money(value, currency='USD'):
    """125000 -> '$125,000.00'. Unparsable/empty values render as an em dash."""
    if value in (None, ''):
        return '—'
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value
    symbol = _CURRENCY_SYMBOLS.get(currency, f'{currency} ')
    return f'{symbol}{amount:,.2f}'


@register.filter
def iso_datetime(value, fmt='M d, Y H:i'):
    """Format an ISO-8601 string OR a date/datetime object; passes through on failure."""
    if not value:
        return ''
    parsed = value
    if isinstance(value, str):
        parsed = parse_datetime(value) or parse_date(value)
        if not parsed:
            return value
    return date_filter(parsed, fmt)


@register.filter
def due_countdown(value):
    """Date -> 'Overdue' / 'Today' / 'N days' (<=30d out) / 'd M Y' further out."""
    if not value:
        return '—'
    from datetime import date as date_cls
    today = date_cls.today()
    d = value.date() if hasattr(value, 'date') else value
    delta = (d - today).days
    if delta < 0:
        return 'Overdue'
    if delta == 0:
        return 'Today'
    if delta <= 30:
        return f'{delta} day{"s" if delta != 1 else ""}'
    return date_filter(d, 'd M Y')


@register.filter
def object_type_label(value):
    """'OrganizationMembership' -> 'team membership'; unmapped names get word-split."""
    if not value:
        return ''
    mapped = _OBJECT_TYPE_LABELS.get(value)
    if mapped:
        return mapped
    return _PASCAL_SPLIT_RE.sub(' ', value).lower()


@register.filter
def sort_label(value):
    """'-created_at' -> 'Created at ↓'; 'value' -> 'Value ↑'. Direction-agnostic
    (an arrow, not "newest"/"highest") since the same sort key can be a date,
    a number, or text depending on the field."""
    if not value:
        return ''
    descending = value.startswith('-')
    field = value[1:] if descending else value
    words = field.replace('_', ' ').split()
    label = ' '.join([words[0].capitalize()] + words[1:]) if words else field
    return f'{label} {"↓" if descending else "↑"}'


@register.filter
def event_label(value):
    """'contract_ai_assistant_invoked' -> 'Contract AI Assistant Invoked'."""
    if not value:
        return ''
    words = [w for w in re.split(r'[_.]+', str(value)) if w]
    return ' '.join(w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words)


@register.filter
def semantic_badge_tone(semantic):
    """Canonical semantic name -> .dc-ds-badge--* tone suffix, for pages
    migrating onto the canonical badge component. ('success' -> 'success',
    'not_applicable' -> 'neutral'). Use with design_system/status_badge.html's
    `tone` parameter. Unknown input falls back to 'neutral' rather than
    raising, since a badge should never render unstyled."""
    tone_class = CANONICAL_BADGE_TONE.get(semantic, CANONICAL_BADGE_TONE['neutral'])
    return tone_class.removeprefix('dc-ds-badge--')


@register.filter
def status_badge_class(status):
    """Contract status key -> canonical badge class ('ACTIVE' -> 'badge-green')."""
    return _STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def phase_badge_class(phase):
    """Case phase key -> canonical badge class ('actief' -> 'badge-green')."""
    return _PHASE_BADGES.get(phase, 'badge-gray')


@register.filter
def lifecycle_stage_label(stage):
    """Contract lifecycle_stage key -> simplified chip label ('NEGOTIATION' -> 'Legal Review')."""
    return _LIFECYCLE_STAGE_LABELS.get(stage, stage.replace('_', ' ').title() if stage else '—')


@register.filter
def lifecycle_stage_badge_class(stage):
    """Contract lifecycle_stage key -> canonical badge class for the simplified chip."""
    return _LIFECYCLE_STAGE_BADGES.get(stage, 'badge-gray')


@register.filter
def document_status_badge_class(status):
    """Document status key -> canonical badge class ('FINAL' -> 'badge-green')."""
    return _DOCUMENT_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def client_status_badge_class(status):
    """Client status key -> canonical badge class ('ACTIVE' -> 'badge-green')."""
    return _CLIENT_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def approval_status_badge_class(status):
    """ApprovalRequest status key -> canonical badge class."""
    return _APPROVAL_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def approval_status_badge_tone(status):
    """ApprovalRequest status key -> canonical .dc-ds-badge--* tone suffix."""
    return _APPROVAL_STATUS_BADGE_TONE.get(status, 'neutral')


@register.filter
def task_status_badge_class(status):
    """LegalTask status key -> canonical badge class."""
    return _TASK_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def task_priority_badge_class(priority):
    """LegalTask priority key -> canonical badge class."""
    return _TASK_PRIORITY_BADGES.get(priority, 'badge-gray')


@register.filter
def risk_status_badge_class(status):
    """RiskLog status key -> canonical badge class."""
    return _RISK_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def risk_status_label(status):
    """RiskLog status key -> English display label ('IN_PROGRESS' -> 'In Progress'),
    overriding the model's own Dutch-labeled get_status_display()."""
    return _RISK_STATUS_LABELS.get(status, status.replace('_', ' ').title() if status else '')


@register.filter
def signature_status_badge_class(status):
    """SignatureRequest status key -> canonical badge class."""
    return _SIGNATURE_STATUS_BADGES.get(status, 'badge-gray')


@register.filter
def contract_risk_badge_class(risk_level):
    """Contract risk_level key -> canonical badge class."""
    return _CONTRACT_RISK_BADGES.get(risk_level, 'badge-gray')


_OBLIGATION_COMPLIANCE_LABELS = {
    'MET': 'Met',
    'OVERDUE': 'Overdue',
    'BREACH_RISK': 'Breach Risk',
    'PENDING': 'Pending Action',
}

_OBLIGATION_COMPLIANCE_BADGES = {
    'MET': 'badge-green',
    'OVERDUE': 'badge-red',
    'BREACH_RISK': 'badge-yellow',
    'PENDING': 'badge-blue',
}


@register.filter
def obligation_compliance_status(deadline):
    """Deadline -> derived compliance status key.

    There is no stored status field for this — it's computed from
    is_completed/is_overdue/days_remaining/reminder_days so the Obligations
    workspace always reflects the deadline's current state, not a value that
    can go stale.
    """
    if not deadline or deadline.is_completed:
        return 'MET'
    if deadline.is_overdue:
        return 'OVERDUE'
    days_left = deadline.days_remaining
    if days_left is not None and days_left <= deadline.reminder_days:
        return 'BREACH_RISK'
    return 'PENDING'


@register.filter
def obligation_compliance_label(deadline):
    """Deadline -> human label for its derived compliance status."""
    return _OBLIGATION_COMPLIANCE_LABELS.get(obligation_compliance_status(deadline), '—')


@register.filter
def obligation_compliance_badge_class(deadline):
    """Deadline -> canonical badge class for its derived compliance status."""
    return _OBLIGATION_COMPLIANCE_BADGES.get(obligation_compliance_status(deadline), 'badge-gray')


@register.filter
def dpa_severity_badge_class(severity):
    """DPARiskItem severity key -> canonical badge class."""
    return _DPA_SEVERITY_BADGES.get(severity, 'badge-gray')


@register.filter
def dpa_approval_badge_class(status):
    """DPAReviewPack approval_status key -> canonical badge class."""
    return _DPA_APPROVAL_BADGES.get(status, 'badge-gray')


@register.filter
def dpa_owner_chips(owners_csv):
    """'LEGAL,DPO_SECURITY' -> ['Legal', 'DPO/Security'] for badge rendering."""
    if not owners_csv:
        return []
    return [_DPA_OWNER_LABELS.get(code, code.replace('_', ' ').title()) for code in owners_csv.split(',') if code]


@register.filter
def approval_step_label(step):
    """ApprovalRequest.approval_step raw code -> human label ('LEGAL' -> 'Legal Review')."""
    if not step:
        return ''
    return _APPROVAL_STEP_LABELS.get(step, step.replace('_', ' ').title())


@register.simple_tag
def lifecycle_steps(contract):
    """Lifecycle path for the detail-page stepper.

    Returns [{'key', 'label', 'state'}] where state is 'done', 'current', or
    'upcoming', derived from contract.lifecycle_stage's position in the
    canonical path. An unknown stage marks every step upcoming rather than
    guessing progress.
    """
    keys = [key for key, _ in _LIFECYCLE_PATH]
    try:
        current = keys.index(contract.lifecycle_stage)
    except ValueError:
        current = -1
    steps = []
    for index, (key, label) in enumerate(_LIFECYCLE_PATH):
        if current == -1 or index > current:
            state = 'upcoming'
        elif index == current:
            state = 'current'
        else:
            state = 'done'
        steps.append({'key': key, 'label': label, 'state': state})
    return steps


@register.filter
def humanduration(seconds):
    """787296 -> '9d 2h'. Machine-style second counts, made skimmable."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return seconds
    if seconds < 60:
        return f'{seconds}s'
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m'
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {mins}m' if mins else f'{hours}h'
    days, hrs = divmod(hours, 24)
    return f'{days}d {hrs}h' if hrs else f'{days}d'
