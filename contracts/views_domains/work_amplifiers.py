"""Phase 6 amplifiers — work health report and My Work saved views."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from contracts.models import MyWorkSavedView
from contracts.permissions import can_manage_organization
from contracts.services.work_instrumentation import build_operating_metrics
from contracts.tenancy import get_user_organization


class WorkHealthReportView(LoginRequiredMixin, TemplateView):
    """Cross-workspace bottleneck / SLA report for legal ops admins."""

    template_name = 'contracts/work_health_report.html'

    def dispatch(self, request, *args, **kwargs):
        org = get_user_organization(request.user)
        if not can_manage_organization(request.user, org):
            return HttpResponseForbidden('Only organization admins can view work health.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        try:
            days = int(self.request.GET.get('days') or 30)
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 180))
        report = build_operating_metrics(org, days=days)
        metrics = report.get('metrics') or {}
        # Present rates as 0–100 percentages for templates.
        bottlenecks = []
        for row in metrics.get('bottlenecks') or []:
            bottlenecks.append({
                **row,
                'overdue_rate_pct': round(float(row.get('overdue_rate') or 0) * 100),
            })
        return_reject = {}
        for ctype, row in (metrics.get('return_reject_rate_by_contract_type') or {}).items():
            return_reject[ctype] = {
                **row,
                'return_reject_rate_pct': round(float(row.get('return_reject_rate') or 0) * 100),
            }
        rbf = metrics.get('restricted_blocked_frequency') or {}
        completed_pct = metrics.get('completed_from_my_work_pct')
        completed_display = (
            round(float(completed_pct) * 100) if completed_pct is not None else None
        )
        daily_series = metrics.get('daily_activity') or []
        daily_series_max = 1
        for day in daily_series:
            day_total = (
                int(day.get('surfaced') or 0)
                + int(day.get('completed') or 0)
                + int(day.get('returned') or 0)
                + int(day.get('rejected') or 0)
            )
            if day_total > daily_series_max:
                daily_series_max = day_total

        from contracts.services.work_instrumentation import build_operating_trends, build_adoption_evidence
        trend_payload = build_operating_trends(org, days=days)
        trends = trend_payload.get('trends') or {}
        adoption = build_adoption_evidence(org, days=days)
        trend_cards = []
        for key, label, as_pct, unit in (
            ('completed_from_my_work_pct', 'Hub completion', True, '%'),
            ('time_to_first_action_hours', 'Time to first action', False, 'h'),
            ('approval_decision_lag_hours', 'Approval decision lag', False, 'h'),
            ('blocked_rate', 'Blocked on surface', True, '%'),
        ):
            row = trends.get(key) or {}
            cur = row.get('current')
            delta = row.get('delta')
            if as_pct and cur is not None:
                cur_display = f'{round(cur * 100)}{unit}'
            elif cur is not None:
                cur_display = f'{cur}{unit}'
            else:
                cur_display = '—'
            if as_pct and delta is not None:
                delta_display = f'{delta * 100:+.1f}{unit} vs prior {days}d'
            elif delta is not None:
                delta_display = f'{delta:+.2f}{unit} vs prior {days}d'
            else:
                delta_display = 'No prior-window baseline yet'
            trend_cards.append({
                'key': key,
                'label': label,
                'value': cur_display,
                'delta': delta_display,
                'direction': row.get('direction') or 'flat',
            })

        signals = adoption.get('signals') or {}
        gates = adoption.get('gates') or {}
        adoption_cards = [
            {'label': 'Team queue views', 'value': signals.get('team_queue_views', 0), 'gate': 'consider_team_default' if gates.get('consider_team_default') else ''},
            {'label': 'Assignee searches', 'value': signals.get('assignee_searches', 0), 'gate': 'consider_sse_workload' if gates.get('consider_sse_workload') else ''},
            {'label': 'Suggest requested', 'value': signals.get('suggest_requested', 0), 'gate': ''},
            {'label': 'Suggest applied', 'value': signals.get('suggest_applied', 0), 'gate': ''},
        ]
        gate_notes = []
        if gates.get('consider_team_default'):
            gate_notes.append('Team queue usage is high enough to reconsider a remembered admin default (still not product-default).')
        if gates.get('consider_chart_library'):
            gate_notes.append('Completion volume supports richer charts if CSS trends are hard to read.')
        if gates.get('consider_sse_workload'):
            gate_notes.append('Assignee search volume may justify live workload feeds.')

        ctx.update({
            'organization': org,
            'report': report,
            'metrics': metrics,
            'bottlenecks': bottlenecks,
            'return_reject_by_type': return_reject,
            'sla_breaches': metrics.get('sla_breaches') or [],
            'blocked_rate_pct': round(float(rbf.get('blocked_rate') or 0) * 100),
            'completed_from_my_work_pct_display': completed_display,
            'hub_completion_healthy': (
                completed_display is not None and completed_display >= 40
            ),
            'daily_series': daily_series,
            'daily_series_max': daily_series_max,
            'trend_cards': trend_cards,
            'adoption_cards': adoption_cards,
            'adoption_gate_notes': gate_notes,
            'window_days': days,
            'hide_app_footer': True,
        })
        return ctx


def _saved_view_payload(view: MyWorkSavedView) -> dict:
    return {
        'id': view.pk,
        'name': view.name,
        'filters': view.filters or {},
        'is_default': bool(view.is_default),
        'updated_at': view.updated_at.isoformat() if view.updated_at else None,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def my_work_saved_views_api(request):
    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)

    if request.method == 'GET':
        views = MyWorkSavedView.objects.filter(organization=org, user=request.user).order_by('name')
        return JsonResponse({'views': [_saved_view_payload(v) for v in views]})

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = (data.get('name') or '').strip()[:120]
    if not name:
        return JsonResponse({'error': 'name is required'}, status=400)
    filters = data.get('filters') if isinstance(data.get('filters'), dict) else {}
    is_default = bool(data.get('is_default'))

    if is_default:
        MyWorkSavedView.objects.filter(
            organization=org, user=request.user, is_default=True,
        ).update(is_default=False)

    view, created = MyWorkSavedView.objects.update_or_create(
        organization=org,
        user=request.user,
        name=name,
        defaults={'filters': filters, 'is_default': is_default},
    )
    return JsonResponse({'ok': True, 'created': created, 'view': _saved_view_payload(view)})


@login_required
@require_http_methods(['POST', 'DELETE'])
def my_work_saved_view_detail_api(request, view_id):
    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)
    view = get_object_or_404(MyWorkSavedView, pk=view_id, organization=org, user=request.user)

    if request.method == 'DELETE':
        view.delete()
        return JsonResponse({'ok': True})

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = (data.get('action') or 'update').strip()
    if action == 'set_default':
        MyWorkSavedView.objects.filter(
            organization=org, user=request.user, is_default=True,
        ).exclude(pk=view.pk).update(is_default=False)
        view.is_default = True
        view.save(update_fields=['is_default', 'updated_at'])
        return JsonResponse({'ok': True, 'view': _saved_view_payload(view)})

    if 'name' in data:
        name = (data.get('name') or '').strip()[:120]
        if name:
            view.name = name
    if isinstance(data.get('filters'), dict):
        view.filters = data['filters']
    if 'is_default' in data:
        is_default = bool(data.get('is_default'))
        if is_default:
            MyWorkSavedView.objects.filter(
                organization=org, user=request.user, is_default=True,
            ).exclude(pk=view.pk).update(is_default=False)
        view.is_default = is_default
    view.save()
    return JsonResponse({'ok': True, 'view': _saved_view_payload(view)})
