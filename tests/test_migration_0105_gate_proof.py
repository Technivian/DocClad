"""
Merge-gate proof for contracts.0105_workflowtemplate_is_active_default_false.

0105 is AlterField-only (no RunPython). It must:
- preserve existing is_active row values
- default new templates to inactive
- reverse cleanly (default metadata only; no silent row deactivation)
"""
from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

MIG_FROM = "0104_myworksavedview"
MIG_TO = "0105_workflowtemplate_is_active_default_false"


class WorkflowTemplateIsActiveDefaultMigrationGateProof(TransactionTestCase):
    """Prove 0105 forward / reverse / re-forward without data loss."""

    def _migrate(self, target: str):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("contracts", target)])
        return MigrationExecutor(connection).loader.project_state(
            [("contracts", target)]
        ).apps

    def test_0105_preserves_rows_and_defaults_new_inactive(self):
        apps = self._migrate(MIG_FROM)
        Organization = apps.get_model("contracts", "Organization")
        User = apps.get_model("auth", "User")
        WorkflowTemplate = apps.get_model("contracts", "WorkflowTemplate")

        org = Organization.objects.create(name="Gate Org 0105", slug="gate-org-0105")
        user = User.objects.create(username="gate_mig_0105", email="gate_mig_0105@example.com")
        active = WorkflowTemplate.objects.create(
            organization=org,
            name="Was Active",
            description="active template",
            created_by=user,
            is_active=True,
        )
        inactive = WorkflowTemplate.objects.create(
            organization=org,
            name="Was Inactive",
            description="inactive template",
            created_by=user,
            is_active=False,
        )
        active_id, inactive_id = active.pk, inactive.pk
        org_id, user_id = org.pk, user.pk

        # Forward → 0105
        apps = self._migrate(MIG_TO)
        WorkflowTemplate = apps.get_model("contracts", "WorkflowTemplate")
        self.assertTrue(WorkflowTemplate.objects.get(pk=active_id).is_active)
        self.assertFalse(WorkflowTemplate.objects.get(pk=inactive_id).is_active)

        Organization = apps.get_model("contracts", "Organization")
        User = apps.get_model("auth", "User")
        created_after = WorkflowTemplate.objects.create(
            organization=Organization.objects.get(pk=org_id),
            name="Created After 0105",
            description="post-forward",
            created_by=User.objects.get(pk=user_id),
        )
        self.assertFalse(
            created_after.is_active,
            "New templates must default inactive after 0105",
        )
        after_id = created_after.pk

        # Reverse → 0104 (AlterField only; row values must remain)
        apps = self._migrate(MIG_FROM)
        WorkflowTemplate = apps.get_model("contracts", "WorkflowTemplate")
        self.assertTrue(WorkflowTemplate.objects.get(pk=active_id).is_active)
        self.assertFalse(WorkflowTemplate.objects.get(pk=inactive_id).is_active)
        self.assertFalse(WorkflowTemplate.objects.get(pk=after_id).is_active)
        self.assertEqual(
            WorkflowTemplate.objects.filter(pk__in=[active_id, inactive_id, after_id]).count(),
            3,
        )

        # Re-forward → 0105
        apps = self._migrate(MIG_TO)
        WorkflowTemplate = apps.get_model("contracts", "WorkflowTemplate")
        self.assertTrue(WorkflowTemplate.objects.get(pk=active_id).is_active)
        self.assertFalse(WorkflowTemplate.objects.get(pk=inactive_id).is_active)
        self.assertFalse(WorkflowTemplate.objects.get(pk=after_id).is_active)

        Organization = apps.get_model("contracts", "Organization")
        User = apps.get_model("auth", "User")
        created_again = WorkflowTemplate.objects.create(
            organization=Organization.objects.get(pk=org_id),
            name="Created After Re-forward",
            description="post-reforward",
            created_by=User.objects.get(pk=user_id),
        )
        self.assertFalse(created_again.is_active)
