from django.contrib.auth import get_user_model

from .models import (
    Budget,
    ChecklistItem,
    ComplianceChecklist,
    Contract,
    DueDiligenceTask,
    DueDiligenceProcess,
    Matter,
    OrganizationMembership,
    Workflow,
    WorkflowStep,
    WorkflowTemplate,
)
from .tenancy import get_user_organization, scope_queryset_for_organization, set_organization_on_instance

User = get_user_model()


def get_request_organization(request):
    if not hasattr(request, '_cached_organization'):
        request._cached_organization = get_user_organization(request.user)
    return request._cached_organization


def get_scoped_queryset_for_request(request, queryset_or_model):
    organization = get_request_organization(request)
    if hasattr(queryset_or_model, '_meta') and hasattr(queryset_or_model, 'objects'):
        queryset = queryset_or_model.objects.all()
    else:
        queryset = queryset_or_model
    return scope_queryset_for_organization(queryset, organization)


class OrganizationContextMixin:
    """Provide a cached organization lookup for the current request."""

    def get_organization(self):
        return get_request_organization(self.request)


class TenantScopedQuerysetMixin(OrganizationContextMixin):
    """Automatically scope querysets to the current organization."""

    def get_queryset(self):
        queryset = super().get_queryset()
        org = self.get_organization()
        return scope_queryset_for_organization(queryset, org)


class TenantAssignCreateMixin(OrganizationContextMixin):
    def form_valid(self, form):
        set_organization_on_instance(form.instance, self.get_organization())
        return super().form_valid(form)


def scope_model_queryset(model_class, organization):
    return scope_queryset_for_organization(model_class.objects.all(), organization)


def apply_form_queryset_scopes(form, organization, scoped_form_fields):
    for field_name, queryset_source in scoped_form_fields.items():
        if field_name not in form.fields:
            continue

        if hasattr(queryset_source, '_meta') and hasattr(queryset_source, 'objects'):
            queryset = scope_model_queryset(queryset_source, organization)
        elif callable(queryset_source):
            queryset = queryset_source(organization)
        else:
            queryset = queryset_source
        form.fields[field_name].queryset = queryset
    return form


class TenantScopedFormMixin(OrganizationContextMixin):
    scoped_form_fields = {}

    def get_scoped_form_fields(self):
        return self.scoped_form_fields

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return apply_form_queryset_scopes(form, self.get_organization(), self.get_scoped_form_fields())


def scope_workflows_for_organization(organization):
    if organization is None:
        return Workflow.objects.none()
    return Workflow.objects.filter(organization=organization)


def scope_workflow_templates_for_organization(organization):
    if organization is None:
        return WorkflowTemplate.objects.none()
    return WorkflowTemplate.objects.filter(
        organization=organization,
    ) | WorkflowTemplate.objects.filter(
        organization__isnull=True,
    )


def scope_workflow_steps_for_organization(organization):
    if organization is None:
        return WorkflowStep.objects.none()
    return WorkflowStep.objects.filter(workflow__organization=organization)


def scope_checklists_for_organization(organization):
    if organization is None:
        return ComplianceChecklist.objects.none()
    return ComplianceChecklist.objects.filter(contract__organization=organization)


def scope_checklist_items_for_organization(organization):
    if organization is None:
        return ChecklistItem.objects.none()
    return ChecklistItem.objects.filter(checklist__contract__organization=organization)


def scope_due_diligence_processes_for_organization(organization):
    if organization is None:
        return DueDiligenceProcess.objects.none()
    return DueDiligenceProcess.objects.filter(organization=organization)


def scope_due_diligence_tasks_for_organization(organization):
    if organization is None:
        return DueDiligenceTask.objects.none()
    return DueDiligenceTask.objects.filter(process__organization=organization)


def scope_budgets_for_organization(organization):
    if organization is None:
        return Budget.objects.none()
    return Budget.objects.filter(organization=organization)


def organization_user_queryset(organization):
    if organization is None:
        return User.objects.none()
    return User.objects.filter(
        organization_memberships__organization=organization,
        organization_memberships__is_active=True,
    ).distinct()


def open_work_count_by_user(organization):
    """Open actionable work counts keyed by assignee user id (approvals, tasks, obligations)."""
    from django.core.cache import cache
    from django.db.models import Count

    from contracts.models import ApprovalRequest, Deadline, LegalTask
    from contracts.tenancy import scope_queryset_for_organization

    if organization is None:
        return {}
    cache_key = f'clmone:open_work_count:v1:{organization.pk}'
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    counts = {}

    def _add(user_id, n):
        if not user_id:
            return
        counts[user_id] = counts.get(user_id, 0) + int(n or 0)

    approvals = scope_queryset_for_organization(
        ApprovalRequest.objects.filter(
            status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED],
        ),
        organization,
    )
    for row in approvals.values('assigned_to_id').annotate(c=Count('id')):
        _add(row['assigned_to_id'], row['c'])
    for row in approvals.exclude(delegated_to_id=None).values('delegated_to_id').annotate(c=Count('id')):
        _add(row['delegated_to_id'], row['c'])

    tasks = LegalTask.objects.for_organization(organization).filter(
        status__in=[LegalTask.Status.PENDING, LegalTask.Status.IN_PROGRESS],
    )
    for row in tasks.values('assigned_to_id').annotate(c=Count('id')):
        _add(row['assigned_to_id'], row['c'])

    obligations = (
        Deadline.objects.for_organization(organization)
        .filter(is_completed=False)
        .values('assigned_to_id')
        .annotate(c=Count('id'))
    )
    for row in obligations:
        _add(row['assigned_to_id'], row['c'])

    cache.set(cache_key, counts, 60)
    return counts


def reassign_member_options(
    organization,
    *,
    include_workload=True,
    q='',
    limit=None,
    exclude_ids=None,
):
    """Active org members for manager reassignment pickers (id + display label + open work).

    Optional ``q`` filters by name/username (case-insensitive contains).
    Optional ``limit`` caps results after workload sort (for live typeahead).
    """
    from django.db.models import Q

    users = organization_user_queryset(organization)
    query = (q or '').strip()
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    users = users.order_by('first_name', 'last_name', 'username')
    exclude = {int(x) for x in (exclude_ids or []) if str(x).isdigit() or isinstance(x, int)}
    workload = open_work_count_by_user(organization) if include_workload else {}
    options = []
    for user in users:
        if user.pk in exclude:
            continue
        full = (user.get_full_name() or '').strip()
        label = full or user.username
        if full and user.username and full.lower() != user.username.lower():
            label = f'{full} ({user.username})'
        open_count = int(workload.get(user.pk, 0))
        options.append({
            'id': user.pk,
            'label': label,
            'username': user.username,
            'open_count': open_count,
            'search': f'{label} {user.username}'.lower(),
        })
    options.sort(key=lambda row: (row['open_count'], row['label'].casefold()))
    if limit is not None:
        try:
            lim = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            lim = 40
        options = options[:lim]
    return options


def configure_workflow_form(form, organization):
    form = apply_form_queryset_scopes(form, organization, {'contract': Contract})
    if 'template' in form.fields:
        if organization is None:
            form.fields['template'].queryset = WorkflowTemplate.objects.none()
        else:
            form.fields['template'].queryset = (
                WorkflowTemplate.objects.filter(
                    organization=organization,
                    is_active=True,
                )
                | WorkflowTemplate.objects.filter(
                    organization__isnull=True,
                    is_active=True,
                )
            ).distinct().order_by('name', '-version', '-created_at', '-pk')
    return form
