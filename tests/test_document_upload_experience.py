from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from contracts.forms import DocumentForm
from contracts.models import Document, Organization, OrganizationMembership


class DocumentUploadExperienceFormTests(SimpleTestCase):
    def test_new_document_form_requires_a_deliberate_type_choice(self):
        form = DocumentForm()

        self.assertEqual(form['document_type'].value(), '')
        self.assertEqual(form.fields['document_type'].choices[0], ('', 'Select document type'))
        self.assertEqual(form['status'].value(), Document.Status.DRAFT)


class DocumentUploadExperienceViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='document-uploader', password='testpass123')
        self.organization = Organization.objects.create(name='Upload Co', slug='upload-co')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_upload_page_is_file_first_with_compact_confirmation(self):
        response = self.client.get(reverse('contracts:document_create'))

        self.assertContains(response, 'Drop a document here, or choose a file')
        self.assertContains(response, 'Confirm document details')
        self.assertContains(response, 'Advanced details')
        self.assertContains(response, 'Saved as Draft')
        self.assertContains(response, 'data-confidence="document-type"')
        self.assertNotContains(response, 'Comma-separated tags')
