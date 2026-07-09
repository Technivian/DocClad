"""Template filters for the DPA workflow builder — a single generic dict
lookup, needed because Django templates can't index a dict by a loop
variable (`{{ errors.field.key }}` looks up a literal "field" key, not the
value of the `field` template variable).
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        return None


@register.filter
def only_type(fields, field_type):
    """Splits a FieldDefinition list by field_type — used to separate the
    yes/no "AI Smart Questions" toggles from their supporting detail
    fields (transfer mechanism, breach window, DPO contact) within the
    same PRIVACY_QUESTIONS section."""
    return [f for f in fields or [] if f.field_type == field_type]


@register.filter
def exclude_type(fields, field_type):
    return [f for f in fields or [] if f.field_type != field_type]
