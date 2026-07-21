# Generated manually for Phase 6 My Work saved views.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0103_workinteractionevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='MyWorkSavedView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='my_work_saved_views', to='contracts.organization')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='my_work_saved_views', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddConstraint(
            model_name='myworksavedview',
            constraint=models.UniqueConstraint(fields=('organization', 'user', 'name'), name='my_work_view_org_user_name_uniq'),
        ),
        migrations.AddIndex(
            model_name='myworksavedview',
            index=models.Index(fields=['organization', 'user', 'is_default'], name='my_work_view_default_ix'),
        ),
    ]
