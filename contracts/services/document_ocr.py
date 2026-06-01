from decimal import Decimal
from io import BytesIO

from contracts.models import DocumentOCRReview
from contracts.services.background_jobs import queue_background_job


TEXT_FILE_EXTENSIONS = {'.txt', '.md', '.csv', '.log', '.rtf', '.html', '.htm', '.json', '.xml'}
TEXT_MIME_PREFIXES = {'text/'}
TEXT_MIME_TYPES = {
    'application/json',
    'application/xml',
    'application/xhtml+xml',
}
PDF_EXTENSIONS = {'.pdf'}
PDF_MIME_TYPES = {'application/pdf'}
DOCX_EXTENSIONS = {'.docx'}
DOCX_MIME_TYPES = {
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def _is_text_document(document):
    mime_type = (document.mime_type or '').lower()
    file_extension = (document.file_extension or '').lower()
    if any(mime_type.startswith(prefix) for prefix in TEXT_MIME_PREFIXES):
        return True
    if mime_type in TEXT_MIME_TYPES:
        return True
    return file_extension in TEXT_FILE_EXTENSIONS


def _is_pdf_document(document):
    mime_type = (document.mime_type or '').lower()
    file_extension = (document.file_extension or '').lower()
    return mime_type in PDF_MIME_TYPES or file_extension in PDF_EXTENSIONS


def _is_docx_document(document):
    mime_type = (document.mime_type or '').lower()
    file_extension = (document.file_extension or '').lower()
    return mime_type in DOCX_MIME_TYPES or file_extension in DOCX_EXTENSIONS


def _extract_pdf_text(document):
    try:
        from pypdf import PdfReader
        document.file.open('rb')
        raw_bytes = document.file.read()
        if hasattr(document.file, 'seek'):
            document.file.seek(0)
        reader = PdfReader(BytesIO(raw_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or '')
        text = '\n'.join(pages).strip()
        confidence = Decimal('0.82') if text else Decimal('0.15')
        return text, confidence, 'pdf-extraction'
    except Exception:
        return '', Decimal('0.10'), 'manual-review'


def _extract_docx_text(document):
    try:
        import docx as python_docx
        document.file.open('rb')
        raw_bytes = document.file.read()
        if hasattr(document.file, 'seek'):
            document.file.seek(0)
        doc = python_docx.Document(BytesIO(raw_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = '\n'.join(paragraphs).strip()
        confidence = Decimal('0.90') if text else Decimal('0.15')
        return text, confidence, 'docx-extraction'
    except Exception:
        return '', Decimal('0.10'), 'manual-review'


def extract_document_text(document):
    if not document.file:
        return '', None, 'no-file'

    if _is_pdf_document(document):
        return _extract_pdf_text(document)

    if _is_docx_document(document):
        return _extract_docx_text(document)

    if not _is_text_document(document):
        return '', Decimal('0.10'), 'manual-review'

    try:
        document.file.open('rb')
        raw_bytes = document.file.read()
        document.file.seek(0)
        extracted_text = raw_bytes.decode('utf-8', errors='ignore').strip()
        confidence = Decimal('0.95') if extracted_text else Decimal('0.35')
        return extracted_text, confidence, 'text-extraction'
    except Exception:
        return '', Decimal('0.20'), 'manual-review'


def queue_document_ocr_review(document):
    extracted_text, confidence_score, source = extract_document_text(document)
    review, _ = DocumentOCRReview.objects.get_or_create(
        document=document,
        defaults={
            'organization': document.organization,
            'status': DocumentOCRReview.Status.IN_REVIEW if extracted_text else DocumentOCRReview.Status.PENDING,
            'extracted_text': extracted_text,
            'confidence_score': confidence_score,
            'source': source,
        },
    )
    if review.status == DocumentOCRReview.Status.PENDING and extracted_text:
        review.status = DocumentOCRReview.Status.IN_REVIEW
        review.extracted_text = extracted_text
        review.confidence_score = confidence_score
        review.source = source
        review.save(update_fields=['status', 'extracted_text', 'confidence_score', 'source', 'updated_at'])
    queue_background_job('process_document_ocr_reviews', organization=document.organization, payload={'document_id': document.id})
    return review


def process_pending_document_ocr_reviews(limit=50):
    from contracts.services.ai_extraction import extract_clause_spans
    processed = 0
    for review in DocumentOCRReview.objects.filter(status=DocumentOCRReview.Status.PENDING).select_related('document', 'document__organization').order_by('created_at')[:limit]:
        extracted_text, confidence_score, source = extract_document_text(review.document)
        review.extracted_text = extracted_text
        review.confidence_score = confidence_score
        review.source = source
        review.status = DocumentOCRReview.Status.IN_REVIEW if extracted_text else DocumentOCRReview.Status.PENDING
        review.save(update_fields=['extracted_text', 'confidence_score', 'source', 'status', 'updated_at'])
        if extracted_text and review.document.organization:
            try:
                extract_clause_spans(
                    extracted_text,
                    review.document.organization,
                    review.document,
                )
            except Exception:
                pass
        processed += 1
    return processed
