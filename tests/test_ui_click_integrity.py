from html.parser import HTMLParser
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from contracts.models import Contract, Organization, OrganizationMembership


class _InteractiveElementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.forms = []
        self.button_actions = []
        self._current_form = None

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)

        if tag == 'a':
            href = attr_map.get('href')
            if href:
                self.links.append(href)
            return

        if tag == 'form':
            self._current_form = {
                'action': attr_map.get('action', ''),
                'method': attr_map.get('method', 'get').lower(),
                'has_csrf': False,
                'submit_controls': 0,
            }
            return

        if self._current_form and tag == 'input':
            input_name = attr_map.get('name', '')
            input_type = attr_map.get('type', '').lower()
            if input_name == 'csrfmiddlewaretoken':
                self._current_form['has_csrf'] = True
            if input_type == 'submit':
                self._current_form['submit_controls'] += 1
            return

        if tag == 'button':
            button_type = attr_map.get('type', 'submit').lower()
            formaction = attr_map.get('formaction')
            if formaction:
                self.button_actions.append(formaction)
            if self._current_form and button_type == 'submit':
                self._current_form['submit_controls'] += 1

    def handle_endtag(self, tag):
        if tag == 'form' and self._current_form:
            self.forms.append(self._current_form)
            self._current_form = None


class UIButtonAndFlowIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='uiowner',
            password='testpass123',
            email='uiowner@example.com',
        )
        self.organization = Organization.objects.create(name='UI Test Org', slug='ui-test-org')
        self.organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        self.organization.save(update_fields=['workspace_mode'])
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='UI Integrity Contract',
            content='Contract used for link/form target checks.',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )
        self.client.login(username='uiowner', password='testpass123')

    def _normalize_internal_path(self, raw_url, current_path):
        if not raw_url:
            return current_path

        parsed = urlparse(raw_url)
        if parsed.scheme or parsed.netloc:
            return None

        if raw_url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            return None

        if parsed.path.startswith(('/static/', '/media/')):
            return None

        if not parsed.path:
            return current_path

        return parsed.path

    def _assert_resolves(self, path, source_page, raw_target):
        try:
            resolve(path)
        except Resolver404:
            self.fail(f'Unresolvable target on {source_page}: {raw_target}')

    def test_click_targets_and_forms_are_wired_on_core_pages(self):
        expected_back_links = {
            reverse('contracts:contract_create'): reverse('contracts:repository'),
            reverse('contracts:contract_template_picker'): reverse('contracts:repository'),
            reverse('contracts:upload_signed_contract'): reverse('contracts:repository'),
            reverse('contracts:contract_update', kwargs={'pk': self.contract.pk}): reverse(
                'contracts:contract_detail', kwargs={'pk': self.contract.pk}
            ),
            reverse('contracts:contract_list'): reverse('contracts:repository'),
            reverse('contracts:document_list'): reverse('contracts:repository'),
            reverse('contracts:deadline_list'): reverse('contracts:obligations_workspace'),
            reverse('contracts:legal_task_kanban'): reverse('contracts:obligations_workspace'),
            reverse('contracts:risk_log_list'): reverse('contracts:privacy_dashboard'),
            reverse('contracts:budget_list'): reverse('contracts:reports_dashboard'),
            reverse('contracts:trademark_request_list'): reverse('contracts:repository'),
            reverse('contracts:due_diligence_list'): reverse('contracts:repository'),
            reverse('contracts:approval_request_list'): reverse('contracts:workflow_dashboard'),
            reverse('contracts:reports_dashboard'): reverse('settings_hub'),
            reverse('contracts:organization_team'): reverse('settings_hub'),
            reverse('contracts:notification_list'): reverse('settings_hub'),
            reverse('contracts:privacy_dashboard'): reverse('settings_hub'),
        }
        pages_without_back = {
            reverse('dashboard'),
            reverse('contracts:repository'),
            reverse('contracts:workflow_dashboard'),
            reverse('contracts:global_search'),
        }

        pages = [
            reverse('dashboard'),
            reverse('contracts:contract_list'),
            reverse('contracts:global_search'),
            reverse('contracts:document_list'),
            reverse('contracts:deadline_list'),
            reverse('contracts:legal_task_kanban'),
            reverse('contracts:risk_log_list'),
            reverse('contracts:budget_list'),
            reverse('contracts:trademark_request_list'),
            reverse('contracts:due_diligence_list'),
            reverse('contracts:workflow_dashboard'),
            reverse('contracts:approval_request_list'),
            reverse('contracts:repository'),
            reverse('contracts:reports_dashboard'),
            reverse('contracts:organization_team'),
            reverse('contracts:notification_list'),
            reverse('contracts:privacy_dashboard'),
            reverse('contracts:contract_create'),
            reverse('contracts:contract_template_picker'),
            reverse('contracts:upload_signed_contract'),
            reverse('contracts:contract_update', kwargs={'pk': self.contract.pk}),
        ]

        for page in pages:
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200, msg=f'Page failed: {page}')
            content = response.content.decode('utf-8')
            self.assertIn('class="topbar-page-title-row"', content)
            self.assertNotIn('<span>Back</span>', content)
            if page in pages_without_back:
                self.assertNotIn('class="topbar-back-link"', content)
            else:
                expected_href = expected_back_links[page]
                self.assertIn(f'<a href="{expected_href}" class="topbar-back-link"', content)
                self.assertNotIn(f'<a href="{reverse("dashboard")}" class="topbar-back-link"', content)

            parser = _InteractiveElementParser()
            parser.feed(content)

            for href in parser.links:
                target_path = self._normalize_internal_path(href, page)
                if not target_path:
                    continue
                self._assert_resolves(target_path, page, href)

            for button_action in parser.button_actions:
                target_path = self._normalize_internal_path(button_action, page)
                if not target_path:
                    continue
                self._assert_resolves(target_path, page, button_action)

            for form in parser.forms:
                action = form['action']
                target_path = self._normalize_internal_path(action, page)
                if target_path:
                    self._assert_resolves(target_path, page, action or '[current-page-action]')

                if form['method'] == 'post' and form['submit_controls'] > 0:
                    self.assertTrue(
                        form['has_csrf'],
                        msg=f'Missing CSRF token in POST form on {page} (action: {action or page})',
                    )

    def test_case_flow_semantics_on_high_traffic_pages(self):
        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        # setUp's contract is DRAFT (not PENDING/IN_REVIEW), so the dashboard
        # should show the current zero-state hero copy rather than a bare "0".
        self.assertContains(dashboard_response, 'dc-ds-metric__value--clear')
        self.assertContains(dashboard_response, 'Top priority')
        self.assertContains(dashboard_response, 'Action queue')

        list_response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Contract Workspace')
        self.assertContains(list_response, 'Search active contract work...')
        # The page header no longer duplicates the create CTA ("New Case"
        # pointed at the same route); the top bar carries the single
        # "New Contract" entry point on every page.
        self.assertContains(list_response, 'New Contract')

        detail_response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': Contract.objects.first().pk}))
        self.assertEqual(detail_response.status_code, 200)
        # Overview shows the lifecycle track; Workflow tab hosts the machinery.
        self.assertContains(detail_response, 'Contract lifecycle')
        self.assertNotContains(detail_response, 'View full workflow')
        self.assertContains(detail_response, 'Contract details')
        self.assertContains(detail_response, 'Audit trail')
        self.assertNotContains(detail_response, 'contract-workflow-reveal')
        tab_labels = [tab['label'] for tab in detail_response.context['workspace_tabs']]
        self.assertNotIn('Review', tab_labels)
        self.assertNotIn('Activity', tab_labels)
        self.assertIn('Audit trail', tab_labels)
        self.assertIn('Workflow', tab_labels)
        search_response = self.client.get(reverse('contracts:global_search'), {'q': 'UI Integrity'})
        self.assertEqual(search_response.status_code, 200)
        # Sub-block C: removed a redundant sr-only duplicate of this
        # description that had drifted out of sync with the visible copy
        # (it still said "cases, case matters" after the visible text was
        # updated to "contracts, matters") — asserting on the one remaining,
        # accurate copy instead of the stale hidden duplicate.
        self.assertContains(search_response, 'Search across contracts, matters, documents, and task signals')
        self.assertContains(search_response, 'Cases (1)')
