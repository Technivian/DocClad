# Generated manually for Phase 5 work instrumentation.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0102_approvalrequest_delegation_coverage'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkInteractionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(choices=[('surfaced', 'Work item surfaced'), ('opened', 'Work item opened'), ('primary_action', 'Primary action taken'), ('completed', 'Work completed'), ('returned', 'Work returned'), ('rejected', 'Work rejected'), ('sla_breached', 'SLA breached / overdue transition')], max_length=32)),
                ('work_item_id', models.CharField(help_text='Stable row id, e.g. approval:12', max_length=80)),
                ('work_kind', models.CharField(blank=True, max_length=40)),
                ('surface', models.CharField(choices=[('my_work', 'My Work'), ('approvals', 'Reviews & Approvals'), ('obligations', 'Obligations'), ('privacy', 'Privacy Reviews'), ('tasks', 'Legal Tasks'), ('contract_detail', 'Contract detail'), ('api', 'API'), ('job', 'Background job')], default='my_work', max_length=32)),
                ('contract_id', models.PositiveIntegerField(blank=True, null=True)),
                ('contract_type', models.CharField(blank=True, max_length=40)),
                ('is_restricted', models.BooleanField(default=False)),
                ('is_blocked', models.BooleanField(default=False)),
                ('is_overdue', models.BooleanField(default=False)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_interaction_events', to='contracts.organization')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='work_interaction_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-occurred_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workinteractionevent',
            index=models.Index(fields=['organization', 'event', 'occurred_at'], name='work_evt_org_evt_ix'),
        ),
        migrations.AddIndex(
            model_name='workinteractionevent',
            index=models.Index(fields=['organization', 'work_item_id', 'event'], name='work_evt_item_evt_ix'),
        ),
        migrations.AddIndex(
            model_name='workinteractionevent',
            index=models.Index(fields=['organization', 'surface', 'event'], name='work_evt_surface_ix'),
        ),
    ]
