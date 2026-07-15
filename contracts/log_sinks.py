import json
import logging
from datetime import datetime, timezone
from urllib.request import HTTPRedirectHandler, Request, build_opener

from contracts.services.outbound_urls import validate_public_https_url


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request, timeout):
    """Issue validated log-sink requests without following redirects."""
    return build_opener(_NoRedirectHandler).open(request, timeout=timeout)


class HttpJsonLogHandler(logging.Handler):
    """
    Best-effort JSON log forwarder.
    Failures are intentionally swallowed to avoid impacting request paths.
    """

    def __init__(self, sink_url: str, timeout_seconds: float = 2.0):
        super().__init__()
        self.sink_url = sink_url
        self.timeout_seconds = timeout_seconds

    def emit(self, record):
        try:
            sink_url = validate_public_https_url(self.sink_url, label='HTTP log sink URL')
            payload = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'request_id': getattr(record, 'request_id', '-'),
                'user_id': getattr(record, 'request_user_id', '-'),
                'org_id': getattr(record, 'request_org_id', '-'),
                'path': getattr(record, 'request_path', '-'),
            }
            body = json.dumps(payload).encode('utf-8')
            request = Request(
                sink_url,
                data=body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urlopen(request, timeout=self.timeout_seconds):
                pass
        except Exception:
            return
