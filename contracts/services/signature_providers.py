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
import json
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings


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


def get_signature_provider(config: Optional[Any] = None) -> OutboundSignatureProvider:
    config = config or settings
    provider_name = str(getattr(config, 'ESIGN_PROVIDER', 'null') or 'null').strip().lower()
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
