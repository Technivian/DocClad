"""Outbound e-signature providers.

Historically the platform could only *reconcile* inbound provider webhooks
(see ``esign.py``) — there was no way to actually send a document out for
signature. This module adds a small provider abstraction for the outbound
direction.

- ``NullSignatureProvider`` is the default: it simulates a send (no network),
  so the signing flow works end-to-end in development, demos and tests without
  any provider credentials.
- ``HttpSignatureProvider`` posts to a configurable e-sign gateway (DocuSign /
  Adobe Sign / an internal relay), selected via the ``ESIGN_PROVIDER`` setting.

Resolve the configured provider with ``get_signature_provider()``.
"""

from __future__ import annotations

import base64
from io import BytesIO
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from django.conf import settings
from pypdf import PdfReader


class SignatureProviderError(RuntimeError):
    """Raised when an outbound provider fails to accept a send request."""


@dataclass
class SendResult:
    """Outcome of dispatching a signature request to a provider."""

    external_id: str
    signing_url: str = ''
    provider: str = ''
    raw: dict = field(default_factory=dict)


class OutboundSignatureProvider(Protocol):
    name: str

    def send(self, signature_request) -> SendResult:
        ...


class NullSignatureProvider:
    """Default provider — simulates a send without any external call.

    The external reference is deterministic so retries are idempotent and the
    value is easy to assert in tests.
    """

    name = 'null'

    def send(self, signature_request) -> SendResult:
        external_id = f'null-{signature_request.organization_id}-{signature_request.id}'
        signing_url = f'/contracts/signatures/{signature_request.id}/'
        return SendResult(
            external_id=external_id,
            signing_url=signing_url,
            provider=self.name,
            raw={'simulated': True},
        )


class HttpSignatureProvider:
    """Generic outbound gateway: POST a JSON envelope to a configured endpoint.

    Works with any e-sign service fronted by an HTTP relay that returns an
    ``external_id`` (and optionally a ``signing_url``). Network shape mirrors
    the existing Salesforce integration (urllib, bounded timeout).
    """

    name = 'http'

    def __init__(self, base_url: str, api_key: str, *, timeout: int = 10, opener=None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        # Injectable for tests; defaults to urllib.
        self._opener = opener or urllib_request.urlopen

    def send(self, signature_request) -> SendResult:
        if not self.base_url:
            raise SignatureProviderError('ESIGN_API_BASE is not configured.')
        payload = {
            'reference': f'{signature_request.organization_id}:{signature_request.id}',
            'signer_name': signature_request.signer_name,
            'signer_email': signature_request.signer_email,
            'signer_role': signature_request.signer_role,
            'contract_id': signature_request.contract_id,
        }
        body = json.dumps(payload).encode('utf-8')
        req = urllib_request.Request(
            f'{self.base_url}/envelopes',
            data=body,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
            },
        )
        try:
            with self._opener(req, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode('utf-8') or '{}')
        except urllib_error.URLError as exc:
            raise SignatureProviderError(f'E-sign gateway request failed: {exc}') from exc
        except (ValueError, TypeError) as exc:
            raise SignatureProviderError(f'E-sign gateway returned an invalid response: {exc}') from exc

        external_id = str(raw.get('external_id') or raw.get('envelope_id') or '').strip()
        if not external_id:
            raise SignatureProviderError('E-sign gateway response is missing an external id.')
        return SendResult(
            external_id=external_id,
            signing_url=str(raw.get('signing_url') or '').strip(),
            provider=self.name,
            raw=raw,
        )


