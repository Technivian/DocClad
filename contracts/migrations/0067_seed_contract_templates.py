from django.db import migrations

TEMPLATES = [
    {
        'name': 'Standard Mutual NDA',
        'contract_type': 'NDA',
        'description': 'Two-way confidentiality agreement for early-stage vendor or partner discussions.',
        'body': (
            'MUTUAL NON-DISCLOSURE AGREEMENT\n\n'
            'This Agreement is entered into as of {{effective_date}} between {{title}} and {{counterparty}} '
            '(together, the "Parties").\n\n'
            '1. Confidential Information. Each Party may disclose information that is confidential or '
            'proprietary. The receiving Party will use such information solely to evaluate a potential '
            'business relationship and will protect it with the same degree of care it uses for its own '
            'confidential information, and no less than reasonable care.\n\n'
            '2. Term. This Agreement remains in effect until {{end_date}}, and the confidentiality '
            'obligations survive for two (2) years after that date.\n\n'
            '3. Governing Law. This Agreement is governed by the laws of {{governing_law}}.\n\n'
            'No license or other rights are granted by this Agreement.'
        ),
    },
    {
        'name': 'Standard Master Service Agreement',
        'contract_type': 'MSA',
        'description': 'Baseline MSA framework for ongoing services engagements, with liability cap language.',
        'body': (
            'MASTER SERVICE AGREEMENT\n\n'
            'This Master Service Agreement ("Agreement") is entered into as of {{effective_date}} between '
            '{{title}} ("Provider") and {{counterparty}} ("Customer").\n\n'
            '1. Services. Provider will perform services as described in one or more Statements of Work '
            'entered into under this Agreement.\n\n'
            '2. Fees. Customer will pay Provider {{value}} {{currency}}, as further specified in the '
            'applicable Statement of Work.\n\n'
            '3. Term. This Agreement is effective as of {{effective_date}} and continues until {{end_date}}, '
            'unless earlier terminated as provided herein.\n\n'
            '4. Limitation of Liability. Neither party shall be liable for indirect, incidental, or '
            'consequential damages. Each party\'s total cumulative liability shall not exceed the fees paid '
            'in the twelve (12) months preceding the claim.\n\n'
            '5. Governing Law. This Agreement is governed by the laws of {{governing_law}}, with jurisdiction '
            'in {{jurisdiction}}.'
        ),
    },
    {
        'name': 'Standard Data Processing Agreement',
        'contract_type': 'DPA',
        'description': 'GDPR-aligned processor terms to attach to a primary services agreement.',
        'body': (
            'DATA PROCESSING AGREEMENT\n\n'
            'This Data Processing Agreement ("DPA") supplements the agreement between {{title}} '
            '("Controller") and {{counterparty}} ("Processor"), effective {{effective_date}}.\n\n'
            '1. Subject Matter. Processor will process personal data solely on behalf of Controller and only '
            'for the purposes of providing the services described in the underlying agreement.\n\n'
            '2. Security. Processor will implement appropriate technical and organizational measures to '
            'protect personal data against unauthorized or unlawful processing and against accidental loss, '
            'destruction, or damage.\n\n'
            '3. Sub-processors. Processor will not engage a sub-processor without Controller\'s prior written '
            'authorization.\n\n'
            '4. Breach Notification. Processor will notify Controller without undue delay after becoming '
            'aware of a personal data breach.\n\n'
            '5. Governing Law. This DPA is governed by the laws of {{governing_law}}.'
        ),
    },
    {
        'name': 'Standard Statement of Work',
        'contract_type': 'SOW',
        'description': 'Scope, fees, and timeline template to execute under an existing MSA.',
        'body': (
            'STATEMENT OF WORK\n\n'
            'This Statement of Work ("SOW") is entered into as of {{effective_date}} between {{title}} and '
            '{{counterparty}}, pursuant to and governed by the terms of the Master Service Agreement between '
            'the parties.\n\n'
            '1. Scope of Work. [Describe deliverables and scope here.]\n\n'
            '2. Fees. Total fees for this SOW are {{value}} {{currency}}.\n\n'
            '3. Term. This SOW begins on {{effective_date}} and is expected to conclude by {{end_date}}.\n\n'
            '4. Acceptance. Deliverables will be deemed accepted unless Customer provides written notice of '
            'deficiency within ten (10) business days of delivery.'
        ),
    },
    {
        'name': 'Standard Consulting Agreement',
        'contract_type': 'CONSULTING',
        'description': 'Independent contractor terms for individual consultants or small firms.',
        'body': (
            'CONSULTING AGREEMENT\n\n'
            'This Consulting Agreement is entered into as of {{effective_date}} between {{title}} ("Company") '
            'and {{counterparty}} ("Consultant").\n\n'
            '1. Services. Consultant will provide the services described in any attached scope of work.\n\n'
            '2. Compensation. Company will pay Consultant {{value}} {{currency}} for the services described '
            'herein.\n\n'
            '3. Independent Contractor. Consultant is an independent contractor and not an employee of '
            'Company. Nothing in this Agreement creates a partnership, joint venture, or agency relationship.\n\n'
            '4. Term. This Agreement is effective as of {{effective_date}} and continues until {{end_date}}, '
            'unless earlier terminated.\n\n'
            '5. Governing Law. This Agreement is governed by the laws of {{governing_law}}.'
        ),
    },
]


def seed_templates(apps, schema_editor):
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    for entry in TEMPLATES:
        ContractTemplate.objects.get_or_create(
            name=entry['name'],
            contract_type=entry['contract_type'],
            defaults={'description': entry['description'], 'body': entry['body'], 'is_active': True},
        )


def unseed_templates(apps, schema_editor):
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    names = [entry['name'] for entry in TEMPLATES]
    ContractTemplate.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0066_contracttemplate'),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
