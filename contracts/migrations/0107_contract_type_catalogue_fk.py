# PAR-CORE-002 — Contract Type catalogue FK + truthful backfill (G-DOM-02).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ENUM_ROWS = [
    ('NDA', 'Non-Disclosure Agreement'),
    ('NON_COMPETE', 'Non-Compete / Non-Solicitation Agreement'),
    ('MSA', 'Master Service Agreement'),
    ('SOW', 'Statement of Work'),
    ('SUBCONTRACTOR_SOW', 'Subcontractor SOW Agreement'),
    ('CONSULTING', 'Consulting / Independent Contractor Agreement'),
    ('EMPLOYMENT', 'Employment Agreement'),
    ('LEASE', 'Lease Agreement'),
    ('LICENSE', 'License Agreement'),
    ('SAAS', 'SaaS Agreement'),
    ('TERMS_OF_SERVICE', 'Terms of Service / Terms & Conditions'),
    ('VENDOR', 'Vendor Agreement'),
    ('PURCHASE_ORDER', 'Purchase Order'),
    ('ORDER_CONFIRMATION', 'Order Confirmation'),
    ('PARTNERSHIP', 'Partnership Agreement'),
    ('RESELLER', 'Referral / Reseller / Channel Partner Agreement'),
    ('SETTLEMENT', 'Settlement Agreement'),
    ('AMENDMENT', 'Amendment'),
    ('DPA', 'Data Processing Agreement'),
    ('BAA', 'Business Associate Agreement (BAA)'),
    ('OTHER', 'Other'),
]

LEGACY_ALIASES = {
    'SERVICE': 'SOW',
    'SERVICES': 'SOW',
    'SUPPLIER': 'VENDOR',
    'SUPPLIER_AGREEMENT': 'VENDOR',
    'ADDENDUM': 'AMENDMENT',
}


def forwards_seed_and_backfill(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    Contract = apps.get_model('contracts', 'Contract')

    catalogue_by_code = {}
    for code, label in ENUM_ROWS:
        row, _ = ContractType.objects.get_or_create(
            code=code,
            defaults={'name': label, 'is_active': True},
        )
        catalogue_by_code[code] = row.pk

    other_pk = catalogue_by_code['OTHER']
    valid_codes = set(catalogue_by_code)

    for contract in Contract.objects.all().iterator():
        raw = (contract.contract_type or '').strip().upper()
        mapped = LEGACY_ALIASES.get(raw, raw)
        if mapped not in valid_codes:
            mapped = 'OTHER'
        cat_pk = catalogue_by_code.get(mapped, other_pk)
        updates = {'contract_type_catalogue_id': cat_pk}
        if mapped != raw and raw:
            updates['contract_type'] = mapped
        Contract.objects.filter(pk=contract.pk).update(**updates)


def backwards_clear_catalogue_fk(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.all().update(contract_type_catalogue_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0106_contract_record_provenance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='contract_type_catalogue',
            field=models.ForeignKey(
                blank=True,
                help_text='Canonical governed Contract Type catalogue row (PAR-CORE-002).',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contract_records',
                to='contracts.contracttype',
            ),
        ),
        migrations.AlterField(
            model_name='contract',
            name='contract_type',
            field=models.CharField(
                choices=ENUM_ROWS,
                default='OTHER',
                help_text='Transitional denormalized code; canonical type is contract_type_catalogue.',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='contracttype',
            name='code',
            field=models.CharField(help_text='Stable type code, e.g. DPA', max_length=20, unique=True),
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['organization', 'contract_type_catalogue'], name='ctr_org_type_cat_ix'),
        ),
        migrations.RunPython(forwards_seed_and_backfill, backwards_clear_catalogue_fk),
    ]
