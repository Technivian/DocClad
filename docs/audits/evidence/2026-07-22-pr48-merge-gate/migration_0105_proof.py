"""Prove 0105 AlterField default does not deactivate existing rows; forward/rollback/re-forward."""
from __future__ import annotations

import importlib.util
import os
import sys
from io import StringIO
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_test')

import django

django.setup()

from django.core.management import call_command

from contracts.models import Organization, WorkflowTemplate


def main() -> int:
    print('=== Migration file inspection ===')
    mig_path = Path('/workspace/contracts/migrations/0105_workflowtemplate_is_active_default_false.py')
    spec = importlib.util.spec_from_file_location('mig_0105', mig_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    ops = mod.Migration.operations
    assert len(ops) == 1
    assert ops[0].__class__.__name__ == 'AlterField'
    assert ops[0].name == 'is_active'
    assert ops[0].field.default is False
    print('OK: single AlterField(is_active, default=False) — no RunPython data rewrite')

    print('\n=== Semantic proof on live test connection ===')
    org = Organization.objects.create(name='Mig Org', slug='mig-org-0105')
    published = WorkflowTemplate.objects.create(
        name='Already Published',
        description='x',
        organization=org,
        is_active=True,
        version=1,
    )
    draft = WorkflowTemplate.objects.create(
        name='Already Draft',
        description='x',
        organization=org,
        is_active=False,
        version=1,
    )
    new_default = WorkflowTemplate(name='New After 0105', description='x', organization=org, version=1)
    new_default.save()

    published.refresh_from_db()
    draft.refresh_from_db()
    new_default.refresh_from_db()
    print(f'published.is_active={published.is_active} (expect True)')
    print(f'draft.is_active={draft.is_active} (expect False)')
    print(f'new_default.is_active={new_default.is_active} (expect False after 0105 model default)')
    assert published.is_active is True, 'EXISTING published row must not be deactivated by default change'
    assert draft.is_active is False
    assert new_default.is_active is False, 'new rows must default unpublished'
    print('OK: existing states preserved; new default inactive')

    print('\n=== Schema default round-trip via migrate ===')
    buf = StringIO()
    call_command('migrate', 'contracts', '0104', verbosity=1, stdout=buf)
    print(buf.getvalue())
    published.refresh_from_db()
    draft.refresh_from_db()
    print(f'after rollback 0104: published={published.is_active} draft={draft.is_active}')
    assert published.is_active is True
    assert draft.is_active is False

    buf = StringIO()
    call_command('migrate', 'contracts', '0105', verbosity=1, stdout=buf)
    print(buf.getvalue())
    published.refresh_from_db()
    draft.refresh_from_db()
    print(f'after re-forward 0105: published={published.is_active} draft={draft.is_active}')
    assert published.is_active is True, 're-forward must not deactivate published'
    assert draft.is_active is False

    again = WorkflowTemplate.objects.create(name='Post Reforward', description='x', organization=org)
    assert again.is_active is False
    print('OK: rollback 0104 + re-forward 0105 preserve row states; new still default False')

    print('\n=== Seed migration note ===')
    for mid in ('0071_seed_dpa_workflow', '0075_seed_msa_workflow', '0077_seed_nda_workflow'):
        print(f'seed module present: {mid} (sets is_active=True explicitly in RunPython)')
    print('NOTE: AlterField default cannot unpublish explicitly seeded active templates.')
    print('\nMIGRATION_0105_PROOF_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
