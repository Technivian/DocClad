from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Model, QuerySet
from django.utils.text import slugify

from .models import Organization, OrganizationMembership
from .services.starter_content import ensure_org_starter_content

User = get_user_model()


def ensure_user_organization(user: Optional[User]) -> Optional[Organization]:
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    memberships = (
        OrganizationMembership.objects
        .filter(user=user, is_active=True, organization__is_active=True)
        .select_related('organization')
    )
    existing = memberships.order_by('id').first()
    if existing:
        return existing.organization

    base_slug = slugify(getattr(user, 'username', '') or f'user-{user.id}') or f'user-{user.id}'
    org_slug = base_slug
    n = 2
    while Organization.objects.filter(slug=org_slug).exists():
        org_slug = f'{base_slug}-{n}'
        n += 1

    org_name = f"{user.get_full_name().strip() or user.username}'s Firm"
    organization = Organization.objects.create(name=org_name, slug=org_slug)
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.OWNER,
        is_active=True,
    )
    ensure_org_starter_content(organization)
    return organization


def get_user_organization(user: Optional[User]) -> Optional[Organization]:
    base_org = ensure_user_organization(user)
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    preferred_org_id = getattr(user, '_active_organization_id', None)
    if preferred_org_id:
        selected = (
            OrganizationMembership.objects
            .filter(
                user=user,
                is_active=True,
                organization__is_active=True,
                organization_id=preferred_org_id,
            )
            .select_related('organization')
            .first()
        )
        if selected:
            return selected.organization

    return base_org


# Models that carry no direct ``organization`` field are scoped through a
# tenant-linking relation instead. Explicit paths are authoritative; any model
# not listed falls back to auto-discovery and finally to deny-by-default, so a
# new organization-less model can never silently leak across tenants.
_TENANT_FK_PATHS = {
    'TrustAccount': 'client__organization',
    'ComplianceChecklist': 'contract__organization',
    'ChecklistItem': 'checklist__contract__organization',
    'WorkflowStep': 'workflow__organization',
}

# Single-hop relations probed (in order) when a model has no explicit path and
# no direct ``organization`` field.
_TENANT_FK_CANDIDATES = ('contract', 'client', 'matter', 'workflow', 'process', 'budget')


def _resolve_tenant_path(model_cls: type[Model], field_names: set[str]) -> Optional[str]:
    explicit = _TENANT_FK_PATHS.get(model_cls.__name__)
    if explicit:
        return explicit
    for candidate in _TENANT_FK_CANDIDATES:
        if candidate not in field_names:
            continue
        try:
            related = model_cls._meta.get_field(candidate).related_model
        except Exception:
            continue
        if related and 'organization' in {f.name for f in related._meta.get_fields()}:
            return f'{candidate}__organization'
    return None


def scope_queryset_for_organization(queryset: QuerySet, organization: Optional[Organization]) -> QuerySet:
    if organization is None:
        return queryset.none()

    model_cls: type[Model] = queryset.model
    field_names = {f.name for f in model_cls._meta.get_fields()}
    if 'organization' in field_names:
        return queryset.filter(organization=organization)

    tenant_path = _resolve_tenant_path(model_cls, field_names)
    if tenant_path:
        return queryset.filter(**{tenant_path: organization})

    # No tenant linkage could be resolved: deny by default rather than leak
    # every tenant's rows through the unscoped queryset.
    return queryset.none()


def set_organization_on_instance(instance: Model, organization: Optional[Organization]) -> None:
    if organization is None:
        return
    if hasattr(instance, 'organization_id') and not getattr(instance, 'organization_id', None):
        instance.organization = organization
