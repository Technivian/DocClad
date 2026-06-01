"""Tests for PostgreSQL Health service (Area 4)."""
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestPostgresHealthService(TestCase):
    def _make_service(self):
        from contracts.services.postgres_health import PostgresHealthService
        return PostgresHealthService()

    def test_check_connection_success(self):
        svc = self._make_service()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        with patch('contracts.services.postgres_health.connection') as mock_conn:
            mock_conn.settings_dict = {'ENGINE': 'django.db.backends.sqlite3'}
            mock_conn.cursor.return_value = mock_cursor
            result = svc.check_connection()

        self.assertIn('connected', result)
        self.assertIn('backend', result)
        self.assertIn('latency_ms', result)

    def test_check_connection_failure(self):
        svc = self._make_service()

        with patch('contracts.services.postgres_health.connection') as mock_conn:
            mock_conn.settings_dict = {'ENGINE': 'django.db.backends.sqlite3'}
            mock_conn.cursor.side_effect = Exception('Connection refused')
            result = svc.check_connection()

        self.assertFalse(result['connected'])

    def test_get_migration_status_returns_correct_keys(self):
        svc = self._make_service()

        mock_executor = MagicMock()
        mock_executor.loader.graph.leaf_nodes.return_value = []
        mock_executor.migration_plan.return_value = []
        mock_executor.loader.applied_migrations = {('app', '0001_initial'): None}

        with patch('contracts.services.postgres_health.MigrationExecutor', return_value=mock_executor):
            result = svc.get_migration_status()

        self.assertIn('total', result)
        self.assertIn('applied', result)
        self.assertIn('pending', result)
        self.assertIsInstance(result['pending'], list)

    def test_get_db_stats_returns_backend(self):
        svc = self._make_service()

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = ('SQLite version 3.39',)

        with patch('contracts.services.postgres_health.connection') as mock_conn:
            mock_conn.settings_dict = {'ENGINE': 'django.db.backends.sqlite3'}
            mock_conn.cursor.return_value = mock_cursor
            result = svc.get_db_stats()

        self.assertIn('backend', result)
        self.assertIn('version', result)
        self.assertIn('connection_pool_size', result)

    def test_migration_status_handles_exception(self):
        svc = self._make_service()

        with patch('contracts.services.postgres_health.MigrationExecutor', side_effect=Exception('DB error')):
            result = svc.get_migration_status()

        self.assertIn('error', result)

    def test_check_connection_latency_non_negative(self):
        svc = self._make_service()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        with patch('contracts.services.postgres_health.connection') as mock_conn:
            mock_conn.settings_dict = {'ENGINE': 'django.db.backends.postgresql'}
            mock_conn.cursor.return_value = mock_cursor
            result = svc.check_connection()

        self.assertGreaterEqual(result['latency_ms'], 0)
