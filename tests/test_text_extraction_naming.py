"""Phase 4H — truthful text-extraction naming (no image-OCR claims)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    Document,
    DocumentOCRReview,
    Organization,
    OrganizationMembership,
)
from contracts.services.document_ocr import extract_document_text

User = get_user_model()
PW = 'StrongPw!123'


def _org():
    return Organization.objects.create(name='Tx Org', slug='tx-org')


def _doc(org, name, content=b'data', mime='', ext=''):
    d = Document(organization=org, title=name, mime_type=mime)
    d.file = SimpleUploadedFile(name, content, content_type=mime or 'application/octet-stream')
    d.save()
    return d


class ExtractionRoutingTests(TestCase):
    def setUp(self):
        self.org = _org()

    def test_text_file_extracted(self):
        d = _doc(self.org, 'note.txt', b'hello contract text', mime='text/plain')
        text, _conf, source = extract_document_text(d)
        self.assertEqual(text, 'hello contract text')
        self.assertEqual(source, 'text-extraction')

    def test_empty_text_routes_manual_review(self):
        d = _doc(self.org, 'empty.txt', b'   ', mime='text/plain')
        text, _conf, source = extract_document_text(d)
        self.assertEqual(text, '')
        self.assertTrue(source.startswith('manual-review'))

    def test_unsupported_file_routes_manual_review(self):
        d = _doc(self.org, 'pic.png', b'\x89PNG', mime='image/png')
        text, _conf, source = extract_document_text(d)
        self.assertEqual(text, '')
        self.assertEqual(source, 'manual-review')

    def test_scanned_image_pdf_routes_manual_review(self):
        d = _doc(self.org, 'scan.pdf', b'%PDF-1.4 fake', mime='application/pdf')
        fake_page = MagicMock()
        fake_page.extract_text.return_value = ''  # image-only -> no text
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]
        with patch('pypdf.PdfReader', return_value=fake_reader):
            text, _conf, source = extract_document_text(d)
        self.assertEqual(text, '')
        self.assertEqual(source, 'manual-review-image-pdf')

    def test_text_pdf_extracted(self):
        d = _doc(self.org, 'doc.pdf', b'%PDF-1.4 fake', mime='application/pdf')
        fake_page = MagicMock()
        fake_page.extract_text.return_value = 'contract clause text'
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]
        with patch('pypdf.PdfReader', return_value=fake_reader):
            text, _conf, source = extract_document_text(d)
        self.assertEqual(text, 'contract clause text')
        self.assertEqual(source, 'pdf-extraction')

    def test_docx_extracted(self):
        d = _doc(self.org, 'doc.docx',
                 mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        para = MagicMock(); para.text = 'word body'
        fake_docx = MagicMock(); fake_docx.paragraphs = [para]
        with patch('docx.Document', return_value=fake_docx):
            text, _conf, source = extract_document_text(d)
        self.assertEqual(text, 'word body')
        self.assertEqual(source, 'docx-extraction')


class ExtractionReasonTests(TestCase):
    def test_image_pdf_reason_mentions_scanned_not_ocr_success(self):
        review = DocumentOCRReview(source='manual-review-image-pdf')
        self.assertTrue(review.needs_manual_review)
        reason = review.extraction_reason.lower()
        self.assertIn('manual review', reason)
        self.assertIn('image', reason)
        self.assertNotIn('successfully', reason)

    def test_text_pdf_reason_not_manual(self):
        review = DocumentOCRReview(source='pdf-extraction')
        self.assertFalse(review.needs_manual_review)


class TerminologyTests(TestCase):
    def setUp(self):
        self.org = _org()
        self.user = User.objects.create_user(username='u', password=PW)
        OrganizationMembership.objects.create(user=self.user, organization=self.org,
                                              role=OrganizationMembership.Role.OWNER, is_active=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_queue_page_uses_text_extraction_terminology(self):
        resp = self.client.get(reverse('contracts:document_ocr_queue'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Text Extraction', body)
        # No user-facing claim of OCR in the page heading/title.
        self.assertNotIn('OCR Queue', body)
