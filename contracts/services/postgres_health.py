"""PostgreSQL health check service for ops hardening."""
from __future__ import annotations

import time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class PostgresHealthService:
    def check_connection(self) -> dict:
        try:
            start = time.monotonic()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            backend = connection.settings_dict.get('ENGINE', 'unknown')
            return {'connected': True, 'backend': backend, 'latency_ms': latency_ms}
        except Exception:
            backend = connection.settings_dict.get('ENGINE', 'unknown')
            return {'connected': False, 'backend': backend, 'latency_ms': -1.0}

    def get_migration_status(self) -> dict:
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            pending = [f'{app}.{name}' for (app, name), _ in plan]
            total_applied = len(executor.loader.applied_migrations)
            return {
                'total': total_applied + len(pending),
                'applied': total_applied,
                'pending': pending,
            }
        except Exception as e:
            return {'total': 0, 'applied': 0, 'pending': [], 'error': str(e)}

    def get_db_stats(self) -> dict:
        backend = connection.settings_dict.get('ENGINE', 'unknown')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT version()')
                row = cursor.fetchone()
                version = row[0] if row else 'unknown'
        except Exception:
            version = 'unknown'

        return {
            'backend': backend,
            'version': version,
            'connection_pool_size': 1,
        }


def get_postgres_health_service() -> PostgresHealthService:
    return PostgresHealthService()
