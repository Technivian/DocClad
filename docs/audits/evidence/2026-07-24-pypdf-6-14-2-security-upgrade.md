# pypdf 6.14.2 security upgrade

## Scope

This change upgrades the pinned runtime dependency from `pypdf==6.13.3` to
`pypdf==6.14.2`. It contains no PAR-EXC authorization change, feature-flag
change, canonical-read implementation, operator-window execution, permission
change, or data repair.

`requirements/runtime.txt` is the repository's Python runtime dependency
manifest and provides the exact production pin. The tracked `uv.lock` is not a
resolved dependency lockfile (it contains only a format header), so there is no
Python lock entry to update. No substitute lockfile is introduced in this
security-only change.

## Compatibility verification

The application uses `pypdf.PdfReader` for PDF text extraction. The focused
PDF extraction and upload tests exercise normal extraction and malformed-PDF
fallback behaviour. Django system checks and the cross-tenant regression suite
also run to confirm that this dependency-only patch does not alter application
configuration or tenant isolation.

The upgrade stays within the same `pypdf` major version and changes no
application call sites.

## Security verification

Run `pip-audit --disable-pip --no-deps -r requirements/runtime.txt` after
installing the updated pin. The scan is expected to clear the advisories that
apply to `pypdf==6.13.3`.

## Rollback

If a verified compatibility regression is found, revert this security PR to
restore the prior dependency manifest. That rollback intentionally restores a
known-vulnerable version and is therefore a temporary containment measure only:
disable the affected PDF processing path as appropriate, document the incident,
and ship a corrected secure patch before re-enabling normal processing.
