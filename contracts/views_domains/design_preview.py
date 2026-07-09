"""Static design-preview pages for the new Command Center / Relationships /
Contract Review Studio visual direction.

These three views render fixed, representative sample data — no querysets,
no model wiring — so the new page shapes can be reviewed and approved before
any real data-model or backend work begins. Not linked from the sidebar nav;
reachable by direct URL only. Once the direction is approved, each becomes
its own follow-up ticket to wire to real data.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def design_preview_command_center(request):
    context = {
        'stats': [
            {'label': 'Needs Legal', 'value': '23', 'delta': '15 vs last 7 days', 'delta_dir': 'up', 'icon': 'scale'},
            {'label': 'Revenue at Risk', 'value': '€4.7M', 'delta': '9% vs last 30 days', 'delta_dir': 'down', 'icon': 'dollar'},
            {'label': 'Renewals & Deadlines', 'value': '18', 'delta': 'Due in next 60 days', 'delta_dir': None, 'icon': 'calendar'},
            {'label': 'Risk Movement', 'value': '12', 'delta': 'High risk increase', 'delta_dir': 'up', 'icon': 'shield'},
        ],
        'priority_queue': [
            {'title': 'Acme MSA Renewal', 'ref': 'MSA-2021-0045', 'counterparty': 'Acme Corporation', 'type': 'MSA', 'status': 'Review', 'risk': 'High', 'risk_dots': 2, 'due': 'May 12', 'age': '5 days', 'urgent': True},
            {'title': 'Northwind DPA', 'ref': 'DPA-2022-0187', 'counterparty': 'Northwind Inc.', 'type': 'DPA', 'status': 'Review', 'risk': 'Medium', 'risk_dots': 2, 'due': 'May 19', 'age': '12 days', 'urgent': False},
            {'title': 'Supplier Renewal', 'ref': 'SUP-2021-0330', 'counterparty': 'Global Supplies Co.', 'type': 'Supply', 'status': 'Draft', 'risk': 'Medium', 'risk_dots': 2, 'due': 'Jun 02', 'age': '26 days', 'urgent': False},
            {'title': 'SOW 002 – Integration', 'ref': 'SOW-2023-0102', 'counterparty': 'Apex Integrations', 'type': 'SOW', 'status': 'Negotiation', 'risk': 'Low', 'risk_dots': 1, 'due': 'May 15', 'age': '8 days', 'urgent': False},
            {'title': 'Security Addendum', 'ref': 'SEC-2023-0044', 'counterparty': 'Harmonic Inc.', 'type': 'Addendum', 'status': 'Approval', 'risk': 'Low', 'risk_dots': 1, 'due': 'Overdue', 'age': '2 days', 'urgent': True},
        ],
        'priority_queue_count': 23,
        'risk_trend': {
            'high': {'value': 28, 'delta': 4, 'dir': 'up'},
            'medium': {'value': 61, 'delta': 6, 'dir': 'down'},
            'low': {'value': 11, 'delta': 2, 'dir': 'down'},
            'labels': ['Apr 16', 'Apr 26', 'May 06', 'May 16'],
        },
        'next_best_actions': [
            {'title': 'Review Acme MSA renewal', 'sub': 'Due in 5 days · High risk', 'icon': 'document'},
            {'title': 'Negotiate liability caps', 'sub': 'Apex Integrations SOW 002', 'icon': 'bolt'},
            {'title': 'Approve Security Addendum', 'sub': 'Harmonic Inc.', 'icon': 'check'},
            {'title': 'Prepare Board Update', 'sub': 'Q2 risk summary', 'icon': 'document'},
        ],
    }
    return render(request, 'contracts/design_preview_command_center.html', context)


@login_required
def design_preview_relationship_detail(request):
    context = {
        'company': {
            'name': 'Acme Corporation',
            'industry': 'Software',
            'location': 'San Francisco, CA',
            'customer_since': 'Jan 2021',
            'owner': 'Olivia Bennett',
            'total_contract_value': '€12.6M',
            'active_contracts': 8,
            'tier': 'Strategic',
        },
        'spine': [
            {'title': 'Master Service Agreement', 'type': 'MSA', 'effective': 'Effective Nov 1, 2021', 'active': True},
            {'title': 'Data Processing Addendum', 'type': 'DPA', 'effective': 'Effective Sep 15, 2021', 'active': False},
            {'title': 'Statement of Work 001', 'type': 'SOW', 'effective': 'Effective Jan 10, 2022', 'active': False},
            {'title': 'Statement of Work 002', 'type': 'SOW', 'effective': 'Effective Apr 1, 2022', 'active': False},
            {'title': 'Security Addendum', 'type': 'SA', 'effective': 'Effective Feb 28, 2022', 'active': False},
            {'title': 'Renewal 2026', 'type': 'Renewal', 'effective': 'Effective Oct 1, 2026', 'active': False},
        ],
        'overview': {
            'type': 'Master Service Agreement',
            'governing_law': 'California',
            'status': 'Active',
            'contract_value': '€4.7M',
            'effective_date': 'Nov 1, 2021',
            'expiration_date': 'Oct 31, 2026',
            'auto_renewal': "Yes – 90 days' notice",
            'owning_team': 'Legal',
            'playbook': 'MSA – Standard v2.1',
        },
        'obligations': [
            {'name': 'Data Processing Compliance', 'section': 'Section 8.2', 'owner': 'Riya Shah', 'due': 'May 15, 2025', 'health': 'On Track'},
            {'name': 'Service Availability', 'section': 'Section 5.1', 'owner': 'James Lee', 'due': 'Jun 1, 2025', 'health': 'On Track'},
            {'name': 'Security Assessment', 'section': 'Section 9.3', 'owner': 'Priya Nair', 'due': 'Jun 30, 2025', 'health': 'Due Soon'},
            {'name': 'Insurance Certificates', 'section': 'Section 12.4', 'owner': 'Alex Morgan', 'due': 'Jul 15, 2025', 'health': 'On Track'},
            {'name': 'Annual Business Review', 'section': 'Section 6.5', 'owner': 'Olivia Bennett', 'due': 'Aug 1, 2025', 'health': 'Due Soon'},
        ],
        'obligations_total': 14,
        'ai_brief': {
            'summary': 'Overall MSA is standard and in institutional library with medium risk exposure.',
            'risk_level': 'High',
            'playbook_fit': 78,
            'revenue_impact': '€2.8M at risk',
            'top_risks': [
                {'label': '3 indemnity clauses above playbook', 'severity': 'High'},
                {'label': 'Limitation of liability cap misaligned', 'severity': 'High'},
                {'label': 'Auto-renewal notice window', 'severity': 'Medium'},
            ],
            'next_best_action': 'Negotiate liability cap to align with playbook standards.',
        },
    }
    return render(request, 'contracts/design_preview_relationship_detail.html', context)


@login_required
def design_preview_review_studio(request):
    context = {
        'doc': {
            'org': 'Acme Corporation',
            'title': 'Master Service Agreement',
            'draft': 'Draft v2',
            'page': 7,
            'total_pages': 34,
        },
        'clauses': [
            {
                'num': '7.2',
                'heading': 'Limitation of Liability.',
                'body': "Neither party shall be liable for any indirect, incidental, special, or consequential damages, including loss of profits or, loss, anticipated or loss of use or data, arising out of or related to this Agreement, except in the case of the receiving party's act of fraud, reckless disregard or willful misconduct, or breach of the security or data obligations. Each party's total cumulative liability shall not exceed the greater of the fees paid by Customer in the [12 months] preceding the event or [€500,000].",
                'highlighted': True,
            },
            {
                'num': '7.3',
                'heading': 'Indemnification.',
                'body': "Each party shall indemnify and hold the other harmless from and against any claims, suits or actions of third parties to the detriment of (a) such other party's IP (excluding willful IP) or (b) a breach by such other party resulting in the inadvertent or negligent disclosure of such other party's confidential information, in each case arising out of its respective or the defense. The Indemnification obligations shall survive for [24 months] after termination.",
                'highlighted': False,
            },
            {
                'num': '11.4',
                'heading': 'Data Breach Notifications.',
                'body': 'Provider will notify Customer without undue delay and in any event within [72 hours] of becoming aware of a Personal Data breach.',
                'highlighted': False,
            },
        ],
        'active_clause': {
            'ref': 'Clause 7.2: Limitation of Liability',
            'your_position': 'Liability cap at fees for 12 months of fees.',
            'counterparty_position': '€500,000 cap.',
            'playbook_guidance': 'Align with market standard. Recommend removing monetary cap or tying to at least 12 months of fees.',
            'risk_if_accepted': 'High',
            'estimated_impact': '€2.8M',
            'fallback_language': 'The total cumulative liability of each party shall not exceed the total fees paid or payable during the twelve (12) months prior to the event giving rise to the claim for direct damages.',
            'similar_accepted_count': 12,
            'similar_accepted_pct': 76,
            'similar_accepted_note': 'liability cap "12 months of fees"',
        },
        'review_intelligence': {
            'risk': 'High',
            'risk_issues': '1 issue · 2 critical',
            'playbook_compliance_pct': 72,
            'playbook_compliance_note': '12 of 16 items aligned',
            'missing_clauses': 4,
            'missing_clauses_note': 'Material gaps identified',
        },
        'approvals_required': {
            'teams': 'Legal, Finance',
            'pending': 2,
        },
    }
    return render(request, 'contracts/design_preview_review_studio.html', context)
