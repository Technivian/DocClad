# PAR-ID-001 — additive RoleDefinition catalogue (ADR-0014 Accepted; auth record 0112).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CANONICAL_SEEDS = (
    ('workspace_owner', 'Workspace Owner', 'WORKSPACE',
     'Organization owner — workspace administration.'),
    ('workspace_admin', 'Workspace Admin', 'WORKSPACE',
     'Organization admin — configuration and elevated operations.'),
    ('workspace_member', 'Workspace Member', 'WORKSPACE',
     'Organization member — base workspace access.'),
    ('requester', 'Requester', 'WORKFLOW',
     'Process requester for a contract or workflow instance.'),
    ('contract_owner', 'Contract Owner', 'WORKFLOW',
     'Accountable contract owner.'),
    ('legal_reviewer', 'Legal Reviewer', 'APPROVAL',
     'Legal review / approval process role.'),
    ('senior_reviewer', 'Senior Reviewer', 'APPROVAL',
     'Senior legal review process role.'),
    ('partner_reviewer', 'Partner Reviewer', 'APPROVAL',
     'Partner-level review process role.'),
    ('paralegal_reviewer', 'Paralegal Reviewer', 'WORKFLOW',
     'Paralegal process role.'),
    ('legal_assistant', 'Legal Assistant', 'WORKFLOW',
     'Legal assistant process role.'),
    ('finance_approver', 'Finance Approver', 'APPROVAL',
     'Finance approval process role.'),
    ('privacy_reviewer', 'Privacy Reviewer', 'APPROVAL',
     'Privacy review process role.'),
    ('executive_approver', 'Executive Approver', 'APPROVAL',
     'Executive approval process role.'),
    ('compliance_reviewer', 'Compliance Reviewer', 'APPROVAL',
     'Compliance review process role.'),
    ('signer', 'Signer', 'SIGNATURE',
     'Signature process role (display catalogue; auth remains email-based).'),
    ('archiver', 'Archiver', 'WORKFLOW',
     'Archival process role.'),
    ('external_participant', 'External Participant', 'WORKFLOW',
     'External / client participant process role.'),
    ('system_actor', 'System Actor', 'SYSTEM',
     'Explicit system principal for background jobs and migrations.'),
    ('legacy_process_admin', 'Legacy Process Admin (ambiguous)', 'LEGACY_UNKNOWN',
     'Maps UserProfile.Role.ADMIN — NOT workspace ADMIN. Semantics uncertain.'),
    ('legacy_unknown', 'Legacy Unknown', 'LEGACY_UNKNOWN',
     'Catch-all for unmapped historical role labels.'),
)


def seed_role_definitions(apps, schema_editor):
    Organization = apps.get_model('contracts', 'Organization')
    RoleDefinition = apps.get_model('contracts', 'RoleDefinition')
    for org in Organization.objects.order_by('id'):
        for code, name, category, description in CANONICAL_SEEDS:
            if RoleDefinition.objects.filter(organization_id=org.pk, code=code).exists():
                continue
            RoleDefinition.objects.create(
                organization_id=org.pk,
                code=code,
                name=name,
                description=description,
                category=category,
                is_active=True,
                is_system_managed=True,
            )


def unseed_role_definitions(apps, schema_editor):
    RoleDefinition = apps.get_model('contracts', 'RoleDefinition')
    RoleDefinition.objects.filter(is_system_managed=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0111_approval_requirement_decision'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True, default='')),
                ('category', models.CharField(
                    choices=[
                        ('WORKSPACE', 'Workspace'),
                        ('WORKFLOW', 'Workflow'),
                        ('APPROVAL', 'Approval'),
                        ('SIGNATURE', 'Signature'),
                        ('SYSTEM', 'System'),
                        ('LEGACY_UNKNOWN', 'Legacy unknown'),
                    ],
                    max_length=32,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('is_system_managed', models.BooleanField(
                    default=False,
                    help_text='System-seeded definitions; code and category protected from casual edit.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='role_definitions_created', to=settings.AUTH_USER_MODEL,
                )),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='role_definitions', to='contracts.organization',
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='role_definitions_updated', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['organization_id', 'category', 'code'],
            },
        ),
        migrations.AddIndex(
            model_name='roledefinition',
            index=models.Index(fields=['organization', 'category', 'is_active'], name='roledef_org_cat_active_ix'),
        ),
        migrations.AddIndex(
            model_name='roledefinition',
            index=models.Index(fields=['organization', 'is_active'], name='roledef_org_active_ix'),
        ),
        migrations.AddConstraint(
            model_name='roledefinition',
            constraint=models.UniqueConstraint(fields=('organization', 'code'), name='roledef_org_code_uniq'),
        ),
        migrations.RunPython(seed_role_definitions, unseed_role_definitions),
    ]
