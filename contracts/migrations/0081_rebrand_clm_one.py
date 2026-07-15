from django.db import migrations


TEXT_FIELD_TYPES = {'CharField', 'TextField', 'EmailField', 'URLField', 'SlugField', 'JSONField'}
SKIP_MODELS = {'AuditLog'}
SKIP_FIELD_PARTS = {'secret', 'token', 'password', 'hash', 'certificate', 'private_key'}


def _replace_brand(value):
    old_lower = 'doc' + 'clad'
    old_camel = 'Doc' + 'Clad'
    old_title = 'Doc' + 'clad'
    old_upper = old_lower.upper()

    if isinstance(value, str):
        return (
            value.replace(old_camel, 'CLM One')
            .replace(old_title, 'CLMOne')
            .replace(old_upper, 'CLMONE')
            .replace(old_lower, 'clmone')
        )
    if isinstance(value, list):
        return [_replace_brand(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_brand(item) for key, item in value.items()}
    return value


def rebrand_persisted_content(apps, schema_editor):
    app_config = apps.get_app_config('contracts')
    models = [model for model in app_config.get_models() if model.__name__ not in SKIP_MODELS]
    models.append(apps.get_model('auth', 'User'))

    for model in models:
        fields = [
            field
            for field in model._meta.local_fields
            if field.get_internal_type() in TEXT_FIELD_TYPES
            and not any(part in field.name.lower() for part in SKIP_FIELD_PARTS)
        ]
        if not fields:
            continue

        field_names = [field.name for field in fields]
        for instance in model.objects.all().iterator(chunk_size=500):
            changed = []
            for field_name in field_names:
                previous = getattr(instance, field_name)
                updated = _replace_brand(previous)
                if updated != previous:
                    setattr(instance, field_name, updated)
                    changed.append(field_name)
            if changed:
                instance.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0080_govern_ai_clause_extraction'),
    ]

    operations = [
        migrations.RunPython(rebrand_persisted_content, migrations.RunPython.noop),
    ]
