"""Lightweight workspace destinations introduced for sidebar information architecture."""

import json
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.generic import TemplateView

from contracts.models import ApprovalRule, ClauseTemplate, DPAPlaybookPosition, WorkflowTemplate
from contracts.permissions import can_manage_organization
from contracts.services.assignments import (
    RECENTLY_COMPLETED_DAYS,
    SUMMARY_FILTERS,
    WORK_TYPE_CHOICES,
    build_filter_options,
    build_summary_counts,
    get_active_work_items_result,
    get_recently_completed_items,
)
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
    """Personal action queue — assigned reviews, approvals, tasks, and obligations."""

    template_name = 'contracts/my_work.html'

    def get_organization(self):
        return getattr(self.request, 'organization', None) or get_user_organization(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        organization = self.get_organization()
        user = self.request.user
        today = timezone.localdate()
        view_mode = self.request.GET.get('view', 'active')
        if view_mode not in ('active', 'completed'):
            view_mode = 'active'

        load_error = False
        active_rows = []
        completed_rows = []
        work_result = {'truncated': False, 'total_before_cap': 0, 'row_limit': None}
        from contracts.permissions import can_manage_organization
        can_team = bool(organization and can_manage_organization(user, organization))
        scope = self.request.GET.get('scope', 'personal')
        if scope != 'team' or not can_team:
            scope = 'personal'
        try:
            work_result = get_active_work_items_result(organization, user, today=today, scope=scope)
            active_rows = work_result['rows']
            completed_rows = get_recently_completed_items(organization, user, today=today)
        except Exception:
            load_error = True
        else:
            if organization and active_rows and view_mode == 'active':
                try:
                    from contracts.services.work_instrumentation import record_rows_surfaced, record_adoption_event
                    record_rows_surfaced(organization, user, active_rows, surface='my_work')
                    if scope == 'team':
                        record_adoption_event(
                            organization=organization,
                            user=user,
                            evidence_key='team_queue',
                            surface='my_work',
                            metadata={
                                'row_count': len(active_rows),
                                'truncated': bool(work_result.get('truncated')),
                                'total_before_cap': work_result.get('total_before_cap'),
                            },
                        )
                except Exception:
                    pass

        summary_counts = build_summary_counts(active_rows)
        filter_options = build_filter_options(active_rows)
        summary_chips = []
        tone_map = {
            'overdue': 'danger',
            'due_today': 'warning',
            'returned_to_me': 'warning',
        }
        for key, label in SUMMARY_FILTERS:
            count = summary_counts.get(key, 0)
            summary_chips.append({
                'key': key,
                'label': label,
                'count': count,
                'tone': tone_map.get(key, 'info'),
                'hidden': count == 0,
            })

        ctx.update({
            'my_work_rows': active_rows,
            'completed_rows': completed_rows,
            'summary_counts': summary_counts,
            'summary_chips': summary_chips,
            'summary_filters': SUMMARY_FILTERS,
            'work_type_choices': WORK_TYPE_CHOICES,
            'filter_options': filter_options,
            'view_mode': view_mode,
            'work_scope': scope,
            'can_view_team_queue': can_team,
            'team_queue_truncated': bool(work_result.get('truncated')),
            'team_queue_total': work_result.get('total_before_cap') or len(active_rows),
            'team_queue_limit': work_result.get('row_limit'),
            'load_error': load_error,
            'last_updated': timezone.now(),
            'recently_completed_days': RECENTLY_COMPLETED_DAYS,
            'recently_completed_copy': f'Completed items from the last {RECENTLY_COMPLETED_DAYS} days will appear here.',
            'hide_app_footer': True,
            'my_work_saved_views': [],
            'my_work_default_filters': {},
            'my_work_default_filters_json': '{}',
            'my_work_saved_views_json': '[]',
            'my_work_row_signature': ','.join(sorted(r.get('id') or '' for r in active_rows)),
        })
        if organization and not load_error:
            from contracts.models import MyWorkSavedView
            saved = list(
                MyWorkSavedView.objects.filter(organization=organization, user=user).order_by('name')
            )
            ctx['my_work_saved_views'] = saved
            default = next((v for v in saved if v.is_default), None)
            if default:
                ctx['my_work_default_filters'] = default.filters or {}
            ctx['my_work_default_filters_json'] = json.dumps(ctx['my_work_default_filters'])
            ctx['my_work_saved_views_json'] = json.dumps([
                {
                    'id': v.pk,
                    'name': v.name,
                    'filters': v.filters or {},
                    'is_default': bool(v.is_default),
                }
                for v in saved
            ])
        from contracts.view_support import reassign_member_options
        from contracts.services.ai_decision_assist import ai_decision_assist_enabled
        members = (
            reassign_member_options(organization, limit=50)
            if can_team else []
        )
        ctx['reassign_members'] = members
        ctx['assignee_options_url'] = reverse('contracts:assignee_options_api') if can_team else ''
        ctx['work_suggest_comment_url'] = reverse('contracts:work_suggest_comment_api')
        ctx['decision_assist_enabled'] = bool(organization and ai_decision_assist_enabled(organization))
        # Template suggestions always available for reject/return (even when Gemini is off).
        ctx['decision_suggest_available'] = True
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('format') == 'json':
            rows = context.get('my_work_rows') or []
            return JsonResponse({
                'count': len(rows),
                'signature': context.get('my_work_row_signature') or '',
                'summary': context.get('summary_counts') or {},
                'last_updated': context['last_updated'].isoformat(),
            })
        return super().render_to_response(context, **response_kwargs)


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
