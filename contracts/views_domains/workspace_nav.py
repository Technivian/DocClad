"""Lightweight workspace destinations introduced for sidebar information architecture."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Q
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.utils.formats import date_format
from django.views.generic import TemplateView

from contracts.models import ApprovalRule, ClauseTemplate, DPAPlaybookPosition, WorkflowTemplate
from contracts.permissions import can_manage_organization
from contracts.tenancy import get_user_organization, scope_queryset_for_organization


def _format_hub_date(value):
    if not value:
        return None
    return date_format(value, 'j M Y')


def _pluralize_label(count, singular, plural=None):
    plural = plural or f'{singular}s'
    return f'{count} {singular if count == 1 else plural}'


def _build_templates_playbooks_hub_cards(organization):
    """Assemble hub destinations with a uniform two-chip metadata layout."""
    if organization is None:
        return []

    clauses = scope_queryset_for_organization(ClauseTemplate.objects.all(), organization)
    clause_total = clauses.count()
    clause_approved = clauses.filter(is_approved=True).count()
    clause_updated = clauses.aggregate(latest=Max('updated_at'))['latest']

    playbooks = DPAPlaybookPosition.objects.filter(
        Q(organization=organization) | Q(organization__isnull=True)
    )
    playbook_total = playbooks.count()
    playbook_updated = playbooks.aggregate(latest=Max('updated_at'))['latest']

    workflows = scope_queryset_for_organization(WorkflowTemplate.objects.all(), organization)
    workflow_total = workflows.count()
    workflow_active = workflows.filter(is_active=True).count()
    workflow_inactive = workflow_total - workflow_active
    workflow_updated = workflows.aggregate(latest=Max('created_at'))['latest']

    rules = scope_queryset_for_organization(ApprovalRule.objects.all(), organization)
    rule_total = rules.count()
    rule_active = rules.filter(is_active=True).count()
    rule_inactive = rule_total - rule_active
    rule_updated = rules.aggregate(latest=Max('created_at'))['latest']

    def card_meta(status_value, updated_at):
        """Every card exposes the same two chips so heights stay aligned."""
        return [
            {'label': 'Status', 'value': status_value},
            {'label': 'Updated', 'value': _format_hub_date(updated_at) or '—'},
        ]

    if clause_total:
        clause_status = f'{clause_approved} of {clause_total} approved'
    else:
        clause_status = 'No clauses yet'

    if playbook_total:
        playbook_status = f'{playbook_total} position{"s" if playbook_total != 1 else ""} configured'
    else:
        playbook_status = 'No positions yet'

    if workflow_total:
        workflow_status = f'{workflow_active} active · {workflow_inactive} inactive'
    else:
        workflow_status = 'No templates yet'

    if rule_total:
        policy_status = f'{rule_active} active · {rule_inactive} inactive'
    else:
        policy_status = 'No policies yet'

    return [
        {
            'id': 'clause-library',
            'title': 'Clause Library',
            'copy': 'Governed clauses, variants, fallback positions, and categories.',
            'href': reverse('contracts:clause_template_list'),
            'cta': 'Open Clause Library',
            'icon': 'file-text',
            'stat_value': clause_total,
            'stat_label': 'clauses' if clause_total != 1 else 'clause',
            'stat_text': _pluralize_label(clause_total, 'clause'),
            'meta': card_meta(clause_status, clause_updated),
        },
        {
            'id': 'privacy-playbooks',
            'title': 'Privacy Playbooks',
            'copy': 'Standard privacy positions and negotiation guidance.',
            'href': reverse('contracts:dpa_playbook_list'),
            'cta': 'Open Privacy Playbooks',
            'icon': 'shield',
            'stat_value': playbook_total,
            'stat_label': 'positions' if playbook_total != 1 else 'position',
            'stat_text': _pluralize_label(playbook_total, 'position'),
            'meta': card_meta(playbook_status, playbook_updated),
        },
        {
            'id': 'workflow-templates',
            'title': 'Workflow Templates',
            'copy': 'Reusable contract workflow blueprints created in Workflow Designer.',
            'href': reverse('contracts:workflow_template_list'),
            'cta': 'Open Workflow Templates',
            'icon': 'workflow',
            'stat_value': workflow_total,
            'stat_label': 'templates' if workflow_total != 1 else 'template',
            'stat_text': _pluralize_label(workflow_total, 'template'),
            'meta': card_meta(workflow_status, workflow_updated),
        },
        {
            'id': 'approval-policies',
            'title': 'Approval Policies',
            'copy': 'Thresholds, routing triggers, escalation rules, and approval gates.',
            'href': reverse('contracts:approval_rule_list'),
            'cta': 'Open Approval Policies',
            'icon': 'lock',
            'stat_value': rule_total,
            'stat_label': 'policies' if rule_total != 1 else 'policy',
            'stat_text': _pluralize_label(rule_total, 'policy', 'policies'),
            'meta': card_meta(policy_status, rule_updated),
        },
    ]


class MyWorkView(LoginRequiredMixin, TemplateView):
    """Personal action queue placeholder — assigned reviews, approvals, and obligations."""

    template_name = 'contracts/my_work.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'approvals_url': reverse('contracts:approval_request_list'),
            'obligations_url': reverse('contracts:obligations_workspace'),
            'repository_url': reverse('contracts:repository'),
            'privacy_reviews_url': reverse('contracts:dpa_review_pack_list'),
        })
        return ctx


class TemplatesPlaybooksHubView(LoginRequiredMixin, TemplateView):
    """Configuration entry point for templates, clauses, playbooks, and related rules."""

    template_name = 'contracts/templates_playbooks_hub.html'

    def dispatch(self, request, *args, **kwargs):
        organization = getattr(request, 'organization', None) or get_user_organization(request.user)
        if not can_manage_organization(request.user, organization):
            return HttpResponseForbidden('You do not have permission to manage templates and playbooks.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        organization = getattr(self.request, 'organization', None) or get_user_organization(self.request.user)
        ctx['hub_organization'] = organization
        ctx['hub_cards'] = _build_templates_playbooks_hub_cards(organization)
        ctx['hub_unavailable'] = organization is None
        return ctx
