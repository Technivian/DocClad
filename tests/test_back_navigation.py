from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from contracts.back_navigation import ROOT_URL_NAMES, resolve_shell_back


class BackNavigationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, path, url_name):
        request = self.factory.get(path)

        class Match:
            pass

        match = Match()
        match.url_name = url_name
        match.kwargs = {}
        request.resolver_match = match
        return request

    def test_root_pages_have_no_back_link(self):
        for url_name in ('dashboard', 'repository', 'workflow_dashboard', 'dpa_review_pack_list'):
            self.assertIn(url_name, ROOT_URL_NAMES)
            self.assertIsNone(resolve_shell_back(self._request('/', url_name)))

    def test_hub_children_go_one_level_up(self):
        link = resolve_shell_back(self._request('/contracts/workflows/templates/', 'workflow_template_list'))
        self.assertEqual(link['href'], reverse('contracts:workflow_dashboard'))
        self.assertEqual(link['aria_label'], 'Back to workflows')

        link = resolve_shell_back(self._request('/contracts/documents/', 'document_list'))
        self.assertEqual(link['href'], reverse('contracts:repository'))
        self.assertNotIn('dashboard', link['href'])

        link = resolve_shell_back(self._request('/settings/profile/', 'profile'))
        self.assertEqual(link['href'], reverse('settings_hub'))
        self.assertEqual(link['aria_label'], 'Back to settings')

    def test_unknown_pages_do_not_fall_back_to_command_center(self):
        self.assertIsNone(resolve_shell_back(self._request('/contracts/unknown/', 'totally_unknown_page')))
