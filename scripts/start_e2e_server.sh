#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY=python
fi

export DJANGO_E2E=1
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_development}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/e2e.sqlite3}"

"$PY" "$ROOT_DIR/manage.py" migrate --noinput
"$PY" "$ROOT_DIR/manage.py" shell -c "
from django.contrib.auth import get_user_model
from contracts.models import Organization, OrganizationMembership

User = get_user_model()
user, _ = User.objects.get_or_create(
    username='e2e_owner',
    defaults={'email': 'e2e_owner@example.com'},
)
user.is_staff = True
user.is_superuser = True
user.set_password('e2e_pass_123')
user.save()

org, _ = Organization.objects.get_or_create(
    slug='e2e-command-center',
    defaults={'name': 'E2E Command Center', 'workspace_mode': Organization.WorkspaceMode.IN_HOUSE_CLM},
)
if org.workspace_mode != Organization.WorkspaceMode.IN_HOUSE_CLM:
    org.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
    org.save(update_fields=['workspace_mode', 'updated_at'])

membership, _ = OrganizationMembership.objects.get_or_create(
    organization=org,
    user=user,
    defaults={'role': OrganizationMembership.Role.OWNER, 'is_active': True},
)
if not membership.is_active or membership.role != OrganizationMembership.Role.OWNER:
    membership.is_active = True
    membership.role = OrganizationMembership.Role.OWNER
    membership.save(update_fields=['is_active', 'role', 'updated_at'])
"

"$PY" "$ROOT_DIR/manage.py" seed_demo_command_center \
  --organization-slug e2e-command-center \
  --username e2e_owner

exec "$PY" "$ROOT_DIR/manage.py" runserver 127.0.0.1:8010
