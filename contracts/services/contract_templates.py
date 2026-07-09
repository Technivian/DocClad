"""Merge-field substitution for ContractTemplate-based contract creation.

Templates hold raw body text with `{{field}}` tokens. render_merge_fields()
substitutes each token with the corresponding value off a Contract instance
(or blank if unset) — called once at save time in ContractCreateView, after
the form's cleaned_data has already been applied to the instance, so it
works whether the text came verbatim from a template or was hand-edited.
"""
import re

# token name -> attribute path on Contract (dotted for related lookups)
MERGE_FIELDS = {
    'title': 'title',
    'counterparty': 'counterparty',
    'value': 'value',
    'currency': 'currency',
    'governing_law': 'governing_law',
    'jurisdiction': 'jurisdiction',
    'start_date': 'start_date',
    'effective_date': 'start_date',
    'end_date': 'end_date',
    'renewal_date': 'renewal_date',
}

_TOKEN_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def _format_value(value):
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%B %d, %Y')
    return str(value)


def render_merge_fields(text, contract):
    """Replace every recognized {{token}} in `text` with `contract`'s value.

    Unrecognized tokens are left as-is rather than blanked out, so a typo'd
    field name stays visibly wrong instead of silently vanishing.
    """
    if not text:
        return text

    def _replace(match):
        token = match.group(1)
        attr = MERGE_FIELDS.get(token)
        if attr is None:
            return match.group(0)
        return _format_value(getattr(contract, attr, ''))

    return _TOKEN_RE.sub(_replace, text)
