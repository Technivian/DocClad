"""Shared row-normalization helpers for the WorkQueue pattern (StageDots /
AssigneeChip / ActivityLine).

Used by both the Dashboard workflow queue and the Repository table so the
two surfaces resolve "who is this waiting on" and "what happened last"
identically — the same contract must never show a different assignee or
activity depending on which screen you're looking at.
"""
from contracts.models import ApprovalRequest, AuditLog, CaseSignal, Deadline, WorkflowStep

# Contract statuses that are "done moving" — a past-due end_date on one of
# these isn't a missed deadline, it's just history. Shared so Dashboard and
# Repository flag "overdue" identically.
TERMINAL_STATUSES = {'COMPLETED', 'EXPIRED', 'TERMINATED', 'CANCELLED'}


def assignee_map_for_contracts(org, contract_ids):
    """Best-known "assigned to" for each contract id, resolved through the
    related task/approval/workflow-step models (Contract itself has no
    assignee field). Later loops take priority over earlier ones — an open
    approval is a stronger "who's blocking this" signal than a routine task,
    so it is resolved last and wins the overwrite."""
    if not org or not contract_ids:
        return {}
    from contracts.models import Contract
    result = {
        contract.pk: contract.owner
        for contract in Contract.objects.filter(
            organization=org, pk__in=contract_ids, owner__isnull=False,
        ).select_related('owner')
    }
    for deadline in (
        Deadline.objects.for_organization(org)
        .filter(contract_id__in=contract_ids, is_completed=False, assigned_to__isnull=False)
        .select_related('assigned_to')
    ):
        result[deadline.contract_id] = deadline.assigned_to
    for step in (
        WorkflowStep.objects.filter(
            workflow__organization=org, workflow__contract_id__in=contract_ids,
            status='PENDING', assigned_to__isnull=False,
        ).select_related('assigned_to', 'workflow')
    ):
        result[step.workflow.contract_id] = step.assigned_to
    for task in (
        CaseSignal.objects.for_organization(org)
        .filter(contract_id__in=contract_ids, status__in=['PENDING', 'IN_PROGRESS'], assigned_to__isnull=False)
        .select_related('assigned_to')
    ):
        result[task.contract_id] = task.assigned_to
    for approval in (
        ApprovalRequest.objects.filter(
            organization=org, contract_id__in=contract_ids, status='PENDING', assigned_to__isnull=False,
        ).select_related('assigned_to')
    ):
        result[approval.contract_id] = approval.assigned_to
    return result


def latest_activity_map(org, object_ids, model_name='Contract'):
    """Most recent AuditLog entry per object id, for a given model_name
    (defaults to 'Contract' for the Dashboard/Repository call sites).
    AuditLog.object_id is a PositiveIntegerField, so this keys (and must be
    looked up) by the plain int pk — never a stringified id, or the lookup
    silently never hits."""
    if not org or not object_ids:
        return {}
    logs = (
        AuditLog.objects.filter(
            organization_id=org.id, model_name=model_name, object_id__in=object_ids,
        )
        .select_related('user')
        .order_by('-timestamp')
    )
    result = {}
    for log in logs:
        result.setdefault(log.object_id, log)
    return result


def creator_map(org, object_ids, model_name):
    """Best-known "created by" user for each object id, resolved from the
    earliest CREATE AuditLog entry for that model/object — the only reliable
    signal for models (like LegalTask) that have no created_by field of
    their own. Objects created before creation-logging existed simply have
    no entry here; that is a graceful gap, not a fabricated value."""
    if not org or not object_ids:
        return {}
    logs = (
        AuditLog.objects.filter(
            organization_id=org.id, model_name=model_name, object_id__in=object_ids,
            action=AuditLog.Action.CREATE,
        )
        .select_related('user')
        .order_by('timestamp')
    )
    result = {}
    for log in logs:
        result.setdefault(log.object_id, log.user)
    return result


def activity_line_parts(log):
    """(text, time_text, actor_initial) for one AuditLog entry, matching the
    exact sentence shape rendered by components/_activity_line.html — so a
    JS-rendered row and a Django-rendered row read identically."""
    if not log:
        return None, None, None
    from django.utils.timesince import timesince

    from contracts.templatetags.clmone_format import object_type_label

    if log.user:
        actor = log.user.get_full_name() or log.user.username
        initial = (log.user.first_name or log.user.username or '?')[:1].upper()
    else:
        actor = 'System'
        initial = 'S'
    verb = log.get_action_display().lower()
    obj = object_type_label(log.model_name)
    text = f'{actor} {verb} {obj}'.strip()
    time_text = f'{timesince(log.timestamp)} ago'
    return text, time_text, initial
