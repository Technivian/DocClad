from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CanonicalWorkflowRuntimeMigrationTests(TransactionTestCase):
    """0116 is additive and reversible before any canonical evidence is written."""

    migrate_from = ('contracts', '0115_exception_correlation_id')
    migrate_to = ('contracts', '0116_canonical_workflow_nda_runtime')

    def test_forward_and_reverse_schema(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
        self.assertTrue({
            'contracts_workflowdefinition',
            'contracts_workflowversion',
            'contracts_workflowinstance',
            'contracts_signaturepacket',
            'contracts_signatureevidence',
            'contracts_contractrecord',
        }.issubset(tables))

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
        self.assertNotIn('contracts_workflowdefinition', tables)

        # Restore the test database to the project's leaf migrations.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