class DocuSignSignatureProvider:
    """DocuSign eSignature REST API provider.

    Creates an envelope (status="sent") for the signature request's linked
    document and returns the DocuSign ``envelopeId`` as the external reference.
    DocuSign emails the signer; status then flows back through the existing
    inbound webhook reconciliation (PENDING -> SENT -> ... -> SIGNED).

    Operational setup required (cannot be done from code):
      - A DocuSign account; ``ESIGN_DOCUSIGN_ACCOUNT_ID`` and
        ``ESIGN_DOCUSIGN_BASE_URI`` (e.g. https://demo.docusign.net/restapi).
      - A valid OAuth access token in ``ESIGN_DOCUSIGN_ACCESS_TOKEN``, refreshed
        out of band (JWT grant tokens expire ~8h).
      - A document attached to the SignatureRequest (the file to sign).
    """

    name = 'docusign'

    def __init__(self, base_uri: str, account_id: str, access_token: str, *, timeout: int = 15, opener=None):
        self.base_uri = base_uri.rstrip('/')
        self.account_id = account_id
        self.access_token = access_token
        self.timeout = timeout
        self._opener = opener or urllib_request.urlopen

    def _document_payload(self, signature_request) -> dict:
        document = getattr(signature_request, 'document', None)
        file_field = getattr(document, 'file', None) if document else None
        if not file_field:
            raise SignatureProviderError('DocuSign send requires a document attached to the signature request.')
        try:
            file_field.open('rb')
            content = file_field.read()
        finally:
            try:
                file_field.close()
            except Exception:
                pass
        extension = (getattr(document, 'mime_type', '') or '').split('/')[-1] or 'pdf'
        return {
            'documentBase64': base64.b64encode(content).decode('ascii'),
            'documentId': '1',
            'name': document.title or 'Contract document',
            'fileExtension': extension,
        }

    def send(self, signature_request) -> SendResult:
        if not (self.base_uri and self.account_id and self.access_token):
            raise SignatureProviderError('DocuSign is not fully configured (base URI, account id, access token).')
        envelope = {
            'emailSubject': f'Signature requested: {signature_request.contract}',
            'status': 'sent',
            'documents': [self._document_payload(signature_request)],
            'recipients': {
                'signers': [{
                    'email': signature_request.signer_email,
                    'name': signature_request.signer_name,
                    'recipientId': '1',
                    'routingOrder': str(signature_request.order or 1),
                }],
            },
        }
        body = json.dumps(envelope).encode('utf-8')
        url = f'{self.base_uri}/v2.1/accounts/{self.account_id}/envelopes'
        req = urllib_request.Request(
            url,
            data=body,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}',
            },
        )
        try:
            with self._opener(req, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode('utf-8') or '{}')
        except urllib_error.URLError as exc:
            raise SignatureProviderError(f'DocuSign request failed: {exc}') from exc
        except (ValueError, TypeError) as exc:
            raise SignatureProviderError(f'DocuSign returned an invalid response: {exc}') from exc

        external_id = str(raw.get('envelopeId') or '').strip()
        if not external_id:
            raise SignatureProviderError('DocuSign response is missing an envelopeId.')
        return SendResult(external_id=external_id, signing_url='', provider=self.name, raw=raw)


