import sys

from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contracts'

    def ready(self):
        # Register authentication audit signal receivers.
        from contracts import signals  # noqa: F401

        self._enforce_local_database_outside_deployment()

    @staticmethod
    def _enforce_local_database_outside_deployment():
        """Sub-block D: refuse to start against a non-local database host
        unless this process is actually running on the deployed platform (or
        the developer explicitly opted in), and always print which database
        is active.

        Deliberately does NOT key off DJANGO_ENV: this repo's local .env sets
        DJANGO_ENV=production (mirroring the real Render deployment's config,
        presumably so production-flavored commands can be run locally when
        genuinely intended) alongside the real DATABASE_URL — so DJANGO_ENV
        cannot distinguish "a local checkout" from "the real deployment".
        config.db_safety.is_running_on_deployed_platform() checks for
        Render-specific env vars that only exist on the real deployed
        service and can't be present on a developer's machine by accident.

        Runs from AppConfig.ready() rather than at settings-module import
        time: apps are fully loaded by this point, so exiting here is clean
        (a printed message and process exit) instead of leaving Django's app
        registry half-initialized, which is what happened when an earlier
        version of this check raised directly from within a settings module
        (a later check — e.g. the URL-namespace check runserver/check run —
        tried to touch models before app loading had finished, surfacing a
        confusing "AppRegistryNotReady" instead of a clear message).
        """
        import os

        from django.conf import settings

        from config.db_safety import is_local_database_host, is_running_on_deployed_platform

        db_config = settings.DATABASES['default']
        is_local = is_local_database_host(db_config)
        is_test_run = len(sys.argv) > 1 and sys.argv[1] == 'test'
        is_deployed = is_running_on_deployed_platform()
        allow_remote = os.environ.get('ALLOW_REMOTE_DATABASE', '').strip().lower() in {'1', 'true', 'yes', 'on'}
        db_identity = db_config.get('NAME') if 'sqlite' in db_config.get('ENGINE', '') else db_config.get('HOST', 'unknown')

        if not is_local and not is_test_run and not is_deployed and not allow_remote:
            print(  # noqa: T201 — this is the point of the guard
                f'[CLM One] REFUSING TO START: DATABASE_URL resolves to a non-local host '
                f'({db_identity!r}) and this does not look like the deployed platform.\n'
                f'[CLM One] Local development must not silently connect to a shared/remote '
                f'database. Point DATABASE_URL at a local database (sqlite or a local '
                f'Postgres), or set ALLOW_REMOTE_DATABASE=true to explicitly opt in '
                f'(e.g. for staging debugging).'
            )
            sys.exit(1)

        kind = 'local' if is_local else ('deployed platform' if is_deployed else 'REMOTE (explicitly allowed via ALLOW_REMOTE_DATABASE)')
        print(f'[CLM One] Database: {db_identity} ({kind}, env={settings.DJANGO_ENV})')  # noqa: T201