class DocumensoSignatureProvider:
    """Documenso V2 e-signature provider.

    Sends a PDF through the current envelope API. Documenso emails the signer
    and returns a direct signing URL. Status can be reconciled through either a
    team webhook or the explicit refresh action available for free accounts.

    Set ESIGN_PROVIDER=documenso plus ESIGN_DOCUMENSO_API_KEY.
    """
    name = 'documenso'

    def __init__(self, api_key: str, base_url: str = 'https://app.documenso.com', *, timeout: int = 15, opener=None):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._opener = opener or urllib_request.urlopen

    def _api_url(self, path: str) -> str:
        base = self.base_url.rstrip('/')
        if not base.endswith('/api/v2'):
            base = f'{base}/api/v2'
        return f'{base}/{path.lstrip("/")}'

    def _read_pdf(self, signature_request) -> tuple[bytes, str, int]:
        document = getattr(signature_request, 'document', None)
        file_field = getattr(document, 'file', None) if document else None
        if not file_field:
            raise SignatureProviderError('Documenso send requires a PDF document attached to the signature request.')

        try:
            file_field.open('rb')
            file_content = file_field.read()
        except Exception as exc:
            raise SignatureProviderError(f'Could not read document file: {exc}') from exc
        finally:
            try:
                file_field.close()
            except Exception:
                pass

        if not file_content.startswith(b'%PDF'):
            raise SignatureProviderError('Documenso only accepts PDF documents.')

        filename = os.path.basename(getattr(file_field, 'name', '') or '') or 'contract.pdf'
        if not filename.lower().endswith('.pdf'):
            filename = f'{filename}.pdf'

        page_number = 1
        try:
            page_number = max(1, len(PdfReader(BytesIO(file_content)).pages))
        except Exception:
            # Documenso performs the authoritative PDF validation. Keeping page
            # one as a fallback gives the provider a useful error for damaged
            # files without leaking document contents into logs.
            page_number = 1
        return file_content, filename, page_number

    def _open_json(self, request, *, action: str) -> dict:
        try:
            with self._opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8') or '{}')
        except urllib_error.HTTPError as exc:
            raise SignatureProviderError(f'Documenso {action} failed with HTTP {exc.code}.') from exc
        except urllib_error.URLError as exc:
            raise SignatureProviderError(f'Documenso {action} failed: {exc}') from exc
        except (ValueError, TypeError) as exc:
            raise SignatureProviderError(f'Documenso returned an invalid response while attempting to {action}.') from exc

    def send(self, signature_request) -> SendResult:
        if not self.api_key:
            raise SignatureProviderError('ESIGN_DOCUMENSO_API_KEY is not configured.')

        file_content, filename, page_number = self._read_pdf(signature_request)
        title = f'Signature requested: {signature_request.contract}'
        external_id = f'clmone-{signature_request.organization_id}-{signature_request.id}'
        payload = {
            'type': 'DOCUMENT',
            'title': title,
            'externalId': external_id,
            'recipients': [{
                'name': signature_request.signer_name,
                'email': signature_request.signer_email,
                'role': 'SIGNER',
                'signingOrder': signature_request.order or 1,
                'fields': [
                    {
                        'identifier': 0,
                        'type': 'NAME',
                        'page': page_number,
                        'positionX': 10,
                        'positionY': 82,
                        'width': 30,
                        'height': 3,
                    },
                    {
                        'identifier': 0,
                        'type': 'SIGNATURE',
                        'page': page_number,
                        'positionX': 10,
                        'positionY': 86,
                        'width': 30,
                        'height': 5,
                    },
                    {
                        'identifier': 0,
                        'type': 'DATE',
                        'page': page_number,
                        'positionX': 50,
                        'positionY': 86,
                        'width': 20,
                        'height': 3,
                    },
                ],
            }],
            'meta': {
                'subject': title,
                'message': 'Please review and sign the attached agreement.',
            },
        }

        boundary = f'----CLMOneDocumenso{uuid4().hex}'
        boundary_bytes = boundary.encode('ascii')
        body = b''.join([
            b'--' + boundary_bytes + b'\r\n'
            b'Content-Disposition: form-data; name="payload"\r\n'
            b'Content-Type: application/json\r\n\r\n'
            + json.dumps(payload).encode('utf-8') + b'\r\n',
            b'--' + boundary_bytes + b'\r\n'
            + f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode('utf-8')
            + b'Content-Type: application/pdf\r\n\r\n'
            + file_content + b'\r\n',
            b'--' + boundary_bytes + b'--\r\n',
        ])

        req = urllib_request.Request(
            self._api_url('/envelope/create'),
            data=body,
            method='POST',
            headers={
                'Authorization': self.api_key,
                'Content-Type': f'multipart/form-data; boundary={boundary}',
            },
        )
        raw = self._open_json(req, action='document creation')

        doc_id = str(raw.get('id') or '').strip()
        if not doc_id:
            raise SignatureProviderError('Documenso response is missing an envelope id.')

        distribute_body = json.dumps({
            'envelopeId': doc_id,
            'meta': payload['meta'],
        }).encode('utf-8')
        send_req = urllib_request.Request(
            self._api_url('/envelope/distribute'),
            data=distribute_body,
            method='POST',
            headers={
                'Authorization': self.api_key,
                'Content-Type': 'application/json',
            },
        )
        send_raw = self._open_json(send_req, action='document distribution')

        recipients = send_raw.get('recipients') or []
        matching_recipient = next(
            (
                recipient for recipient in recipients
                if str(recipient.get('email') or '').lower() == signature_request.signer_email.lower()
            ),
            recipients[0] if recipients else {},
        )
        signing_url = str(matching_recipient.get('signingUrl') or '').strip()

        return SendResult(
            external_id=doc_id,
            signing_url=signing_url,
            provider=self.name,
            raw={**raw, **send_raw},
        )

    def fetch_status(self, external_id: str) -> dict:
        """Return the current envelope state for webhook-free free accounts."""
        envelope_id = str(external_id or '').strip()
        if not envelope_id:
            raise SignatureProviderError('Documenso status refresh requires an envelope id.')
        req = urllib_request.Request(
            self._api_url(f'/envelope/{envelope_id}'),
            method='GET',
            headers={'Authorization': self.api_key},
        )
        return self._open_json(req, action='status refresh')


def get_signature_provider(config: Optional[Any] = None) -> OutboundSignatureProvider:
    config = config or settings
    provider_name = str(getattr(config, 'ESIGN_PROVIDER', 'null') or 'null').strip().lower()
    if provider_name == 'documenso':
        return DocumensoSignatureProvider(
            api_key=str(getattr(config, 'ESIGN_DOCUMENSO_API_KEY', '') or ''),
            base_url=str(getattr(config, 'ESIGN_DOCUMENSO_BASE_URL', 'https://app.documenso.com') or 'https://app.documenso.com'),
            timeout=int(getattr(config, 'ESIGN_API_TIMEOUT_SECONDS', 15)),
        )
    if provider_name == 'docusign':
        return DocuSignSignatureProvider(
            base_uri=str(getattr(config, 'ESIGN_DOCUSIGN_BASE_URI', '') or ''),
            account_id=str(getattr(config, 'ESIGN_DOCUSIGN_ACCOUNT_ID', '') or ''),
            access_token=str(getattr(config, 'ESIGN_DOCUSIGN_ACCESS_TOKEN', '') or ''),
            timeout=int(getattr(config, 'ESIGN_API_TIMEOUT_SECONDS', 15)),
        )
    if provider_name == 'http':
        return HttpSignatureProvider(
            base_url=str(getattr(config, 'ESIGN_API_BASE', '') or ''),
            api_key=str(getattr(config, 'ESIGN_API_KEY', '') or ''),
            timeout=int(getattr(config, 'ESIGN_API_TIMEOUT_SECONDS', 10)),
        )
    return NullSignatureProvider()
