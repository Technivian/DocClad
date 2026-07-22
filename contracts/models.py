from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import hashlib
import json
import secrets
import uuid
import os

User = get_user_model()


def document_upload_path(instance, filename):
    return f'documents/{instance.matter.id if instance.matter else "general"}/{filename}'


class Organization(models.Model):
    class IdentityProvider(models.TextChoices):
        OIDC = 'OIDC', 'OpenID Connect'
        SAML = 'SAML', 'SAML'

    class WorkspaceMode(models.TextChoices):
        LAW_FIRM_OPS = 'law_firm_ops', 'Law firm operations'
        IN_HOUSE_CLM = 'in_house_clm', 'In-house CLM'

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    # Per-tenant nav/dashboard emphasis (see contracts/nav_config.py). This is
    # deliberately a DB field, not a global env feature flag — different
    # tenants in the same deployment need different modes simultaneously.
    # Never gates permissions or route availability, only what the sidebar
    # renders by default; every route stays reachable directly regardless.
    workspace_mode = models.CharField(
        max_length=20, choices=WorkspaceMode.choices, default=WorkspaceMode.IN_HOUSE_CLM,
    )
    require_mfa = models.BooleanField(default=False)
    session_idle_timeout_minutes = models.PositiveIntegerField(
        default=120,
        validators=[MinValueValidator(5)],
    )
    identity_provider = models.CharField(max_length=20, choices=IdentityProvider.choices, default=IdentityProvider.OIDC)
    saml_entity_id = models.CharField(max_length=255, blank=True)
    saml_sso_url = models.URLField(blank=True)
    saml_slo_url = models.URLField(blank=True)
    saml_metadata_url = models.URLField(blank=True)
    saml_x509_certificate = models.TextField(blank=True)
    # SAML MFA trust policy (Phase 4G). CLM One marks a SAML session as
    # MFA-satisfied only when the assertion's AuthnContextClassRef is in
    # `saml_accepted_authn_contexts` (comma/newline-separated), OR when the org
    # has explicitly enabled `saml_mfa_trusted` (compatibility mode: delegates
    # MFA enforcement entirely to the IdP). Default is fail-closed: a SAML login
    # without proven MFA assurance must still complete CLM One MFA.
    saml_mfa_trusted = models.BooleanField(default=False)
    saml_accepted_authn_contexts = models.TextField(blank=True)
    scim_enabled = models.BooleanField(default=False)
    scim_token_hash = models.CharField(max_length=64, blank=True)
    scim_token_last4 = models.CharField(max_length=4, blank=True)
    scim_token_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def rotate_scim_token(self):
        raw_token = secrets.token_urlsafe(32)
        self.scim_token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        self.scim_token_last4 = raw_token[-4:]
        self.scim_token_created_at = timezone.now()
        self.scim_enabled = True
        self.save(
            update_fields=[
                'scim_token_hash',
                'scim_token_last4',
                'scim_token_created_at',
                'scim_enabled',
                'updated_at',
            ]
        )
        return raw_token

    def matches_scim_token(self, raw_token):
        if not raw_token or not self.scim_token_hash:
            return False
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest() == self.scim_token_hash

    def rotate_api_token(self, scopes=None, label='API token', created_by=None):
        token_scopes = scopes or ['contracts:read']
        return OrganizationAPIToken.create_token(
            organization=self,
            scopes=token_scopes,
            label=label,
            created_by=created_by,
        )


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        ADMIN = 'ADMIN', 'Admin'
        MEMBER = 'MEMBER', 'Member'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organization_memberships')
    scim_external_id = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')
        ordering = ['organization__name', 'user__username']

    def __str__(self):
        return f'{self.user.username} @ {self.organization.name} ({self.role})'


class OrganizationInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REVOKED = 'REVOKED', 'Revoked'
        EXPIRED = 'EXPIRED', 'Expired'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=OrganizationMembership.Role.choices, default=OrganizationMembership.Role.MEMBER)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_organization_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_organization_invitations')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class DeliveryStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    # Delivery state is tracked separately from invitation state (Phase 4D): a
    # mail-provider failure must not corrupt the invitation. delivery_error holds
    # a SAFE classification (exception class name), never a traceback or secrets.
    delivery_status = models.CharField(max_length=10, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivery_error = models.CharField(max_length=100, blank=True)
    last_delivery_attempt_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['email', 'status']),
        ]

    def __str__(self):
        return f'Invite {self.email} to {self.organization.name} ({self.get_status_display()})'


class UserProfile(models.Model):
    class Role(models.TextChoices):
        PARTNER = 'PARTNER', 'Partner'
        SENIOR_ASSOCIATE = 'SENIOR_ASSOCIATE', 'Senior Associate'
        ASSOCIATE = 'ASSOCIATE', 'Associate'
        PARALEGAL = 'PARALEGAL', 'Paralegal'
        LEGAL_ASSISTANT = 'LEGAL_ASSISTANT', 'Legal Assistant'
        ADMIN = 'ADMIN', 'Administrator'
        CLIENT = 'CLIENT', 'Client'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ASSOCIATE)
    phone = models.CharField(max_length=20, blank=True)
    bar_number = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_verified_at = models.DateTimeField(null=True, blank=True)
    mfa_enrollment_code_hash = models.CharField(max_length=64, blank=True)
    mfa_enrollment_code_expires_at = models.DateTimeField(null=True, blank=True)
    mfa_enrollment_code_sent_at = models.DateTimeField(null=True, blank=True)
    mfa_recovery_code_hashes = models.JSONField(default=list, blank=True)
    session_revocation_counter = models.PositiveIntegerField(default=0)
    # Account preferences — self-service presentation and notification controls.
    class Language(models.TextChoices):
        EN = 'en', 'English'
        NL = 'nl', 'Nederlands'
        DE = 'de', 'Deutsch'
        FR = 'fr', 'Français'

    class DateFormat(models.TextChoices):
        DMY_LONG = 'd M Y', '31 Jan 2026'
        ISO = 'Y-m-d', '2026-01-31'
        MDY = 'm/d/Y', '01/31/2026'
        DMY = 'd/m/Y', '31/01/2026'

    language = models.CharField(max_length=8, choices=Language.choices, default=Language.EN)
    timezone = models.CharField(max_length=64, default='UTC')
    date_format = models.CharField(max_length=16, choices=DateFormat.choices, default=DateFormat.DMY_LONG)
    notify_contract_updates = models.BooleanField(default=True)
    notify_workflow_events = models.BooleanField(default=True)
    notify_review_approval_requests = models.BooleanField(default=True)
    notify_obligation_reminders = models.BooleanField(default=True)
    notify_security_alerts = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        if not self.mfa_enabled:
            self.mfa_verified_at = None
        super().save(*args, **kwargs)

    def _mfa_code_hash(self, code):
        material = f'{self.user_id}:{code}:{settings.SECRET_KEY}'
        return hashlib.sha256(material.encode('utf-8')).hexdigest()

    def issue_mfa_enrollment_code(self, ttl_minutes=10):
        code = f'{secrets.randbelow(1_000_000):06d}'
        self.mfa_enrollment_code_hash = self._mfa_code_hash(code)
        self.mfa_enrollment_code_expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
        self.mfa_enrollment_code_sent_at = timezone.now()
        self.save(
            update_fields=[
                'mfa_enrollment_code_hash',
                'mfa_enrollment_code_expires_at',
                'mfa_enrollment_code_sent_at',
                'updated_at',
            ]
        )
        return code

    def verify_mfa_enrollment_code(self, code):
        if not code or not self.mfa_enrollment_code_hash:
            return False
        if self.mfa_enrollment_code_expires_at and timezone.now() > self.mfa_enrollment_code_expires_at:
            return False
        if self.mfa_enrollment_code_hash != self._mfa_code_hash(str(code).strip()):
            return False
        self.mfa_enabled = True
        self.mfa_verified_at = timezone.now()
        self.mfa_enrollment_code_hash = ''
        self.mfa_enrollment_code_expires_at = None
        self.mfa_enrollment_code_sent_at = None
        self.save(
            update_fields=[
                'mfa_enabled',
                'mfa_verified_at',
                'mfa_enrollment_code_hash',
                'mfa_enrollment_code_expires_at',
                'mfa_enrollment_code_sent_at',
                'updated_at',
            ]
        )
        return True

    def issue_mfa_recovery_codes(self, count=8):
        codes = []
        code_hashes = []
        for _ in range(max(1, int(count))):
            code = f'{secrets.randbelow(1_000_000):06d}'
            codes.append(code)
            code_hashes.append(self._mfa_code_hash(code))
        self.mfa_recovery_code_hashes = code_hashes
        self.save(update_fields=['mfa_recovery_code_hashes', 'updated_at'])
        return codes

    def verify_mfa_recovery_code(self, code):
        if not code or not self.mfa_recovery_code_hashes:
            return False
        code_hash = self._mfa_code_hash(str(code).strip())
        if code_hash not in self.mfa_recovery_code_hashes:
            return False
        self.mfa_recovery_code_hashes = [existing_hash for existing_hash in self.mfa_recovery_code_hashes if existing_hash != code_hash]
        self.session_revocation_counter += 1
        self.save(update_fields=['mfa_recovery_code_hashes', 'session_revocation_counter', 'updated_at'])
        return True

    @property
    def mfa_recovery_code_count(self):
        return len(self.mfa_recovery_code_hashes or [])

    def check_mfa_code(self, code) -> bool:
        """Verify a login-challenge OTP without changing enrollment state."""
        if not code or not self.mfa_enrollment_code_hash:
            return False
        if self.mfa_enrollment_code_expires_at and timezone.now() > self.mfa_enrollment_code_expires_at:
            return False
        ok = self.mfa_enrollment_code_hash == self._mfa_code_hash(str(code).strip())
        if ok:
            self.mfa_enrollment_code_hash = ''
            self.mfa_enrollment_code_expires_at = None
            self.save(update_fields=['mfa_enrollment_code_hash', 'mfa_enrollment_code_expires_at', 'updated_at'])
        return ok

    @property
    def can_approve(self):
        return self.role in [self.Role.PARTNER, self.Role.SENIOR_ASSOCIATE, self.Role.ADMIN]

    @property
    def is_attorney(self):
        return self.role in [self.Role.PARTNER, self.Role.SENIOR_ASSOCIATE, self.Role.ASSOCIATE]


class OrganizationSCIMGroup(models.Model):
    ROLE_CHOICES = [
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='scim_groups')
    external_id = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    is_active = models.BooleanField(default=True)
    members = models.ManyToManyField(
        OrganizationMembership,
        through='OrganizationSCIMGroupMembership',
        related_name='scim_group_memberships',
        blank=True,
    )
    nested_groups = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='parent_groups',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'display_name')
        ordering = ['organization__name', 'display_name']

    def __str__(self):
        return f'{self.display_name} @ {self.organization.name}'


class OrganizationSCIMGroupMembership(models.Model):
    group = models.ForeignKey(OrganizationSCIMGroup, on_delete=models.CASCADE, related_name='group_memberships')
    membership = models.ForeignKey(OrganizationMembership, on_delete=models.CASCADE, related_name='group_memberships')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'membership')


class OrganizationAPIToken(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='api_tokens')
    label = models.CharField(max_length=200, default='API token')
    token_hash = models.CharField(max_length=64, unique=True)
    token_last4 = models.CharField(max_length=4, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_api_tokens')
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Token is rejected after this datetime. Leave blank for no expiry.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.label} @ {self.organization.name}'

    @property
    def is_expired(self):
        from django.utils import timezone
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @staticmethod
    def _hash_token(raw_token):
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @classmethod
    def create_token(cls, organization, scopes=None, label='API token', created_by=None):
        raw_token = secrets.token_urlsafe(32)
        token = cls.objects.create(
            organization=organization,
            label=label,
            token_hash=cls._hash_token(raw_token),
            token_last4=raw_token[-4:],
            scopes=list(scopes or ['contracts:read']),
            created_by=created_by,
        )
        return token, raw_token

    def matches_token(self, raw_token):
        if not raw_token:
            return False
        return self._hash_token(raw_token) == self.token_hash

    def has_scope(self, scope):
        if not scope:
            return True
        normalized = {str(item).strip() for item in (self.scopes or []) if str(item).strip()}
        return scope in normalized or 'contracts:*' in normalized or 'api:*' in normalized


class SalesforceOrganizationConnection(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='salesforce_connection')
    connected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='salesforce_connections')
    external_org_id = models.CharField(max_length=255, blank=True)
    instance_url = models.URLField(blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    scope = models.CharField(max_length=255, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name']

    def __str__(self):
        return f'Salesforce connection @ {self.organization.name}'

    @property
    def token_expired(self):
        return bool(self.token_expires_at and timezone.now() >= self.token_expires_at)


class OrganizationContractFieldMap(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='contract_field_maps')
    canonical_field = models.CharField(max_length=64)
    salesforce_object = models.CharField(max_length=80, default='Opportunity')
    salesforce_field = models.CharField(max_length=120)
    is_required = models.BooleanField(default=False)
    transform_rule = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_contract_field_maps')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_contract_field_maps')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'canonical_field')
        ordering = ['organization__name', 'canonical_field']

    def __str__(self):
        return f'{self.organization.slug}:{self.canonical_field}->{self.salesforce_object}.{self.salesforce_field}'


class SalesforceSyncRun(models.Model):
    class TriggerSource(models.TextChoices):
        API = 'API', 'API'
        COMMAND = 'COMMAND', 'Command'
        WORKER = 'WORKER', 'Worker'

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', 'Running'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='salesforce_sync_runs')
    connection = models.ForeignKey(
        SalesforceOrganizationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sync_runs',
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salesforce_sync_runs',
    )
    trigger_source = models.CharField(max_length=20, choices=TriggerSource.choices, default=TriggerSource.API)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    dry_run = models.BooleanField(default=False)
    limit_applied = models.PositiveIntegerField(default=200)
    source_object = models.CharField(max_length=80, blank=True)
    fetched_records = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['organization', '-started_at'], name='sf_sync_org_time_ix'),
            models.Index(fields=['organization', 'status'], name='sf_sync_org_status_ix'),
        ]

    def __str__(self):
        return f'Salesforce sync {self.id} ({self.organization.slug}) {self.status}'


class WebhookEndpoint(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DISABLED = 'DISABLED', 'Disabled'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='webhook_endpoints')
    name = models.CharField(max_length=120)
    url = models.URLField()
    secret = models.CharField(max_length=255, blank=True)
    event_types = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    max_attempts = models.PositiveIntegerField(default=5)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_webhook_endpoints')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name', 'name']

    def __str__(self):
        return f'{self.organization.slug}:{self.name}'


class WebhookDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        DEAD_LETTER = 'DEAD_LETTER', 'Dead Letter'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='webhook_deliveries')
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status', 'next_attempt_at'], name='webhook_org_stat_next_ix'),
            models.Index(fields=['endpoint', 'status'], name='webhook_ep_stat_ix'),
        ]

    def __str__(self):
        return f'{self.event_type} -> {self.endpoint_id} ({self.status})'


class ExecutiveDashboardPreset(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='executive_dashboard_presets',
    )
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    layout = models.JSONField(default=dict, blank=True)
    is_shared = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executive_dashboard_presets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name', 'name']
        unique_together = ('organization', 'name')

    def __str__(self):
        return f'{self.organization.slug}:{self.name}'


class SearchPreset(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='search_presets',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_presets',
    )
    name = models.CharField(max_length=120)
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name', 'name']
        unique_together = ('organization', 'created_by', 'name')
        indexes = [
            models.Index(fields=['organization', 'created_by', 'name'], name='searchpreset_org_user_name_ix'),
            models.Index(fields=['organization', 'name'], name='searchpreset_org_name_ix'),
        ]

    def __str__(self):
        return f'{self.organization.slug}:{self.name}'


class MyWorkSavedView(models.Model):
    """Per-user My Work filter presets (Phase 6 persistent saved views)."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='my_work_saved_views',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='my_work_saved_views',
    )
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'user', 'name'],
                name='my_work_view_org_user_name_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'user', 'is_default'], name='my_work_view_default_ix'),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.name}'


class Client(models.Model):
    class ClientType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', 'Individual'
        CORPORATION = 'CORPORATION', 'Corporation'
        LLC = 'LLC', 'LLC'
        PARTNERSHIP = 'PARTNERSHIP', 'Partnership'
        GOVERNMENT = 'GOVERNMENT', 'Government Entity'
        NON_PROFIT = 'NON_PROFIT', 'Non-Profit'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        PROSPECTIVE = 'PROSPECTIVE', 'Prospective'
        FORMER = 'FORMER', 'Former'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='clients')
    name = models.CharField(max_length=200)
    client_type = models.CharField(max_length=20, choices=ClientType.choices, default=ClientType.INDIVIDUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='United States')
    tax_id = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    primary_contact = models.CharField(max_length=200, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=20, blank=True)
    responsible_attorney = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responsible_clients')
    originating_attorney = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='originated_clients')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_clients')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def total_billed(self):
        return self.invoices.aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0')

    @property
    def outstanding_balance(self):
        return self.invoices.filter(status__in=['SENT', 'OVERDUE']).aggregate(
            total=models.Sum('total_amount'))['total'] or Decimal('0')

    @property
    def active_matters_count(self):
        return self.matters.filter(status='ACTIVE').count()


class Matter(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        PENDING = 'PENDING', 'Pending'
        CLOSED = 'CLOSED', 'Closed'
        ON_HOLD = 'ON_HOLD', 'On Hold'

    class PracticeArea(models.TextChoices):
        CORPORATE = 'CORPORATE', 'Corporate'
        LITIGATION = 'LITIGATION', 'Litigation'
        IP = 'IP', 'Intellectual Property'
        REAL_ESTATE = 'REAL_ESTATE', 'Real Estate'
        EMPLOYMENT = 'EMPLOYMENT', 'Employment'
        TAX = 'TAX', 'Tax'
        REGULATORY = 'REGULATORY', 'Regulatory'
        FAMILY = 'FAMILY', 'Family Law'
        CRIMINAL = 'CRIMINAL', 'Criminal Defense'
        BANKRUPTCY = 'BANKRUPTCY', 'Bankruptcy'
        IMMIGRATION = 'IMMIGRATION', 'Immigration'
        ESTATE = 'ESTATE', 'Estate Planning'
        ENVIRONMENTAL = 'ENVIRONMENTAL', 'Environmental'
        OTHER = 'OTHER', 'Other'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='matters')
    scope = models.CharField(
        max_length=20,
        choices=[
            ('GEMEENTE', 'Gemeente'),
            ('REGIO', 'Regio'),
        ],
        default='GEMEENTE',
        help_text='Municipality or Regional scope',
    )
    is_active = models.BooleanField(default=True)
    matter_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='matters')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    practice_area = models.CharField(max_length=20, choices=PracticeArea.choices, default=PracticeArea.CORPORATE)
    responsible_attorney = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responsible_matters')
    originating_attorney = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='originated_matters')
    team_members = models.ManyToManyField(User, blank=True, related_name='matter_team')
    open_date = models.DateField(default=date.today)
    close_date = models.DateField(null=True, blank=True)
    statute_of_limitations = models.DateField(null=True, blank=True)
    court_name = models.CharField(max_length=200, blank=True)
    case_number = models.CharField(max_length=100, blank=True)
    opposing_party = models.CharField(max_length=200, blank=True)
    opposing_counsel = models.CharField(max_length=200, blank=True)
    max_wait_days = models.PositiveIntegerField(null=True, blank=True)
    priority_rules = models.TextField(blank=True)
    responsible_team = models.CharField(max_length=200, blank=True)
    billing_type = models.CharField(max_length=20, choices=[
        ('HOURLY', 'Hourly'),
        ('FLAT_FEE', 'Flat Fee'),
        ('CONTINGENCY', 'Contingency'),
        ('RETAINER', 'Retainer'),
        ('PRO_BONO', 'Pro Bono'),
    ], default='HOURLY')
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    is_confidential = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_matters')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.matter_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.matter_number:
            last = Matter.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.matter_number = f'MTR-{next_num:05d}'
        super().save(*args, **kwargs)

    @property
    def total_time_billed(self):
        entries = self.time_entries.filter(is_billable=True)
        total = sum(e.hours for e in entries)
        return total

    @property
    def total_amount_billed(self):
        entries = self.time_entries.filter(is_billable=True)
        total = sum(e.total_amount for e in entries)
        return total


class ContractQuerySet(models.QuerySet):
    """Block QuerySet.update / bulk_create from bypassing provenance immutability."""

    def update(self, **kwargs):
        from contracts.services.contract_provenance import PROVENANCE_UPDATE_BLOCKLIST, ProvenanceError

        blocked = sorted(set(kwargs) & PROVENANCE_UPDATE_BLOCKLIST)
        if blocked:
            raise ProvenanceError(
                f'QuerySet.update cannot mutate provenance fields {blocked}. '
                f'Use repair_contract_provenance() for governed repairs.'
            )
        return super().update(**kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        from django.utils import timezone
        from contracts.services.contract_provenance import OriginKind, ensure_create_provenance
        from contracts.services.contract_type_catalogue import sync_contract_type_catalogue_fields

        for obj in objs:
            if not (getattr(obj, 'origin_kind', '') or '').strip():
                obj.origin_kind = OriginKind.LEGACY_UNKNOWN
            ensure_create_provenance(obj)
            sync_contract_type_catalogue_fields(obj)
            if obj.provenance_locked_at is None:
                obj.provenance_locked_at = timezone.now()
        return super().bulk_create(objs, *args, **kwargs)


class ContractManager(models.Manager.from_queryset(ContractQuerySet)):
    pass


class Contract(models.Model):
    class Status(models.TextChoices):
        """Record status — business state of the contract record (not workflow stage)."""
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        ACTIVE = 'ACTIVE', 'Active'
        EXPIRED = 'EXPIRED', 'Expired'
        TERMINATED = 'TERMINATED', 'Terminated'
        CANCELLED = 'CANCELLED', 'Cancelled'
        ARCHIVED = 'ARCHIVED', 'Archived'

    class LifecycleStage(models.TextChoices):
        """Workflow stage — where the agreement sits in the operating pipeline."""
        INTAKE = 'INTAKE', 'Intake'
        DRAFTING = 'DRAFTING', 'Drafting'
        INTERNAL_REVIEW = 'INTERNAL_REVIEW', 'Internal review'
        NEGOTIATION = 'NEGOTIATION', 'Negotiation'
        APPROVAL = 'APPROVAL', 'Approval'
        SIGNATURE = 'SIGNATURE', 'Signature'
        EXECUTED = 'EXECUTED', 'Executed'
        OBLIGATION_TRACKING = 'OBLIGATION_TRACKING', 'Obligation tracking'
        RENEWAL = 'RENEWAL', 'Renewal'

    class ContractType(models.TextChoices):
        NDA = 'NDA', 'Non-Disclosure Agreement'
        NON_COMPETE = 'NON_COMPETE', 'Non-Compete / Non-Solicitation Agreement'
        MSA = 'MSA', 'Master Service Agreement'
        SOW = 'SOW', 'Statement of Work'
        SUBCONTRACTOR_SOW = 'SUBCONTRACTOR_SOW', 'Subcontractor SOW Agreement'
        CONSULTING = 'CONSULTING', 'Consulting / Independent Contractor Agreement'
        EMPLOYMENT = 'EMPLOYMENT', 'Employment Agreement'
        LEASE = 'LEASE', 'Lease Agreement'
        LICENSE = 'LICENSE', 'License Agreement'
        SAAS = 'SAAS', 'SaaS Agreement'
        TERMS_OF_SERVICE = 'TERMS_OF_SERVICE', 'Terms of Service / Terms & Conditions'
        VENDOR = 'VENDOR', 'Vendor Agreement'
        PURCHASE_ORDER = 'PURCHASE_ORDER', 'Purchase Order'
        ORDER_CONFIRMATION = 'ORDER_CONFIRMATION', 'Order Confirmation'
        PARTNERSHIP = 'PARTNERSHIP', 'Partnership Agreement'
        RESELLER = 'RESELLER', 'Referral / Reseller / Channel Partner Agreement'
        SETTLEMENT = 'SETTLEMENT', 'Settlement Agreement'
        AMENDMENT = 'AMENDMENT', 'Amendment'
        DPA = 'DPA', 'Data Processing Agreement'
        BAA = 'BAA', 'Business Associate Agreement (BAA)'
        OTHER = 'OTHER', 'Other'

    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class Currency(models.TextChoices):
        USD = 'USD', 'USD ($)'
        EUR = 'EUR', 'EUR (€)'
        GBP = 'GBP', 'GBP (£)'
        CHF = 'CHF', 'CHF (Fr)'
        CAD = 'CAD', 'CAD (C$)'
        AUD = 'AUD', 'AUD (A$)'
        OTHER = 'OTHER', 'Other'

    class PaperSource(models.TextChoices):
        OUR_PAPER = 'OUR_PAPER', 'Our paper'
        COUNTERPARTY_PAPER = 'COUNTERPARTY_PAPER', 'Counterparty paper'

    class OriginKind(models.TextChoices):
        WORKFLOW = 'WORKFLOW', 'Workflow instance'
        MANUAL = 'MANUAL', 'Manual creation'
        UPLOAD = 'UPLOAD', 'Document upload'
        IMPORT_CSV = 'IMPORT_CSV', 'CSV import'
        IMPORT_INBOUND = 'IMPORT_INBOUND', 'Inbound import'
        INTEGRATION = 'INTEGRATION', 'External integration'
        MIGRATION = 'MIGRATION', 'Data migration'
        SEED = 'SEED', 'Seed / demo data'
        ADMIN = 'ADMIN', 'Admin console'
        LEGACY_UNKNOWN = 'LEGACY_UNKNOWN', 'Legacy / unknown'

    objects = ContractManager()

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='contracts')
    title = models.CharField(max_length=200)
    contract_type = models.CharField(
        max_length=20,
        choices=ContractType.choices,
        default=ContractType.OTHER,
        help_text='Transitional denormalized code; canonical type is contract_type_catalogue.',
    )
    contract_type_catalogue = models.ForeignKey(
        'ContractType',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contract_records',
        help_text='Canonical governed Contract Type catalogue row (PAR-CORE-002).',
    )
    content = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.IN_PROGRESS)
    case_phase = models.CharField(
        max_length=20,
        choices=[
            ('intake', 'Intake'),
            ('beoordeling', 'Beoordeling'),
            ('matching', 'Matching'),
            ('plaatsing', 'Plaatsing'),
            ('actief', 'Actief'),
            ('afgerond', 'Afgerond'),
        ],
        default='intake',
    )
    phase_entered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the case entered the current phase',
    )
    counterparty = models.CharField(max_length=200, blank=True)
    business_unit = models.CharField(max_length=120, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=5, choices=Currency.choices, default=Currency.USD)
    governing_law = models.CharField(max_length=200, blank=True, help_text='Governing law jurisdiction')
    jurisdiction = models.CharField(max_length=200, blank=True, help_text='Contract jurisdiction')
    language = models.CharField(max_length=50, default='English', blank=True)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.LOW)
    personal_data_processing = models.BooleanField(default=False, help_text='Agreement involves processing personal data')
    sensitive_data_flag = models.BooleanField(default=False, help_text='Sensitive, high-volume, or non-standard personal data is involved')
    counterparty_privacy_review_required = models.BooleanField(default=False, help_text='Counterparty requires privacy review')
    data_transfer_flag = models.BooleanField(default=False, help_text='Involves cross-border data transfer (EU/US)')
    dpa_attached = models.BooleanField(default=False, help_text='Data Processing Agreement attached')
    scc_attached = models.BooleanField(default=False, help_text='Standard Contractual Clauses attached')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    termination_notice_date = models.DateField(null=True, blank=True)
    lifecycle_stage = models.CharField(
        max_length=20,
        choices=LifecycleStage.choices,
        default=LifecycleStage.DRAFTING,
    )
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    matter = models.ForeignKey('Matter', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    parent_contract = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_contracts',
        help_text='Master or governing agreement that this contract belongs to.',
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_contracts',
        help_text='Active workspace member accountable for this contract.',
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_contracts')
    approved_at = models.DateTimeField(null=True, blank=True)
    paper_source = models.CharField(max_length=24, choices=PaperSource.choices, blank=True, default='')
    source_system = models.CharField(max_length=40, blank=True, default='')
    source_system_id = models.CharField(max_length=255, blank=True, default='')
    source_system_url = models.URLField(blank=True)
    source_last_modified_at = models.DateTimeField(null=True, blank=True)
    # PAR-CORE-003 — Contract Record provenance (immutable once locked).
    origin_kind = models.CharField(
        max_length=32,
        choices=OriginKind.choices,
        blank=True,
        default='',
        help_text='How this Contract Record entered CLM One. Blank only until first save.',
    )
    origin_channel = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Narrower channel within origin_kind (e.g. salesforce, dpa_workflow, ui).',
    )
    origin_workflow = models.ForeignKey(
        'Workflow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='originated_contracts',
        help_text='Originating Workflow Instance when created via workflow.',
    )
    origin_workflow_template = models.ForeignKey(
        'WorkflowTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='originated_contracts',
        help_text='Immutable Workflow Version (template row) pinned at creation.',
    )
    origin_workflow_template_version = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Denormalized template.version at creation for durable lineage.',
    )
    origin_reason = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Reason for manual creation or governed provenance repair.',
    )
    provenance_correlation_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Import batch or correlation identifier.',
    )
    provenance_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When provenance was finalized; fields are immutable afterwards.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_expiring_soon(self):
        if self.end_date and self.status == 'ACTIVE':
            days_until = (self.end_date - date.today()).days
            return 0 <= days_until <= 30
        return False

    @property
    def days_until_expiry(self):
        if self.end_date:
            return (self.end_date - date.today()).days
        return None

    def can_transition_lifecycle_stage(self, new_stage):
        from .services.contract_lifecycle import can_transition_lifecycle_stage as can_transition_contract_lifecycle_stage

        return can_transition_contract_lifecycle_stage(self, new_stage)

    def clean(self):
        from django.core.exceptions import ValidationError
        from .services.lifecycle_dimensions import validate_status_stage_pair

        super().clean()
        errors = {}
        try:
            validate_status_stage_pair(self.status, self.lifecycle_stage)
        except ValidationError as exc:
            errors['status'] = exc.messages
            errors['lifecycle_stage'] = exc.messages
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Enforce PDR-0002 status/stage pairing and PAR-CORE-003 provenance lock.

        Validation runs when status or lifecycle_stage is written (including
        creates). Partial updates that omit both fields leave historical pairs
        untouched so migrations/jobs can update unrelated columns safely.

        On create, if status is set with the model-default ``DRAFTING`` stage and
        the pair is illegal (common test/factory pattern for ``ACTIVE``), coerce
        the stage to the canonical resting stage for that status. Explicit
        updates that write an illegal pair still raise.

        Pass ``skip_lifecycle_validation=True`` only for proven migration or
        repair paths — never for product writers.

        Provenance fields are immutable once ``provenance_locked_at`` is set.
        Pass ``allow_provenance_mutation=True`` only from
        ``assign_and_lock_provenance`` / ``repair_contract_provenance`` /
        ``pin_workflow_provenance``.
        """
        skip_lifecycle_validation = kwargs.pop('skip_lifecycle_validation', False)
        allow_provenance_mutation = kwargs.pop('allow_provenance_mutation', False)
        update_fields = kwargs.get('update_fields')

        previous_provenance = None
        if self.pk and not allow_provenance_mutation:
            previous_provenance = (
                type(self).objects.filter(pk=self.pk)
                .values(
                    'origin_kind',
                    'origin_channel',
                    'origin_workflow_id',
                    'origin_workflow_template_id',
                    'origin_workflow_template_version',
                    'origin_reason',
                    'provenance_correlation_id',
                    'provenance_locked_at',
                    'source_system',
                    'source_system_id',
                    'created_by_id',
                )
                .first()
            )
            if previous_provenance and previous_provenance.get('provenance_locked_at'):
                from contracts.services.contract_provenance import assert_provenance_immutable
                assert_provenance_immutable(self, previous=previous_provenance)

        if self.pk is None and not allow_provenance_mutation:
            from contracts.services.contract_provenance import ensure_create_provenance
            ensure_create_provenance(self)
            if update_fields is not None:
                extra = {'origin_kind', 'provenance_locked_at'}
                kwargs['update_fields'] = list(dict.fromkeys(list(update_fields) + list(extra)))

        from contracts.services.contract_type_catalogue import sync_contract_type_catalogue_fields
        sync_contract_type_catalogue_fields(self)
        if update_fields is not None:
            extra_type = {'contract_type', 'contract_type_catalogue'}
            kwargs['update_fields'] = list(dict.fromkeys(list(kwargs.get('update_fields', update_fields)) + list(extra_type)))

        should_validate = not skip_lifecycle_validation
        if should_validate and update_fields is not None:
            fields = set(update_fields)
            should_validate = ('status' in fields) or ('lifecycle_stage' in fields)
        if should_validate:
            from django.core.exceptions import ValidationError
            from .services.lifecycle_dimensions import (
                is_valid_status_stage_pair,
                validate_status_stage_pair,
            )

            if (
                self.pk is None
                and not is_valid_status_stage_pair(self.status, self.lifecycle_stage)
                and self.lifecycle_stage == self.LifecycleStage.DRAFTING
            ):
                from .services.contract_import_lifecycle import default_stage_for_status
                self.lifecycle_stage = default_stage_for_status(self.status)
                if update_fields is not None and 'lifecycle_stage' not in update_fields:
                    kwargs['update_fields'] = list(kwargs.get('update_fields', update_fields)) + ['lifecycle_stage']
            try:
                validate_status_stage_pair(self.status, self.lifecycle_stage)
            except ValidationError:
                raise
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['organization', 'status', '-updated_at'], name='ctr_org_stat_upd_ix'),
            models.Index(fields=['organization', '-updated_at'], name='ctr_org_upd_ix'),
            models.Index(fields=['organization', 'end_date'], name='ctr_org_end_ix'),
            models.Index(fields=['organization', 'renewal_date'], name='ctr_org_renew_ix'),
            models.Index(fields=['organization', 'created_at'], name='ctr_org_created_ix'),
            models.Index(fields=['organization', 'source_system', 'source_system_id'], name='ctr_org_src_ref_ix'),
            models.Index(fields=['organization', 'origin_kind'], name='ctr_org_origin_ix'),
            models.Index(fields=['organization', 'provenance_correlation_id'], name='ctr_org_prov_corr_ix'),
            models.Index(fields=['organization', 'contract_type_catalogue'], name='ctr_org_type_cat_ix'),
        ]


class ContractTemplate(models.Model):
    """A pre-approved starting draft for a given contract type.

    Body text may contain `{{merge_field}}` tokens (see
    contracts.services.contract_templates.MERGE_FIELDS) that get substituted
    with the new contract's own field values at save time — see
    render_merge_fields() and ContractCreateView.form_valid(). Global/shared
    across organizations for now; not org-scoped.
    """
    name = models.CharField(max_length=200)
    contract_type = models.CharField(max_length=20, choices=Contract.ContractType.choices)
    description = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['contract_type', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_contract_type_display()})'


class DocumentQuerySet(models.QuerySet):
    """Block QuerySet.update from bypassing document version immutability."""

    def update(self, **kwargs):
        from contracts.services.document_version_service import IMMUTABLE_DOCUMENT_FIELDS, DocumentVersionError

        blocked = sorted(set(kwargs) & IMMUTABLE_DOCUMENT_FIELDS)
        if blocked:
            raise DocumentVersionError(
                f'QuerySet.update cannot mutate immutable document version fields {blocked}. '
                f'Create a new document version instead.'
            )
        return super().update(**kwargs)


class DocumentManager(models.Manager.from_queryset(DocumentQuerySet)):
    pass


class Document(models.Model):
    class DocType(models.TextChoices):
        CONTRACT = 'CONTRACT', 'Contract Document'
        AMENDMENT = 'AMENDMENT', 'Amendment'
        EXHIBIT = 'EXHIBIT', 'Exhibit/Attachment'
        CORRESPONDENCE = 'CORRESPONDENCE', 'Correspondence'
        COURT_FILING = 'COURT_FILING', 'Court Filing'
        PLEADING = 'PLEADING', 'Pleading'
        DISCOVERY = 'DISCOVERY', 'Discovery'
        MEMO = 'MEMO', 'Memorandum'
        RESEARCH = 'RESEARCH', 'Legal Research'
        INVOICE = 'INVOICE', 'Invoice'
        TEMPLATE = 'TEMPLATE', 'Template'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        """Document state — artifact maturity (not contract record status)."""
        DRAFT = 'DRAFT', 'Draft'
        FINAL = 'FINAL', 'Final'
        EXECUTED = 'EXECUTED', 'Executed'
        SUPERSEDED = 'SUPERSEDED', 'Superseded'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    title = models.CharField(max_length=300)
    document_type = models.CharField(max_length=20, choices=DocType.choices, default=DocType.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)
    version = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions')
    logical_document = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='logical_versions',
        help_text='Logical document identity root; null until first version is saved.',
    )
    version_source = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='How this version entered CLM One (manual_upload, ai_upload, …).',
    )
    version_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When file/content metadata became immutable for this version row.',
    )
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True)
    is_privileged = models.BooleanField(default=False)
    is_confidential = models.BooleanField(default=False)
    # A deliberate, document-level boundary for the counterparty workspace.
    # Never infer sharing from a contract invitation: documents can contain
    # internal legal analysis, even when the contract itself is shared.
    share_with_counterparty = models.BooleanField(
        default=False,
        help_text='Make this document available to approved counterparty collaborators.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DocumentManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'logical_document', '-version'], name='doc_org_logical_ver_ix'),
        ]

    def __str__(self):
        return f'{self.title} (v{self.version})'

    def clean(self):
        from django.core.exceptions import ValidationError
        from .services.lifecycle_dimensions import validate_document_state_for_contract

        super().clean()
        if not self.contract_id:
            return
        contract = self.contract
        try:
            validate_document_state_for_contract(
                self.status,
                contract_status=getattr(contract, 'status', None),
                contract_stage=getattr(contract, 'lifecycle_stage', None),
            )
        except ValidationError as exc:
            raise ValidationError({'status': exc.messages}) from exc

    def save(self, *args, **kwargs):
        skip_version_immutability = kwargs.pop('skip_version_immutability', False)
        update_fields = kwargs.get('update_fields')
        previous = None
        if self.pk and not skip_version_immutability:
            previous = (
                type(self).objects.filter(pk=self.pk)
                .values(
                    'file', 'file_hash', 'file_size', 'mime_type', 'version',
                    'parent_document_id', 'logical_document_id', 'uploaded_by_id',
                    'version_locked_at', 'version_source',
                )
                .first()
            )
            if previous and previous.get('version_locked_at'):
                from contracts.services.document_version_service import assert_document_version_immutable
                assert_document_version_immutable(self, previous=previous)

        if self.file:
            self.file_size = self.file.size
            self.mime_type = getattr(self.file, 'content_type', '')
            if not skip_version_immutability or not self.file_hash:
                try:
                    hasher = hashlib.sha256()
                    for chunk in self.file.chunks():
                        hasher.update(chunk)
                    if hasattr(self.file, 'seek'):
                        self.file.seek(0)
                    self.file_hash = hasher.hexdigest()
                except Exception:
                    pass
        super().save(*args, **kwargs)
        if self.file:
            try:
                from .services.document_ocr import queue_document_ocr_review

                queue_document_ocr_review(self)
            except Exception:
                pass
        if not skip_version_immutability:
            try:
                from .services.document_version_service import ensure_canonical_version_for_document
                ensure_canonical_version_for_document(self)
            except Exception:
                pass

    @property
    def file_extension(self):
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ''

    # Soft deletion (Phase 4E): legal documents are tombstoned, not hard-removed.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_documents',
    )

    def _check_retention_hold(self):
        active_holds = LegalHold.objects.filter(status=LegalHold.Status.ACTIVE)
        if self.matter_id and active_holds.filter(matter_id=self.matter_id).exists():
            raise PermissionError(
                'This document cannot be deleted: its matter is under an active legal hold.'
            )
        if self.client_id and active_holds.filter(client_id=self.client_id).exists():
            raise PermissionError(
                'This document cannot be deleted: its client is under an active legal hold.'
            )

    def _check_evidentiary(self):
        """Block soft-deletion of evidentiary records (Phase 5I).

        Derived entirely from existing CLM One model relationships — no second
        parallel document-classification system is introduced.

        A document is evidentiary when it falls into any of:

        1. It is the direct subject of a completed (SIGNED) signature request.
           This covers: signed documents, completion evidence, signature packets.
        2. It has reached FINAL or EXECUTED status on a contract whose lifecycle
           stage is at/after EXECUTED — i.e. the executed source document of a
           binding agreement.
        3. It is a final court filing, pleading, or discovery document.

        Unsigned/cancelled drafts follow the ordinary deletion policy.
        """
        if not self.pk:
            return
        # 1. Completed signature request directly names this document.
        if self.signature_requests.filter(status='SIGNED').exists():
            raise PermissionError(
                'This document cannot be deleted: it is the subject of a '
                'completed signature request.'
            )
        # 2. FINAL/EXECUTED source document on an executed/active contract.
        executed_stages = {'EXECUTED', 'OBLIGATION_TRACKING', 'RENEWAL'}
        if (
            self.status in {self.Status.FINAL, self.Status.EXECUTED}
            and self.contract_id
            and self.contract.lifecycle_stage in executed_stages
        ):
            raise PermissionError(
                'This document cannot be deleted: it is a final document on '
                'an executed contract.'
            )
        # 3. Final court / legal filing.
        legal_types = {self.DocType.COURT_FILING, self.DocType.PLEADING, self.DocType.DISCOVERY}
        if self.document_type in legal_types and self.status in {self.Status.FINAL, self.Status.EXECUTED}:
            raise PermissionError(
                'This document cannot be deleted: it is a final court/legal record.'
            )

    def delete(self, *args, **kwargs):
        self._check_retention_hold()
        self._check_evidentiary()
        super().delete(*args, **kwargs)


class DocumentVersionQuerySet(models.QuerySet):
    """Block QuerySet.update from bypassing DocumentVersion immutability."""

    def update(self, **kwargs):
        from contracts.services.document_version_service import IMMUTABLE_VERSION_FIELDS, DocumentVersionError

        blocked = sorted(set(kwargs) & IMMUTABLE_VERSION_FIELDS)
        if blocked:
            raise DocumentVersionError(
                f'QuerySet.update cannot mutate immutable DocumentVersion fields {blocked}.'
            )
        return super().update(**kwargs)


class DocumentVersionManager(models.Manager.from_queryset(DocumentVersionQuerySet)):
    pass


class DocumentVersion(models.Model):
    """Immutable Document Version — one file/content state (CANONICAL_DOMAIN_MODEL §2.16)."""

    class Source(models.TextChoices):
        MANUAL_UPLOAD = 'manual_upload', 'Manual upload'
        AI_UPLOAD = 'ai_upload', 'AI-assisted upload'
        CONTRACT_ATTACHMENT = 'contract_attachment', 'Contract attachment'
        DOCUMENT_EDIT = 'document_edit', 'Document edit / new version'
        COUNTERPARTY_REVISION = 'counterparty_revision', 'Counterparty revision'
        GENERATED = 'generated', 'Generated document'
        IMPORT = 'import', 'Import'
        LEGACY_UNKNOWN = 'legacy_unknown', 'Legacy / unknown'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='document_versions')
    logical_document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='version_records',
    )
    document_row = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='canonical_version',
    )
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    document_type = models.CharField(max_length=20, choices=Document.DocType.choices)
    status = models.CharField(max_length=20, choices=Document.Status.choices)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True, default='')
    file_hash = models.CharField(max_length=64, blank=True, default='')
    original_filename = models.CharField(max_length=255, blank=True, default='')
    source = models.CharField(max_length=64, choices=Source.choices, default=Source.LEGACY_UNKNOWN)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    derived_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_versions',
    )
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    checksum_missing = models.BooleanField(
        default=False,
        help_text='True when checksum could not be computed from available bytes.',
    )
    version_locked_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DocumentVersionManager()

    class Meta:
        ordering = ['logical_document_id', '-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['logical_document', 'version_number'],
                name='docver_logical_version_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'logical_document'], name='docver_org_logical_ix'),
            models.Index(fields=['contract', '-version_number'], name='docver_contract_ver_ix'),
        ]

    def __str__(self):
        return f'{self.title} v{self.version_number}'

    def save(self, *args, **kwargs):
        skip_immutability = kwargs.pop('skip_version_immutability', False)
        previous = None
        if self.pk and not skip_immutability:
            previous = (
                type(self).objects.filter(pk=self.pk)
                .values(*[
                    'file', 'file_hash', 'file_size', 'mime_type', 'original_filename',
                    'version_number', 'source', 'uploaded_by_id', 'derived_from_id',
                    'logical_document_id', 'version_locked_at', 'checksum_missing',
                    'organization_id', 'contract_id',
                ])
                .first()
            )
            if previous and previous.get('version_locked_at'):
                from contracts.services.document_version_service import assert_document_version_row_immutable
                assert_document_version_row_immutable(self, previous=previous)
        if not self.version_locked_at:
            self.version_locked_at = timezone.now()
        super().save(*args, **kwargs)


class DocumentOCRReview(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='document_ocr_reviews')
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='ocr_review')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    extracted_text = models.TextField(blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=50, blank=True)
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ocr_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Text extraction review for {self.document.title} ({self.get_status_display()})'

    @property
    def needs_manual_review(self):
        return (self.source or '').startswith('manual-review')

    @property
    def extraction_reason(self):
        """Human-readable status of automatic text extraction (not image OCR)."""
        reasons = {
            'manual-review-image-pdf':
                'No machine-readable text found (scanned/image-only PDF). '
                'Automatic text extraction cannot read images — manual review required.',
            'manual-review-empty': 'No readable text found in the document — manual review required.',
            'manual-review': 'Unsupported or unreadable file — manual review required.',
            'no-file': 'No file attached.',
            'pdf-extraction': 'Text extracted from PDF.',
            'docx-extraction': 'Text extracted from Word document.',
            'text-extraction': 'Text extracted.',
        }
        return reasons.get(self.source or '', 'Pending text extraction.')

    def mark_verified(self, reviewer=None):
        self.status = self.Status.VERIFIED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()

    def mark_rejected(self, reviewer=None):
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()


class AIExtractionSpan(models.Model):
    """A text-span citation produced by the AI extraction rules engine."""

    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Needs review'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        DISMISSED = 'DISMISSED', 'Dismissed'

    class RiskLevel(models.TextChoices):
        CLEAR = 'CLEAR', 'Clear'
        REVIEW = 'REVIEW', 'Review needed'
        RISK = 'RISK', 'Active risk'

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='ai_extraction_spans'
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='ai_extraction_spans'
    )
    label = models.CharField(max_length=100)
    span_text = models.TextField()
    start_char = models.PositiveIntegerField()
    end_char = models.PositiveIntegerField()
    confidence = models.DecimalField(max_digits=5, decimal_places=4)
    extraction_model = models.CharField(max_length=100, default='rules-engine-v1')
    rationale = models.CharField(max_length=500, blank=True)
    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.REVIEW,
    )
    source_template = models.ForeignKey(
        'ClauseTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_extraction_spans',
        help_text='Approved clause-library source matched to this citation.',
    )
    review_status = models.CharField(
        max_length=12,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_ai_extraction_spans',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_char']
        indexes = [
            models.Index(fields=['document', 'label']),
            models.Index(fields=['organization', 'label']),
            models.Index(fields=['organization', 'review_status']),
        ]

    def __str__(self):
        return f'{self.label} span [{self.start_char}:{self.end_char}] on {self.document_id}'

    @property
    def label_display(self):
        return self.label.replace('_', ' ').title()


class DocumentReviewRun(models.Model):
    """The governed, auditable processing record for one uploaded version."""

    class Status(models.TextChoices):
        UPLOADED = 'UPLOADED', 'Uploaded'
        EXTRACTING = 'EXTRACTING', 'Extracting'
        CLASSIFICATION_REQUIRED = 'CLASSIFICATION_REQUIRED', 'Classification required'
        PLAYBOOK_REQUIRED = 'PLAYBOOK_REQUIRED', 'Playbook required'
        AI_REVIEW_IN_PROGRESS = 'AI_REVIEW_IN_PROGRESS', 'AI review in progress'
        AI_REVIEW_INCOMPLETE = 'AI_REVIEW_INCOMPLETE', 'AI review incomplete'
        READY = 'READY', 'AI review ready'
        HUMAN_REVIEW_IN_PROGRESS = 'HUMAN_REVIEW_IN_PROGRESS', 'Human review in progress'
        REVIEW_COMPLETED = 'REVIEW_COMPLETED', 'Review completed'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='document_review_runs')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='document_review_runs')
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='review_run')
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.UPLOADED)
    current_step = models.CharField(max_length=64, default='Uploaded')
    progress_steps = models.JSONField(default=list, blank=True)
    extracted_metadata = models.JSONField(default=dict, blank=True)
    governance_sources = models.JSONField(default=dict, blank=True)
    primary_next_action = models.CharField(max_length=300, blank=True)
    review_objective = models.CharField(max_length=300, blank=True)
    review_model = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['contract', '-started_at'], name='drr_contract_started_ix'),
            models.Index(fields=['organization', 'status'], name='drr_org_status_ix'),
        ]

    def __str__(self):
        return f'Review of {self.document} ({self.get_status_display()})'


class ContractReviewFinding(models.Model):
    """A human-owned assessment grounded in an extracted clause citation."""

    class Severity(models.TextChoices):
        CRITICAL = 'CRITICAL', 'Critical'
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'
        INFORMATION = 'INFORMATION', 'Information'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        DISMISSED = 'DISMISSED', 'Dismissed'
        RESOLVED = 'RESOLVED', 'Resolved'
        ESCALATED = 'ESCALATED', 'Escalated'
        INFORMATION_REQUESTED = 'INFORMATION_REQUESTED', 'Information requested'
        EXCEPTION_REQUESTED = 'EXCEPTION_REQUESTED', 'Exception requested'

    class DismissalReason(models.TextChoices):
        ACCEPTED_BUSINESS_RISK = 'ACCEPTED_BUSINESS_RISK', 'Accepted business risk'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'False positive'
        COVERED_ELSEWHERE = 'COVERED_ELSEWHERE', 'Covered elsewhere'
        APPROVED_EXCEPTION = 'APPROVED_EXCEPTION', 'Approved exception'
        NOT_APPLICABLE = 'NOT_APPLICABLE', 'Not applicable'
        OTHER = 'OTHER', 'Other'

    review_run = models.ForeignKey(DocumentReviewRun, on_delete=models.CASCADE, related_name='findings')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='review_findings')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='review_findings')
    source_span = models.OneToOneField(
        AIExtractionSpan, on_delete=models.SET_NULL, null=True, blank=True, related_name='review_finding'
    )
    risk_log = models.OneToOneField(
        'RiskLog', on_delete=models.SET_NULL, null=True, blank=True, related_name='review_finding'
    )
    title = models.CharField(max_length=240)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.MEDIUM)
    source_clause = models.CharField(max_length=120, blank=True)
    source_page = models.PositiveIntegerField(null=True, blank=True)
    source_excerpt = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    business_legal_impact = models.TextField(blank=True)
    conflicting_rule = models.TextField(blank=True)
    approved_position = models.TextField(blank=True)
    acceptable_fallback = models.TextField(blank=True)
    suggested_redline = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    recommended_action = models.TextField(blank=True)
    assigned_reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_review_findings'
    )
    status = models.CharField(max_length=28, choices=Status.choices, default=Status.OPEN)
    assessment = models.TextField(blank=True)
    redline_draft = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    dismissal_reason = models.CharField(max_length=32, choices=DismissalReason.choices, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_review_findings')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_review_findings')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['severity', 'created_at']
        indexes = [
            models.Index(fields=['contract', 'status'], name='crf_contract_status_ix'),
            models.Index(fields=['review_run', 'severity'], name='crf_run_severity_ix'),
        ]

    def __str__(self):
        return self.title


class TimeEntry(models.Model):
    class ActivityType(models.TextChoices):
        RESEARCH = 'RESEARCH', 'Legal Research'
        DRAFTING = 'DRAFTING', 'Document Drafting'
        REVIEW = 'REVIEW', 'Document Review'
        MEETING = 'MEETING', 'Meeting/Conference'
        COURT = 'COURT', 'Court Appearance'
        DEPOSITION = 'DEPOSITION', 'Deposition'
        NEGOTIATION = 'NEGOTIATION', 'Negotiation'
        COMMUNICATION = 'COMMUNICATION', 'Communication'
        TRAVEL = 'TRAVEL', 'Travel'
        ADMIN = 'ADMIN', 'Administrative'
        OTHER = 'OTHER', 'Other'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='time_entries')
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, related_name='time_entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_entries')
    date = models.DateField(default=date.today)
    hours = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.1'))])
    description = models.TextField()
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.OTHER)
    rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_billable = models.BooleanField(default=True)
    is_billed = models.BooleanField(default=False)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='time_entries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} - {self.matter} - {self.hours}h'

    @property
    def total_amount(self):
        if self.rate:
            return self.hours * self.rate
        try:
            return self.hours * self.user.profile.hourly_rate
        except Exception:
            return Decimal('0')

    def save(self, *args, **kwargs):
        if not self.rate:
            try:
                self.rate = self.user.profile.hourly_rate
            except Exception:
                pass
        super().save(*args, **kwargs)


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        PAID = 'PAID', 'Paid'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        VOID = 'VOID', 'Void'
        WRITTEN_OFF = 'WRITTEN_OFF', 'Written Off'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='invoices')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(default=date.today)
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=200, default='Net 30')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return f'Invoice #{self.invoice_number} - {self.client.name}'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last = Invoice.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.invoice_number = f'INV-{next_num:05d}'
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total_amount = self.subtotal + self.tax_amount
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def is_overdue(self):
        return self.status in ['SENT', 'PARTIALLY_PAID'] and self.due_date < date.today()


class TrustAccount(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='trust_accounts')
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='trust_accounts')
    account_name = models.CharField(max_length=200)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.account_name} - {self.client.name} (${self.balance})'


class TrustTransaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        TRANSFER = 'TRANSFER', 'Transfer'
        REFUND = 'REFUND', 'Refund'

    account = models.ForeignKey(TrustAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=300)
    reference_number = models.CharField(max_length=100, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_transaction_type_display()} - ${self.amount}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.transaction_type in ['DEPOSIT']:
            self.account.balance += self.amount
        elif self.transaction_type in ['WITHDRAWAL', 'TRANSFER']:
            self.account.balance -= self.amount
        elif self.transaction_type == 'REFUND':
            self.account.balance -= self.amount
        self.account.save()


class DeadlineQuerySet(models.QuerySet):
    """Custom queryset for Deadline with organization-scoping support."""
    def for_organization(self, organization):
        """Filter deadlines that belong to a specific organization via contract or matter."""
        if not organization:
            return self.none()
        from django.db.models import Q
        return self.filter(
            Q(contract__organization=organization) | Q(matter__organization=organization)
        )


class DeadlineManager(models.Manager):
    """Custom manager for Deadline."""
    def get_queryset(self):
        return DeadlineQuerySet(self.model, using=self._db)
    
    def for_organization(self, organization):
        """Filter deadlines that belong to a specific organization."""
        return self.get_queryset().for_organization(organization)


class Deadline(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class DeadlineType(models.TextChoices):
        COURT = 'COURT', 'Court Deadline'
        FILING = 'FILING', 'Filing Deadline'
        SOL = 'SOL', 'Statute of Limitations'
        CONTRACT = 'CONTRACT', 'Contract Deadline'
        REGULATORY = 'REGULATORY', 'Regulatory Deadline'
        INTERNAL = 'INTERNAL', 'Internal Deadline'
        CLIENT = 'CLIENT', 'Client Deadline'
        RENEWAL = 'RENEWAL', 'Renewal / Termination'
        PAYMENT = 'PAYMENT', 'Payment Obligation'
        NDA_EXPIRY = 'NDA_EXPIRY', 'NDA Expiry'
        SLA = 'SLA', 'SLA Obligation'
        OTHER = 'OTHER', 'Other'

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    deadline_type = models.CharField(max_length=20, choices=DeadlineType.choices, default=DeadlineType.OTHER)
    auto_generated = models.BooleanField(default=False)
    generation_source = models.CharField(
        max_length=20,
        choices=[
            ('MANUAL', 'Handmatig'),
            ('INTAKE', 'Intake'),
            ('ASSESSMENT', 'Beoordeling'),
            ('MATCHING', 'Matching'),
            ('PLACEMENT', 'Plaatsing'),
        ],
        default='MANUAL',
    )
    task_type = models.CharField(
        max_length=30,
        choices=[
            ('INTAKE_COMPLETE', 'Intake afronden'),
            ('ASSESSMENT_PERFORM', 'Beoordeling uitvoeren'),
            ('SELECT_MATCH', 'Match selecteren'),
            ('CONTACT_PROVIDER', 'Aanbieder contacteren'),
            ('CONFIRM_PLACEMENT', 'Plaatsing bevestigen'),
            ('EVALUATE', 'Evaluatie uitvoeren'),
        ],
        default='INTAKE_COMPLETE',
        verbose_name='Type taak',
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField()
    due_time = models.TimeField(null=True, blank=True)
    reminder_days = models.PositiveIntegerField(default=7)
    due_diligence_process = models.ForeignKey(
        'DueDiligenceProcess',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='followup_tasks',
        verbose_name='Casus',
    )
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='deadlines')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='deadlines')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deadlines')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_deadlines')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_deadlines')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DeadlineManager()

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f'{self.title} - Due: {self.due_date}'

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_date < date.today()

    @property
    def days_remaining(self):
        if self.is_completed:
            return None
        return (self.due_date - date.today()).days

    @property
    def needs_reminder(self):
        if self.is_completed:
            return False
        days = (self.due_date - date.today()).days
        return 0 < days <= self.reminder_days


class AuditWriteError(Exception):
    """Raised when application code attempts to mutate or delete an audit row."""


class AuditLogQuerySet(models.QuerySet):
    """Append-only: block bulk update/delete through ordinary product paths."""

    def update(self, *args, **kwargs):
        raise AuditWriteError('AuditLog is append-only; bulk update is not allowed.')

    def delete(self, *args, **kwargs):
        raise AuditWriteError('AuditLog is append-only; bulk delete is not allowed.')

    def _raw_delete(self, *args, **kwargs):  # used by cascade collector
        raise AuditWriteError('AuditLog is append-only; deletion is not allowed.')


class AuditLogManager(models.Manager.from_queryset(AuditLogQuerySet)):
    pass


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        VIEW = 'VIEW', 'Viewed'
        LOGIN = 'LOGIN', 'Logged In'
        LOGOUT = 'LOGOUT', 'Logged Out'
        EXPORT = 'EXPORT', 'Exported'
        APPROVE = 'APPROVE', 'Approved'
        REJECT = 'REJECT', 'Rejected'

    class ActorType(models.TextChoices):
        HUMAN = 'human', 'Human'
        SERVICE = 'service', 'Service account'
        SYSTEM = 'system', 'System'
        SCHEDULED_JOB = 'scheduled_job', 'Scheduled job'
        WEBHOOK = 'webhook', 'Webhook'
        MIGRATION = 'migration', 'Migration'

    class Outcome(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILURE = 'failure', 'Failure'
        BLOCKED = 'blocked', 'Blocked'

    # Tenant boundary. PROTECT so audit history is never cascade-deleted when an
    # organization is removed (orgs are soft-deactivated in product, not hard
    # deleted). NULL = a system/global event with no single tenant.
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, null=True, blank=True,
        related_name='audit_logs',
    )
    # Audit hashes include user_id. Keep this historical identifier immutable
    # when an account is removed instead of nulling it and breaking the chain.
    # The missing user is intentionally represented as an unavailable actor in
    # the UI; a database constraint would prevent the account-retention policy
    # from being applied.
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_constraint=False,
    )
    actor_type = models.CharField(max_length=20, choices=ActorType.choices, default=ActorType.SYSTEM)
    action = models.CharField(max_length=20, choices=Action.choices)
    # Canonical, stable event key (e.g. 'approval.approved'). Free-form display
    # text belongs in the UI layer, not here.
    event_type = models.CharField(max_length=100, blank=True, default='')
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.SUCCESS)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    # Correlation / provenance.
    request_id = models.CharField(max_length=64, blank=True, default='')
    job_run_id = models.UUIDField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Tamper-evident per-organization hash chain.
    seq = models.PositiveBigIntegerField(
        null=True, blank=True,
        help_text='Per-organization monotonic sequence; NULL on legacy rows.',
    )
    prev_hash = models.CharField(max_length=64, blank=True, default='')
    entry_hash = models.CharField(
        max_length=64, blank=True,
        help_text='SHA-256 of the canonical entry payload incl. prev_hash; see '
                  'contracts.services.audit. Blank/legacy on pre-chain rows.',
    )
    hash_version = models.PositiveSmallIntegerField(
        default=1,
        help_text='1 = legacy self-hash (no chain); 2 = per-org hash chain.',
    )

    objects = AuditLogManager()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['organization', 'seq'], name='audit_org_seq_ix'),
            models.Index(fields=['organization', '-timestamp'], name='audit_org_ts_ix'),
            models.Index(fields=['event_type'], name='audit_event_type_ix'),
        ]
        constraints = [
            # Tenant chains: (organization, seq) unique where organization is set.
            models.UniqueConstraint(
                fields=['organization', 'seq'],
                condition=models.Q(organization__isnull=False),
                name='audit_org_seq_uniq',
            ),
            # System/global chain: seq unique where organization IS NULL. A plain
            # (organization, seq) unique would NOT enforce this on PostgreSQL,
            # which treats NULLs as distinct — so the system chain needs its own
            # partial constraint. (Legacy v1 rows have seq IS NULL and are exempt
            # from both, since seq is part of each constraint.)
            models.UniqueConstraint(
                fields=['seq'],
                condition=models.Q(organization__isnull=True, seq__isnull=False),
                name='audit_system_seq_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.user} {self.get_action_display()} {self.model_name} #{self.object_id}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AuditWriteError('AuditLog rows are append-only and cannot be modified.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditWriteError('AuditLog rows are append-only and cannot be deleted.')

    def compute_hash(self) -> str:
        """Legacy v1 self-hash (kept for verifying pre-chain rows only).

        New rows use the per-organization chain in contracts.services.audit.
        """
        material = (
            f'{self.pk}:{self.user_id}:{self.action}:{self.model_name}:'
            f'{self.object_id}:{self.timestamp.isoformat() if self.timestamp else ""}:'
            f'{json.dumps(self.changes, sort_keys=True, default=str)}'
        )
        return hashlib.sha256(material.encode('utf-8')).hexdigest()


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        DEADLINE = 'DEADLINE', 'Deadline Reminder'
        TASK = 'TASK', 'Task Assignment'
        CONTRACT = 'CONTRACT', 'Contract Update'
        APPROVAL = 'APPROVAL', 'Approval Request'
        SYSTEM = 'SYSTEM', 'System'
        BILLING = 'BILLING', 'Billing'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=300)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='notif_rec_read_created_ix'),
            models.Index(fields=['recipient', '-created_at'], name='notif_rec_created_ix'),
        ]

    def __str__(self):
        return f'{self.title} -> {self.recipient.username}'


class ConflictCheck(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        CLEAR = 'CLEAR', 'No Conflict'
        CONFLICT = 'CONFLICT', 'Conflict Found'
        WAIVED = 'WAIVED', 'Conflict Waived'

    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='conflict_checks')
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='conflict_checks')
    checked_party = models.CharField(max_length=200)
    checked_party_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    conflicts_found = models.TextField(blank=True)
    checked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conflict_checks_performed')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conflict_checks_resolved')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Conflict Check: {self.checked_party} ({self.get_status_display()})'


class TrademarkRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        FILED = 'FILED', 'Filed'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    mark_text = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    goods_services = models.TextField(blank=True)
    filing_basis = models.CharField(max_length=100, blank=True)
    care_form = models.CharField(
        max_length=20,
        choices=[
            ('OUTPATIENT', 'Ambulant'),
            ('DAY_TREATMENT', 'Dagbehandeling'),
            ('RESIDENTIAL', 'Residentieel'),
            ('CRISIS', 'Crisisopvang'),
        ],
        blank=True,
        verbose_name='Zorgvorm',
    )
    decision_notes = models.TextField(blank=True, verbose_name='Besluitnotities')
    due_diligence_process = models.ForeignKey(
        'DueDiligenceProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='indications',
        verbose_name='Casus',
    )
    duration_weeks = models.PositiveIntegerField(null=True, blank=True, verbose_name='Duur (weken, optioneel)')
    proposed_provider = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposed_indications',
        verbose_name='Voorgestelde aanbieder',
    )
    selected_provider = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='selected_indications',
        verbose_name='Geselecteerde aanbieder',
    )
    start_date = models.DateField(null=True, blank=True, verbose_name='Startdatum')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='trademark_requests')
    matter = models.ForeignKey(Matter, on_delete=models.SET_NULL, null=True, blank=True, related_name='trademark_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.mark_text


class LegalTaskQuerySet(models.QuerySet):
    """Custom queryset for LegalTask with organization-scoping support."""
    def for_organization(self, organization):
        """Filter legal tasks that belong to a specific organization via contract or matter."""
        if not organization:
            return self.none()
        from django.db.models import Q
        return self.filter(
            Q(contract__organization=organization) | Q(matter__organization=organization)
        )


class LegalTaskManager(models.Manager):
    """Custom manager for LegalTask."""
    def get_queryset(self):
        return LegalTaskQuerySet(self.model, using=self._db)
    
    def for_organization(self, organization):
        """Filter legal tasks that belong to a specific organization."""
        return self.get_queryset().for_organization(organization)


class LegalTask(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LegalTaskManager()

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class RiskLogQuerySet(models.QuerySet):
    """Custom queryset for RiskLog with organization-scoping support."""
    def for_organization(self, organization):
        """Filter risk logs that belong to a specific organization via contract or matter."""
        if not organization:
            return self.none()
        from django.db.models import Q
        return self.filter(
            Q(contract__organization=organization) | Q(matter__organization=organization)
        )


class RiskLogManager(models.Manager):
    """Custom manager for RiskLog."""
    def get_queryset(self):
        return RiskLogQuerySet(self.model, using=self._db)
    
    def for_organization(self, organization):
        """Filter risk logs that belong to a specific organization."""
        return self.get_queryset().for_organization(organization)


class RiskLog(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class SignalType(models.TextChoices):
        SAFETY = 'SAFETY', 'Veiligheid'
        ESCALATION = 'ESCALATION', 'Escalatie'
        NO_MATCH = 'NO_MATCH', 'Geen match'
        WAIT_EXCEEDED = 'WAIT_EXCEEDED', 'Wachttijd overschreden'
        CAPACITY_ISSUE = 'CAPACITY_ISSUE', 'Capaciteit probleem'
        INTAKE_INCOMPLETE = 'INTAKE_INCOMPLETE', 'Intake incompleet'
        DROPOUT_RISK = 'DROPOUT_RISK', 'Uitval risico'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In opvolging'
        RESOLVED = 'RESOLVED', 'Afgerond'

    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(verbose_name='Omschrijving')
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.MEDIUM, verbose_name='Urgentie')
    signal_type = models.CharField(max_length=30, choices=SignalType.choices, default=SignalType.SAFETY, verbose_name='Type signaal')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, verbose_name='Status')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='risks')
    due_diligence_process = models.ForeignKey(
        'DueDiligenceProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signals',
        verbose_name='Casus',
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_signals',
        verbose_name='Verantwoordelijke',
    )
    follow_up = models.TextField(blank=True, verbose_name='Opvolging')
    mitigation_plan = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RiskLogManager()

    def __str__(self):
        return self.title


class CommandCenterSavedView(models.Model):
    """Persisted workspace view definition for the Command Center.

    This gives the dashboard an explicit data contract for saved views instead
    of hardcoding every tab/filter in the template. The filters are descriptive
    metadata consumed by the Command Center service/UI; they do not enforce
    authorization or workflow transitions.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='command_center_saved_views')
    key = models.SlugField(max_length=60)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='command_center_saved_views_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'key'], name='cc_saved_view_org_key_uniq'),
        ]

    def __str__(self):
        return self.name


class CommandCenterWorkItem(models.Model):
    """Normalized actionable row for the Command Center workbench.

    Rows can point to the existing source record that created the action
    (Contract, DPA finding, ApprovalRequest, Deadline, LegalTask, or RiskLog),
    but the display and ranking fields are denormalized so the dashboard can
    render a stable legal-ops queue without re-running scanners or business
    logic at request time.
    """

    class SourceType(models.TextChoices):
        CONTRACT = 'CONTRACT', 'Contract'
        DPA_CONFLICT = 'DPA_CONFLICT', 'DPA / MSA Conflict'
        APPROVAL = 'APPROVAL', 'Approval'
        DEADLINE = 'DEADLINE', 'Deadline'
        LEGAL_TASK = 'LEGAL_TASK', 'Legal Task'
        RISK = 'RISK', 'Risk'
        REVIEW_MEMO = 'REVIEW_MEMO', 'Review Memo'
        WORKFLOW = 'WORKFLOW', 'Workflow'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        BLOCKED = 'BLOCKED', 'Blocked'
        DONE = 'DONE', 'Done'
        DISMISSED = 'DISMISSED', 'Dismissed'

    class Priority(models.IntegerChoices):
        LOW = 30, 'Low'
        MEDIUM = 50, 'Medium'
        HIGH = 70, 'High'
        CRITICAL = 90, 'Critical'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='command_center_work_items')
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_model = models.CharField(max_length=80, blank=True)
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)

    title = models.CharField(max_length=240)
    subtitle = models.CharField(max_length=300, blank=True)
    item_type = models.CharField(max_length=60, blank=True)
    stage = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    risk_level = models.CharField(max_length=10, choices=Contract.RiskLevel.choices, default=Contract.RiskLevel.LOW)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.MEDIUM)

    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='command_center_work_items')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    dpa_review_pack = models.ForeignKey('DPAReviewPack', on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    dpa_risk_item = models.ForeignKey('DPARiskItem', on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    approval_request = models.ForeignKey('ApprovalRequest', on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    deadline = models.ForeignKey(Deadline, on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    legal_task = models.ForeignKey(LegalTask, on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    risk_log = models.ForeignKey(RiskLog, on_delete=models.CASCADE, null=True, blank=True, related_name='command_center_work_items')
    workflow = models.ForeignKey('Workflow', on_delete=models.SET_NULL, null=True, blank=True, related_name='command_center_work_items')

    due_at = models.DateTimeField(null=True, blank=True)
    action_label = models.CharField(max_length=80, default='Open')
    action_path = models.CharField(max_length=500, blank=True)
    flags = models.JSONField(default=dict, blank=True)
    last_source_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'due_at', '-updated_at']
        indexes = [
            models.Index(fields=['organization', 'status', '-priority'], name='cc_work_org_status_pri_ix'),
            models.Index(fields=['organization', 'source_type', 'source_object_id'], name='cc_work_org_source_ix'),
            models.Index(fields=['organization', 'due_at'], name='cc_work_org_due_ix'),
            models.Index(fields=['organization', 'owner', 'status'], name='cc_work_org_owner_ix'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'source_type', 'source_model', 'source_object_id'],
                name='cc_work_source_uniq',
            ),
        ]

    def __str__(self):
        return self.title


class CommandCenterRailItem(models.Model):
    """Persisted right-rail command signal for approvals, deadlines, memos, etc."""

    class Kind(models.TextChoices):
        APPROVALS = 'APPROVALS', 'Approvals'
        DEADLINES = 'DEADLINES', 'Deadlines'
        DPA_CONFLICTS = 'DPA_CONFLICTS', 'DPA / MSA Conflicts'
        REVIEW_MEMOS = 'REVIEW_MEMOS', 'Review Memos'
        RISK = 'RISK', 'Risk'
        ACTIVITY = 'ACTIVITY', 'Activity'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='command_center_rail_items')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=160)
    summary = models.CharField(max_length=300, blank=True)
    count = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=10, choices=Contract.RiskLevel.choices, default=Contract.RiskLevel.LOW)
    action_label = models.CharField(max_length=80, default='Open')
    action_path = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'kind'], name='cc_rail_org_kind_uniq'),
        ]

    def __str__(self):
        return self.title


class ReviewMemo(models.Model):
    """First-class review memo record surfaced in the Command Center.

    DPAReviewPack.review_memo remains for backwards compatibility; this model
    records memos as their own searchable/referencable artifacts and can point
    back to the DPA review pack or contract that generated them.
    """

    class MemoType(models.TextChoices):
        DPA_REVIEW = 'DPA_REVIEW', 'DPA Review'
        RISK_REVIEW = 'RISK_REVIEW', 'Risk Review'
        APPROVAL = 'APPROVAL', 'Approval'
        GENERAL = 'GENERAL', 'General'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='review_memos')
    title = models.CharField(max_length=240)
    memo_type = models.CharField(max_length=20, choices=MemoType.choices, default=MemoType.GENERAL)
    body = models.TextField()
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='review_memos')
    dpa_review_pack = models.ForeignKey('DPAReviewPack', on_delete=models.CASCADE, null=True, blank=True, related_name='review_memos')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='review_memos_generated')
    generated_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['organization', '-generated_at'], name='review_memo_org_gen_ix'),
            models.Index(fields=['organization', 'memo_type'], name='review_memo_org_type_ix'),
        ]

    def __str__(self):
        return self.title


class ComplianceChecklist(models.Model):
    class RegulationType(models.TextChoices):
        GDPR = 'GDPR', 'GDPR'
        HIPAA = 'HIPAA', 'HIPAA'
        SOX = 'SOX', 'Sarbanes-Oxley'
        PCI = 'PCI', 'PCI DSS'
        OTHER = 'OTHER', 'Other'

    title = models.CharField(max_length=200)
    description = models.TextField()
    regulation_type = models.CharField(max_length=20, choices=RegulationType.choices)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ChecklistItem(models.Model):
    checklist = models.ForeignKey(ComplianceChecklist, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=200, default='Untitled Item')
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class WorkflowTemplate(models.Model):
    class Category(models.TextChoices):
        CONTRACT_REVIEW = 'CONTRACT_REVIEW', 'Contract Review'
        DUE_DILIGENCE = 'DUE_DILIGENCE', 'Due Diligence'
        TRADEMARK = 'TRADEMARK', 'Trademark'
        COMPLIANCE = 'COMPLIANCE', 'Compliance'
        GENERAL = 'GENERAL', 'General'

    name = models.CharField(max_length=200)
    description = models.TextField()
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_templates',
    )
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.GENERAL)
    version = models.PositiveIntegerField(default=1)
    parent_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_versions',
    )
    # Direct type binding for the workflow-first flow (e.g. the DPA Privacy
    # Review Workflow) — lets a template be looked up by contract type
    # exactly, instead of only via the heuristic category matching in
    # contracts/services/workflow_routing.py::suggest_workflow_template_for_contract.
    contract_type = models.ForeignKey(
        'ContractType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_templates',
    )
    # Unpublished (draft) by default — publication is an explicit governed action.
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_workflow_templates',
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_workflow_templates',
    )
    fallback_signer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_template_fallback_signers',
        help_text='Optional governed fallback when a Signature step has no signer configuration. '
                  'When set, new launches may route to this signer instead of being blocked.',
    )

    class Meta:
        ordering = ['name', '-version', '-created_at']

    def __str__(self):
        return self.name


class WorkflowTemplateScenario(models.Model):
    """Named Test-tab scenario payloads for a workflow template lineage."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='workflow_template_scenarios',
    )
    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='test_scenarios',
    )
    name = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'name'],
                name='wf_template_scenario_name_uniq',
            ),
        ]

    def __str__(self):
        return self.name


class WorkflowTemplateStep(models.Model):
    class StepKind(models.TextChoices):
        TASK = 'TASK', 'Task'
        REVIEW = 'REVIEW', 'Review'
        APPROVAL = 'APPROVAL', 'Approval'
        SIGNATURE = 'SIGNATURE', 'Signature'
        AUTOMATION = 'AUTOMATION', 'Automation'
        NOTIFICATION = 'NOTIFICATION', 'Notification'
        CONDITION = 'CONDITION', 'Condition'
        # Legacy aliases retained for migration/read compatibility until remapped.
        AUTOMATIC = 'AUTOMATIC', 'Automatic'
        BRANCH = 'BRANCH', 'Branch'

    template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='steps')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    estimated_duration = models.DurationField(null=True, blank=True)
    step_kind = models.CharField(max_length=20, choices=StepKind.choices, default=StepKind.TASK)
    condition_expression = models.CharField(
        max_length=512,
        blank=True,
        help_text='Compiled condition expression (legacy-compatible). Prefer condition_rules.',
    )
    condition_rules = models.JSONField(null=True, blank=True, default=None)
    assignee_role = models.CharField(max_length=20, choices=UserProfile.Role.choices, blank=True)
    specific_assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_template_step_assignments',
    )
    sla_hours = models.PositiveIntegerField(null=True, blank=True)
    escalation_after_hours = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.template.name} - {self.name}"

    def applies_to_contract(self, contract):
        rules = getattr(self, 'condition_rules', None)
        expression = (self.condition_expression or '').strip()
        if not rules and not expression:
            return True
        try:
            from contracts.services.workflow_execution import evaluate_step_condition
            return evaluate_step_condition(contract, self)
        except Exception:
            return False

    def resolve_assignee(self, contract=None):
        if self.specific_assignee_id:
            return self.specific_assignee
        role = (self.assignee_role or '').strip()
        organization = getattr(contract, 'organization', None)
        if not role or organization is None:
            return None
        membership_qs = OrganizationMembership.objects.filter(
            organization=organization,
            is_active=True,
        ).select_related('user').prefetch_related('user__profile')
        for membership in membership_qs:
            profile_role = getattr(getattr(membership.user, 'profile', None), 'role', None)
            if profile_role == role:
                return membership.user
        return None


class Workflow(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='workflows')
    template = models.ForeignKey(WorkflowTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class WorkflowStep(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        SKIPPED = 'SKIPPED', 'Skipped'
        ESCALATED = 'ESCALATED', 'Escalated'

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='steps')
    template_step = models.ForeignKey(
        WorkflowTemplateStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_steps',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.workflow.title} - {self.name}"

    def can_transition_to(self, new_status):
        if not new_status:
            return False
        if new_status == self.status:
            return True
        allowed_transitions = {
            self.Status.PENDING: {self.Status.IN_PROGRESS, self.Status.COMPLETED, self.Status.SKIPPED, self.Status.ESCALATED},
            self.Status.IN_PROGRESS: {self.Status.COMPLETED, self.Status.SKIPPED, self.Status.ESCALATED},
            self.Status.ESCALATED: {self.Status.IN_PROGRESS, self.Status.COMPLETED, self.Status.SKIPPED},
            self.Status.COMPLETED: set(),
            self.Status.SKIPPED: set(),
        }
        return new_status in allowed_transitions.get(self.status, set())

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.status in {self.Status.PENDING, self.Status.IN_PROGRESS}
            and self.due_date < timezone.now()
        )


# ── Workflow-first CLM model ────────────────────────────────────────────
# "New Contract" is moving from a plain form to starting a governed
# workflow instance for the selected contract type. `Workflow`/`WorkflowStep`
# above already play the role of "workflow instance"/"workflow stage" — the
# models below are the genuinely new pieces this needs: a real ContractType
# lookup, data-driven field definitions/values (so a workflow's intake
# fields are configuration, not hardcoded ModelForm fields), a persisted
# draft document, a lightweight approval-route definition, and rule-based
# (not AI) risk signals detected while drafting.

class ContractType(models.Model):
    """Governed Contract Type catalogue (CANONICAL_DOMAIN_MODEL §2.6).

    ``code`` is the stable identifier shared with integrations and the
    transitional ``Contract.contract_type`` denormalized field. Workflow
    templates bind to catalogue rows via ``WorkflowTemplate.contract_type``.
    """
    code = models.CharField(max_length=20, unique=True, help_text='Stable type code, e.g. DPA')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FieldDefinition(models.Model):
    """A configurable intake field on a WorkflowTemplate — required fields
    and "smart questions" as data, not hardcoded form fields."""
    class Section(models.TextChoices):
        BASIC_DETAILS = 'BASIC_DETAILS', 'Basic details'
        NDA_TERMS = 'NDA_TERMS', 'NDA terms'
        COMMERCIAL_TERMS = 'COMMERCIAL_TERMS', 'Commercial terms'
        SERVICES_SCOPE = 'SERVICES_SCOPE', 'Services & scope'
        PRIVACY_DETAILS = 'PRIVACY_DETAILS', 'Privacy details'
        LEGAL_POSITION = 'LEGAL_POSITION', 'Legal position'
        PRIVACY_QUESTIONS = 'PRIVACY_QUESTIONS', 'Smart privacy questions'
        SMART_QUESTIONS = 'SMART_QUESTIONS', 'AI smart questions'

    class FieldType(models.TextChoices):
        TEXT = 'TEXT', 'Text'
        TEXTAREA = 'TEXTAREA', 'Textarea'
        DATE = 'DATE', 'Date'
        NUMBER = 'NUMBER', 'Number'
        BOOLEAN = 'BOOLEAN', 'Yes/No'
        SELECT = 'SELECT', 'Select'

    workflow_template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='field_definitions')
    key = models.SlugField(max_length=60, help_text='Merge-field token name, e.g. dpo_contact')
    label = models.CharField(max_length=200)
    help_text = models.CharField(max_length=300, blank=True)
    section = models.CharField(max_length=20, choices=Section.choices, default=Section.BASIC_DETAILS)
    field_type = models.CharField(max_length=10, choices=FieldType.choices, default=FieldType.TEXT)
    options = models.JSONField(default=list, blank=True, help_text='Choices for SELECT fields')
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    maps_to_contract_field = models.CharField(
        max_length=40, blank=True,
        help_text='If set, this value is also written onto Contract.<field> on submit (e.g. counterparty, start_date).',
    )

    class Meta:
        ordering = ['section', 'order']
        constraints = [models.UniqueConstraint(fields=['workflow_template', 'key'], name='fielddef_template_key_uniq')]

    def __str__(self):
        return f'{self.workflow_template.name} · {self.label}'


class FieldValue(models.Model):
    """A submitted answer for one FieldDefinition on one Workflow instance."""
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='field_values')
    field_definition = models.ForeignKey(FieldDefinition, on_delete=models.CASCADE, related_name='values')
    value = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workflow', 'field_definition'], name='fieldvalue_workflow_field_uniq')]

    def __str__(self):
        return f'{self.workflow.title} · {self.field_definition.key}'


class DraftDocument(models.Model):
    """The live/versioned draft document tied to a Workflow instance —
    distinct from Contract.content, which stays the saved/final text."""
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='draft_documents')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='draft_documents')
    content = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f'{self.workflow.title} draft v{self.version}'


class ApprovalRoute(models.Model):
    """A persisted, ordered approval-step definition per WorkflowTemplate —
    formalizes what draft_cockpit.get_approval_route_preview() otherwise
    fabricates ad hoc for the generic (non-workflow) create page. Not built
    on ApprovalRule/ApprovalRequest, which model conditional rule-matching
    and real tracked per-contract approvals — a heavier concern than a
    template-level approval-chain definition."""
    workflow_template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='approval_routes')
    name = models.CharField(max_length=100, help_text='e.g. Contract Owner, Legal, DPO, Finance')
    order = models.PositiveIntegerField(default=0)
    role_label = models.CharField(max_length=100, blank=True, help_text='Plain-language role description shown in the UI')
    is_conditional = models.BooleanField(default=False)
    condition_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['workflow_template', 'order']

    def __str__(self):
        return f'{self.workflow_template.name} · {self.name}'


class RiskSignal(models.Model):
    """A rule-based (not AI) risk signal detected while drafting a Workflow
    instance — deliberately lighter than DPARiskItem, which is built for
    the separate, deep DPAReviewPack analysis flow."""
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='risk_signals')
    code = models.CharField(max_length=60, help_text='Stable rule identifier, e.g. cross_border_no_mechanism')
    description = models.CharField(max_length=300)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    detected_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-severity', 'detected_at']

    def __str__(self):
        return f'{self.workflow.title} · {self.code}'


class DueDiligenceProcess(models.Model):
    class ProcessStatus(models.TextChoices):
        INTAKE = 'INTAKE', 'Intake'
        ASSESSMENT = 'ASSESSMENT', 'Beoordeling'
        MATCHING = 'MATCHING', 'Matching'
        DECISION = 'DECISION', 'Matchbesluit'
        COMPLETED = 'COMPLETED', 'Afgerond'
        ON_HOLD = 'ON_HOLD', 'In wacht'

    class TransactionType(models.TextChoices):
        MERGER = 'MERGER', 'Merger'
        ACQUISITION = 'ACQUISITION', 'Acquisition'
        JOINT_VENTURE = 'JOINT_VENTURE', 'Joint Venture'
        ASSET_PURCHASE = 'ASSET_PURCHASE', 'Asset Purchase'

    class AgeCategory(models.TextChoices):
        AGE_0_4 = '0_4', '0–4'
        AGE_4_12 = '4_12', '4–12'
        AGE_12_18 = '12_18', '12–18'
        AGE_18_PLUS = '18_PLUS', '18+'

    class Complexity(models.TextChoices):
        SIMPLE = 'SIMPLE', 'Enkelvoudig'
        MULTIPLE = 'MULTIPLE', 'Meervoudig'
        SEVERE = 'SEVERE', 'Zwaar'

    class FamilySituation(models.TextChoices):
        HOME_DWELLING = 'HOME_DWELLING', 'Thuiswonend'
        DIVORCED_PARENTS = 'DIVORCED_PARENTS', 'Gescheiden ouders'
        FOSTER_CARE = 'FOSTER_CARE', 'Pleegzorg'
        INSTITUTION = 'INSTITUTION', 'Instelling'
        OTHER = 'OTHER', 'Anders'

    class Urgency(models.TextChoices):
        LOW = 'LOW', 'Laag'
        MEDIUM = 'MEDIUM', 'Middel'
        HIGH = 'HIGH', 'Hoog'
        CRISIS = 'CRISIS', 'Crisis'

    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, null=True, blank=True,
        related_name='due_diligence_processes',
    )
    title = models.CharField(max_length=200)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    assessment_summary = models.TextField(blank=True, verbose_name='Intake samenvatting', help_text='Hulpvraag samenvatting, urgentie, aandachtspunten')
    client_age_category = models.CharField(max_length=10, choices=AgeCategory.choices, null=True, blank=True, verbose_name='Leeftijdscategorie cliënt')
    complexity = models.CharField(max_length=20, choices=Complexity.choices, default=Complexity.SIMPLE, verbose_name='Complexiteit')
    family_situation = models.CharField(max_length=20, choices=FamilySituation.choices, null=True, blank=True, verbose_name='Gezinssituatie')
    has_other_support = models.BooleanField(default=False, verbose_name='Betrokken hulp (ja/nee)')
    other_support_description = models.TextField(blank=True, verbose_name='Beschrijving betrokken hulp')
    preferred_care_form = models.CharField(max_length=20, choices=[
        ('OUTPATIENT', 'Ambulant'),
        ('DAY_TREATMENT', 'Dagbehandeling'),
        ('RESIDENTIAL', 'Residentieel'),
        ('CRISIS', 'Crisisopvang'),
    ], default='OUTPATIENT', verbose_name='Gewenste zorgvorm')
    school_work_status = models.CharField(max_length=200, blank=True, verbose_name='School- / werkstatus')
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.MEDIUM, verbose_name='Urgentie')
    target_company = models.CharField(max_length=200, blank=True)
    deal_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=ProcessStatus.choices, default=ProcessStatus.INTAKE)
    lead_attorney = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dd_processes', verbose_name='Casusregisseur')
    start_date = models.DateField(verbose_name='Intakedatum')
    target_completion_date = models.DateField()
    description = models.TextField(blank=True, verbose_name='Aanvullende opmerkingen')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} - {self.target_company}'


class DueDiligenceTask(models.Model):
    class TaskStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        BLOCKED = 'BLOCKED', 'Blocked'

    class TaskCategory(models.TextChoices):
        LEGAL = 'LEGAL', 'Legal'
        FINANCIAL = 'FINANCIAL', 'Financial'
        OPERATIONAL = 'OPERATIONAL', 'Operational'
        TECHNICAL = 'TECHNICAL', 'Technical'
        REGULATORY = 'REGULATORY', 'Regulatory'
        COMMERCIAL = 'COMMERCIAL', 'Commercial'

    process = models.ForeignKey(DueDiligenceProcess, on_delete=models.CASCADE, related_name='dd_tasks')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=TaskCategory.choices)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    due_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'due_date']

    def __str__(self):
        return f'{self.process.title} - {self.title}'


class DueDiligenceRisk(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'

    class RiskCategory(models.TextChoices):
        LEGAL = 'LEGAL', 'Legal & Regulatory'
        FINANCIAL = 'FINANCIAL', 'Financial'
        OPERATIONAL = 'OPERATIONAL', 'Operational'
        REPUTATIONAL = 'REPUTATIONAL', 'Reputational'
        STRATEGIC = 'STRATEGIC', 'Strategic'

    process = models.ForeignKey(DueDiligenceProcess, on_delete=models.CASCADE, related_name='dd_risks')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=RiskCategory.choices)
    description = models.TextField()
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    likelihood = models.CharField(max_length=10, choices=RiskLevel.choices)
    impact = models.CharField(max_length=10, choices=RiskLevel.choices)
    mitigation_strategy = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    identified_date = models.DateField(auto_now_add=True)
    target_resolution_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.process.title} - {self.title} ({self.risk_level})'


class Budget(models.Model):
    class Quarter(models.TextChoices):
        Q1 = 'Q1', 'Q1'
        Q2 = 'Q2', 'Q2'
        Q3 = 'Q3', 'Q3'
        Q4 = 'Q4', 'Q4'

    class CareType(models.TextChoices):
        OUTPATIENT = 'OUTPATIENT', 'Ambulant'
        DAY_TREATMENT = 'DAY_TREATMENT', 'Dagbehandeling'
        RESIDENTIAL = 'RESIDENTIAL', 'Residentieel'
        CRISIS = 'CRISIS', 'Crisisopvang'

    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, null=True, blank=True,
        related_name='budgets',
    )
    year = models.PositiveIntegerField()
    quarter = models.CharField(max_length=2, choices=Quarter.choices)
    department = models.CharField(max_length=100)
    care_type = models.CharField(max_length=20, choices=CareType.choices, default=CareType.OUTPATIENT, verbose_name='Zorgtype')
    scope_type = models.CharField(max_length=20, choices=[('GEMEENTE', 'Gemeente'), ('REGIO', 'Regio')], default='GEMEENTE', verbose_name='Gemeente / regio type')
    scope_name = models.CharField(max_length=150, blank=True, default='', verbose_name='Gemeente / regio')
    target_group = models.CharField(max_length=150, blank=True, default='', verbose_name='Doelgroep')
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['organization', 'year', 'quarter', 'department']

    def __str__(self):
        return f'{self.department} - {self.year} {self.quarter}'

    @property
    def spent_amount(self):
        return self.expenses.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    @property
    def is_over_budget(self):
        return self.spent_amount > self.allocated_amount


class BudgetExpense(models.Model):
    class Category(models.TextChoices):
        LEGAL_FEES = 'LEGAL_FEES', 'Legal Fees'
        CONSULTING = 'CONSULTING', 'Consulting'
        SOFTWARE = 'SOFTWARE', 'Software'
        TRAVEL = 'TRAVEL', 'Travel'
        OFFICE = 'OFFICE', 'Office Supplies'
        OTHER = 'OTHER', 'Other'

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    category = models.CharField(max_length=20, choices=Category.choices)
    date = models.DateField()
    receipt_url = models.URLField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.budget} - {self.description} (${self.amount})'


class NegotiationThread(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='negotiation_threads')
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.contract.title} - {self.title}"


class CounterpartyCollaborationParticipant(models.Model):
    """A revocable, contract-scoped participant in the external workspace.

    This is intentionally not an OrganizationMembership. A counterparty never
    becomes a member of the customer workspace and cannot reach its internal
    records, search, or navigation.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        REVOKED = 'REVOKED', 'Revoked'
        EXPIRED = 'EXPIRED', 'Expired'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='counterparty_collaboration_participants'
    )
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='counterparty_collaboration_participants'
    )
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    can_view_documents = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=True)
    can_upload_revisions = models.BooleanField(default=False)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='sent_counterparty_collaboration_invites')
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract', 'status'], name='ccp_contract_status_ix'),
            models.Index(fields=['organization', 'email'], name='ccp_org_email_ix'),
        ]

    def __str__(self):
        return f'{self.email} · {self.contract.title}'

    @property
    def is_accessible(self):
        return (
            self.status in (self.Status.PENDING, self.Status.ACTIVE)
            and (self.expires_at is None or self.expires_at > timezone.now())
            and self.organization.is_active
        )


class CounterpartyCollaborationItem(models.Model):
    """A shared comment, revision hand-off, or task within one contract."""

    class Kind(models.TextChoices):
        COMMENT = 'COMMENT', 'Comment'
        REVISION = 'REVISION', 'Revision'
        TASK = 'TASK', 'Task'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        COMPLETED = 'COMPLETED', 'Completed'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='counterparty_collaboration_items'
    )
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='counterparty_collaboration_items'
    )
    participant = models.ForeignKey(
        CounterpartyCollaborationParticipant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items'
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='counterparty_collaboration_items')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='counterparty_collaboration_items')
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.COMMENT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='completed_counterparty_collaboration_items')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['contract', 'status', '-created_at'], name='cci_contract_status_ix')]

    def __str__(self):
        return self.title or f'{self.get_kind_display()} for {self.contract.title}'


class Counterparty(models.Model):
    class EntityType(models.TextChoices):
        CORPORATION = 'CORPORATION', 'Corporation'
        LLC = 'LLC', 'LLC'
        PARTNERSHIP = 'PARTNERSHIP', 'Partnership'
        INDIVIDUAL = 'INDIVIDUAL', 'Individual'
        GOVERNMENT = 'GOVERNMENT', 'Government'
        NON_PROFIT = 'NON_PROFIT', 'Non-Profit'
        OTHER = 'OTHER', 'Other'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='counterparties')
    name = models.CharField(max_length=300)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices, default=EntityType.CORPORATION)
    jurisdiction = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Counterparties'

    def __str__(self):
        return self.name


class ClauseCategory(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='clause_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Clause categories'
        ordering = ['order', 'name']
        unique_together = [('organization', 'name')]

    def __str__(self):
        return self.name


class ClauseTemplate(models.Model):
    class JurisdictionScope(models.TextChoices):
        EU = 'EU', 'European Union'
        US = 'US', 'United States'
        UK = 'UK', 'United Kingdom'
        GLOBAL = 'GLOBAL', 'Global/Universal'
        CUSTOM = 'CUSTOM', 'Custom'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='clause_templates')
    title = models.CharField(max_length=200)
    category = models.ForeignKey(ClauseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='clauses')
    content = models.TextField(help_text='Standard clause text')
    fallback_content = models.TextField(blank=True, help_text='Fallback/negotiation position')
    jurisdiction_scope = models.CharField(max_length=10, choices=JurisdictionScope.choices, default=JurisdictionScope.GLOBAL)
    is_mandatory = models.BooleanField(default=False, help_text='Required in all contracts of this type')
    applicable_contract_types = models.CharField(max_length=200, blank=True, help_text='Comma-separated contract types')
    version = models.PositiveIntegerField(default=1)
    parent_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_versions',
    )
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_clauses')
    approved_at = models.DateTimeField(null=True, blank=True)
    playbook_notes = models.TextField(blank=True, help_text='Negotiation playbook guidance')
    tags = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} (v{self.version})'


class ClausePlaybook(models.Model):
    class JurisdictionScope(models.TextChoices):
        EU = 'EU', 'European Union'
        US = 'US', 'United States'
        UK = 'UK', 'United Kingdom'
        GLOBAL = 'GLOBAL', 'Global/Universal'
        CUSTOM = 'CUSTOM', 'Custom'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='clause_playbooks')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    fallback_position = models.TextField(blank=True)
    jurisdiction_scope = models.CharField(max_length=10, choices=JurisdictionScope.choices, default=JurisdictionScope.GLOBAL)
    risk_level = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_clause_playbooks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ClauseVariant(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='clause_variants')
    template = models.ForeignKey(ClauseTemplate, on_delete=models.CASCADE, related_name='variants')
    playbook = models.ForeignKey(ClausePlaybook, on_delete=models.SET_NULL, null=True, blank=True, related_name='variants')
    jurisdiction_scope = models.CharField(max_length=10, choices=ClauseTemplate.JurisdictionScope.choices, default=ClauseTemplate.JurisdictionScope.GLOBAL)
    contract_type = models.CharField(max_length=50, blank=True)
    risk_level = models.CharField(max_length=20, blank=True)
    fallback_content = models.TextField(blank=True)
    playbook_notes = models.TextField(blank=True)
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', '-created_at']

    def __str__(self):
        return f'{self.template.title} variant {self.priority}'


class EthicalWall(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='ethical_walls')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='ethical_walls')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='ethical_walls')
    restricted_users = models.ManyToManyField(User, related_name='ethical_wall_restrictions', blank=True)
    is_active = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_walls')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class SignatureRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        VIEWED = 'VIEWED', 'Viewed'
        SIGNED = 'SIGNED', 'Signed'
        DECLINED = 'DECLINED', 'Declined'
        EXPIRED = 'EXPIRED', 'Expired'
        CANCELLED = 'CANCELLED', 'Cancelled'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='signature_requests')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='signature_requests')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='signature_requests')
    document_version = models.ForeignKey(
        'DocumentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signature_requests',
        help_text='Exact immutable Document Version bound when the packet was created.',
    )
    signer_name = models.CharField(max_length=200)
    signer_email = models.EmailField()
    signer_role = models.CharField(max_length=100, blank=True, help_text='e.g. CEO, Legal Counsel')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    external_id = models.CharField(max_length=200, blank=True, help_text='External provider reference ID')
    esign_provider = models.CharField(max_length=40, blank=True, help_text='Outbound e-sign provider that dispatched this request')
    signing_url = models.CharField(max_length=500, blank=True, help_text='Provider signing URL returned when the request was sent')
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    execution_certificate_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.contract.title} - {self.signer_name} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if self.document_id and not self.document_version_id:
            from contracts.services.document_version_service import bind_signature_document_version

            bind_signature_document_version(self)
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status):
        if not new_status:
            return False
        if new_status == self.status:
            return True
        allowed_transitions = {
            self.Status.PENDING: {self.Status.SENT, self.Status.CANCELLED},
            self.Status.SENT: {
                self.Status.VIEWED,
                self.Status.SIGNED,
                self.Status.DECLINED,
                self.Status.EXPIRED,
                self.Status.CANCELLED,
            },
            self.Status.VIEWED: {
                self.Status.SIGNED,
                self.Status.DECLINED,
                self.Status.EXPIRED,
                self.Status.CANCELLED,
            },
            self.Status.SIGNED: set(),
            self.Status.DECLINED: set(),
            self.Status.EXPIRED: set(),
            self.Status.CANCELLED: set(),
        }
        return new_status in allowed_transitions.get(self.status, set())

    def can_actor_transition(self, actor, new_status):
        if actor is None or not getattr(actor, 'is_authenticated', False):
            return False
        if self.created_by_id and self.created_by_id == actor.id:
            return True
        if self.organization_id:
            from .permissions import can_manage_organization
            if can_manage_organization(actor, self.organization):
                return True
        signer_actions = {self.Status.VIEWED, self.Status.SIGNED, self.Status.DECLINED}
        signer_email = (self.signer_email or '').strip().lower()
        actor_email = (actor.email or '').strip().lower()
        if new_status in signer_actions and signer_email and actor_email:
            if not self.is_routing_ready():
                return False
            return signer_email == actor_email
        return False

    def routing_blockers(self):
        if not self.order:
            return []
        terminal_statuses = {
            self.Status.SIGNED,
            self.Status.DECLINED,
            self.Status.EXPIRED,
            self.Status.CANCELLED,
        }
        return list(
            SignatureRequest.objects.select_related('contract')
            .filter(
                contract_id=self.contract_id,
                order__lt=self.order,
            )
            .exclude(status__in=terminal_statuses)
            .order_by('order', 'created_at')
        )

    def is_routing_ready(self):
        return not self.routing_blockers()

    def available_transitions_for_actor(self, actor):
        if not self.is_routing_ready():
            signer_email = (getattr(actor, 'email', '') or '').strip().lower()
            if signer_email and signer_email == (self.signer_email or '').strip().lower():
                return []
        ordered_statuses = [
            self.Status.SENT,
            self.Status.VIEWED,
            self.Status.SIGNED,
            self.Status.DECLINED,
            self.Status.EXPIRED,
            self.Status.CANCELLED,
        ]
        labels = dict(self.Status.choices)
        return [
            {
                'value': status,
                'label': labels.get(status, status.title()),
            }
            for status in ordered_statuses
            if self.can_transition_to(status) and self.can_actor_transition(actor, status)
        ]

    def is_follow_up_due(self, threshold_days: int = 7) -> bool:
        if self.status not in {self.Status.PENDING, self.Status.SENT, self.Status.VIEWED}:
            return False
        if not self.sent_at:
            return self.status in {self.Status.SENT, self.Status.VIEWED}
        return self.sent_at <= timezone.now() - timedelta(days=threshold_days)


class DataInventoryRecord(models.Model):
    class LawfulBasis(models.TextChoices):
        CONSENT = 'CONSENT', 'Consent'
        CONTRACT = 'CONTRACT', 'Contractual Necessity'
        LEGAL_OBLIGATION = 'LEGAL_OBLIGATION', 'Legal Obligation'
        VITAL_INTEREST = 'VITAL_INTEREST', 'Vital Interest'
        PUBLIC_INTEREST = 'PUBLIC_INTEREST', 'Public Interest'
        LEGITIMATE_INTEREST = 'LEGITIMATE_INTEREST', 'Legitimate Interest'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='data_inventory_records')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    data_categories = models.TextField(help_text='Categories of personal data processed')
    data_subjects = models.TextField(help_text='Categories of data subjects')
    purpose = models.TextField(help_text='Purpose of processing')
    lawful_basis = models.CharField(max_length=25, choices=LawfulBasis.choices)
    retention_period = models.CharField(max_length=200, help_text='e.g. 7 years, until consent withdrawn')
    recipients = models.TextField(blank=True, help_text='Categories of recipients')
    third_country_transfers = models.BooleanField(default=False)
    transfer_safeguards = models.TextField(blank=True, help_text='SCC, DPF, adequacy decision, etc.')
    technical_measures = models.TextField(blank=True, help_text='Encryption, pseudonymization, etc.')
    organizational_measures = models.TextField(blank=True, help_text='Access controls, training, etc.')
    dpia_required = models.BooleanField(default=False, help_text='Data Protection Impact Assessment required')
    dpia_completed = models.BooleanField(default=False)
    controller = models.CharField(max_length=200, blank=True)
    processor = models.CharField(max_length=200, blank=True)
    dpo_contact = models.CharField(max_length=200, blank=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='data_inventory')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class DSARRequest(models.Model):
    class RequestType(models.TextChoices):
        ACCESS = 'ACCESS', 'Right of Access'
        RECTIFICATION = 'RECTIFICATION', 'Right to Rectification'
        ERASURE = 'ERASURE', 'Right to Erasure'
        RESTRICT = 'RESTRICT', 'Right to Restrict Processing'
        PORTABILITY = 'PORTABILITY', 'Right to Data Portability'
        OBJECTION = 'OBJECTION', 'Right to Object'

    class Status(models.TextChoices):
        RECEIVED = 'RECEIVED', 'Received'
        VERIFIED = 'VERIFIED', 'Identity Verified'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        DENIED = 'DENIED', 'Denied'
        EXTENDED = 'EXTENDED', 'Extended'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='dsar_requests')
    reference_number = models.CharField(max_length=50, unique=True)
    request_type = models.CharField(max_length=15, choices=RequestType.choices)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.RECEIVED)
    requester_name = models.CharField(max_length=200)
    requester_email = models.EmailField()
    requester_id_verified = models.BooleanField(default=False)
    description = models.TextField()
    response = models.TextField(blank=True)
    denial_reason = models.TextField(blank=True)
    received_date = models.DateField()
    due_date = models.DateField(help_text='Must respond within 30 days (GDPR)')
    completed_date = models.DateField(null=True, blank=True)
    extended = models.BooleanField(default=False, help_text='Extension requested (up to 60 additional days)')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='dsar_requests')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_dsars')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'DSAR Request'

    def __str__(self):
        return f'{self.reference_number} - {self.get_request_type_display()}'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            last = DSARRequest.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.reference_number = f'DSAR-{next_num:05d}'
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.status not in ['COMPLETED', 'DENIED'] and self.due_date:
            return date.today() > self.due_date
        return False


class Subprocessor(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='subprocessors')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    service_type = models.CharField(max_length=200, help_text='e.g. Cloud hosting, Payment processing')
    country = models.CharField(max_length=100)
    is_eu_based = models.BooleanField(default=False)
    dpa_in_place = models.BooleanField(default=False)
    scc_in_place = models.BooleanField(default=False)
    dpf_certified = models.BooleanField(default=False, help_text='Data Privacy Framework certified')
    data_categories = models.TextField(blank=True, help_text='Types of data shared')
    contact_email = models.EmailField(blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    last_audit_date = models.DateField(null=True, blank=True)
    risk_level = models.CharField(max_length=10, choices=[
        ('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'),
    ], default='LOW')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.country})'


class TransferRecord(models.Model):
    class TransferMechanism(models.TextChoices):
        ADEQUACY = 'ADEQUACY', 'Adequacy Decision'
        SCC = 'SCC', 'Standard Contractual Clauses'
        BCR = 'BCR', 'Binding Corporate Rules'
        DPF = 'DPF', 'Data Privacy Framework'
        CONSENT = 'CONSENT', 'Explicit Consent'
        DEROGATION = 'DEROGATION', 'Derogation'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='transfer_records')
    title = models.CharField(max_length=200)
    source_country = models.CharField(max_length=100)
    destination_country = models.CharField(max_length=100)
    transfer_mechanism = models.CharField(max_length=15, choices=TransferMechanism.choices)
    data_categories = models.TextField(help_text='Types of data transferred')
    subprocessor = models.ForeignKey(Subprocessor, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='data_transfers')
    tia_completed = models.BooleanField(default=False, help_text='Transfer Impact Assessment completed')
    supplementary_measures = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} ({self.source_country} → {self.destination_country})'


class RetentionPolicy(models.Model):
    class Category(models.TextChoices):
        CONTRACTS = 'CONTRACTS', 'Contracts'
        CLIENT_DATA = 'CLIENT_DATA', 'Client Data'
        EMPLOYEE_DATA = 'EMPLOYEE_DATA', 'Employee Data'
        FINANCIAL = 'FINANCIAL', 'Financial Records'
        CORRESPONDENCE = 'CORRESPONDENCE', 'Correspondence'
        LITIGATION = 'LITIGATION', 'Litigation Files'
        COMPLIANCE = 'COMPLIANCE', 'Compliance Records'
        OTHER = 'OTHER', 'Other'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='retention_policies')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)
    retention_period_days = models.PositiveIntegerField(help_text='Retention period in days')
    legal_basis = models.TextField(blank=True, help_text='Legal requirement for retention')
    deletion_method = models.CharField(max_length=200, blank=True, help_text='How data is destroyed')
    auto_delete = models.BooleanField(default=False)
    review_frequency_days = models.PositiveIntegerField(default=365)
    last_reviewed = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Retention policies'

    def __str__(self):
        return f'{self.title} ({self.retention_period_days} days)'


class LegalHold(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        RELEASED = 'RELEASED', 'Released'
        EXPIRED = 'EXPIRED', 'Expired'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='legal_holds')
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True, related_name='legal_holds')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='legal_holds')
    custodians = models.ManyToManyField(User, related_name='legal_hold_custodians', blank=True)
    hold_start_date = models.DateField()
    hold_end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    scope = models.TextField(blank=True, help_text='Documents, emails, data types in scope')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_holds')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class DPAReviewPack(models.Model):
    """First-class review record for a Data Processing Agreement.

    Deliberately denormalized (one model, many boolean/text fields grouped
    by review section) rather than split across a dozen tables — every
    field maps to one literal item on the DPA review checklist, so the
    detail page can render the whole checklist from one row without a web
    of joins. Findings on this record can come from the heuristic scanner
    (services.dpa_review.run_dpa_analysis, marked as suggestions) or from a
    human reviewer editing the record directly — either way, approval_status
    only ever moves via an explicit human action (see DPAReviewPackApproveView),
    never automatically.
    """

    class RoleQualification(models.TextChoices):
        CONTROLLER_PROCESSOR = 'CONTROLLER_PROCESSOR', 'Client Controller / Processor'
        JOINT_CONTROLLER = 'JOINT_CONTROLLER', 'Joint-Controller Risk'
        INDEPENDENT_CONTROLLER = 'INDEPENDENT_CONTROLLER', 'Independent-Controller Risk'
        AMBIGUOUS = 'AMBIGUOUS', 'Ambiguous / Undetermined'

    class ApprovalStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        ESCALATED = 'ESCALATED', 'Escalated'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='dpa_review_packs')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='dpa_review_packs')
    counterparty = models.ForeignKey(Counterparty, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_review_packs')
    matter = models.ForeignKey(Matter, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_review_packs')
    # The MSA/SOW (or any other contract in the same engagement) this DPA is
    # reviewed against for cross-document conflicts (services.dpa_conflict).
    # There is no "ContractPack" grouping model in this codebase — linking
    # directly to the related Contract rows is the real equivalent.
    related_contracts = models.ManyToManyField(Contract, blank=True, related_name='dpa_review_packs_as_related')
    documents = models.ManyToManyField(Document, blank=True, related_name='dpa_review_packs')
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_dpa_review_packs',
    )

    # 1. Role qualification
    role_qualification = models.CharField(max_length=25, choices=RoleQualification.choices, default=RoleQualification.AMBIGUOUS)
    role_qualification_notes = models.TextField(blank=True)
    subprocessors_involved = models.BooleanField(default=False)

    # 2. Processing description
    data_subject_categories = models.TextField(blank=True, help_text='Categories of data subjects (e.g. employees, contractors)')
    personal_data_categories = models.TextField(blank=True)
    special_category_data = models.TextField(blank=True)
    processing_purposes = models.TextField(blank=True)
    processing_duration = models.CharField(max_length=200, blank=True)
    retention_obligations = models.TextField(blank=True)
    systems_tools_vendors = models.TextField(blank=True)

    # 3. Payroll-specific data categories (Payrollminds-driven checklist)
    has_employee_identity_data = models.BooleanField(default=False)
    has_salary_wage_data = models.BooleanField(default=False)
    has_tax_data = models.BooleanField(default=False)
    has_social_security_data = models.BooleanField(default=False)
    has_bank_account_data = models.BooleanField(default=False)
    has_pension_benefits_data = models.BooleanField(default=False)
    has_absence_leave_data = models.BooleanField(default=False)
    has_employment_contract_data = models.BooleanField(default=False)
    has_national_identifiers = models.BooleanField(default=False)
    has_payroll_corrections = models.BooleanField(default=False)
    has_payslip_data = models.BooleanField(default=False)
    has_cross_border_payroll_data = models.BooleanField(default=False)

    # 4. Subprocessor / vendor review — cross-referenced against the
    # existing Subprocessor model rather than duplicating vendor data.
    subprocessors = models.ManyToManyField(Subprocessor, blank=True, related_name='dpa_review_packs')
    subprocessor_prior_approval_required = models.BooleanField(default=False)
    subprocessor_general_authorization_allowed = models.BooleanField(default=False)
    subprocessor_notification_period_days = models.PositiveIntegerField(null=True, blank=True)
    subprocessor_model_conflict_notes = models.TextField(blank=True)

    # 5. International transfer review — cross-referenced against the
    # existing TransferRecord model.
    transfer_records = models.ManyToManyField(TransferRecord, blank=True, related_name='dpa_review_packs')
    transfers_outside_eea = models.BooleanField(default=False)
    transfer_mechanism_present = models.BooleanField(default=False)
    transfer_escalation_required = models.BooleanField(default=False)
    transfer_notes = models.TextField(blank=True)

    # 6. Security measures review
    security_encryption = models.BooleanField(default=False)
    security_access_control = models.BooleanField(default=False)
    security_mfa = models.BooleanField(default=False)
    security_logging = models.BooleanField(default=False)
    security_backup = models.BooleanField(default=False)
    security_incident_response = models.BooleanField(default=False)
    security_data_segregation = models.BooleanField(default=False)
    security_measures_specific = models.BooleanField(default=False, help_text='False = measures described in vague/generic terms')
    security_notes = models.TextField(blank=True)

    # 7. Breach notification review
    breach_notification_deadline_hours = models.PositiveIntegerField(null=True, blank=True)
    breach_notification_realistic = models.BooleanField(default=True)
    breach_notification_conflicts_msa = models.BooleanField(default=False)
    breach_notification_notes = models.TextField(blank=True)

    # 8. Data subject request assistance
    dsar_assistance_required = models.BooleanField(default=False)
    dsar_assistance_deadline_days = models.PositiveIntegerField(null=True, blank=True)
    dsar_assistance_chargeable = models.BooleanField(default=False)
    dsar_business_confirmation_needed = models.BooleanField(default=False)

    # 9. Audit rights
    audit_rights_onsite_allowed = models.BooleanField(default=False)
    audit_rights_frequency_limited = models.BooleanField(default=False)
    audit_third_party_reports_accepted = models.BooleanField(default=False)
    audit_costs_addressed = models.BooleanField(default=False)
    audit_conflicts_msa = models.BooleanField(default=False)
    audit_notes = models.TextField(blank=True)

    # 10. Deletion and return
    deletion_return_deadline_days = models.PositiveIntegerField(null=True, blank=True)
    deletion_legal_retention_conflict = models.BooleanField(default=False)
    deletion_backup_addressed = models.BooleanField(default=False)
    deletion_certification_required = models.BooleanField(default=False)
    deletion_notes = models.TextField(blank=True)

    # 11. Liability conflict detection (DPA vs MSA/SOW)
    liability_uncapped = models.BooleanField(default=False)
    liability_overrides_msa_cap = models.BooleanField(default=False)
    liability_separate_indemnities = models.BooleanField(default=False)
    liability_conflicts_standard_position = models.BooleanField(default=False)
    liability_notes = models.TextField(blank=True)

    # 13. Output / review memo
    review_memo = models.TextField(blank=True)
    review_memo_generated_at = models.DateTimeField(null=True, blank=True)
    last_analyzed_at = models.DateTimeField(null=True, blank=True)

    # Human-controlled approval — never set by the analyzer.
    approval_status = models.CharField(max_length=15, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_review_packs_approved')
    approved_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_review_packs_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'DPA Review Pack — {self.contract.title}'


class DPARiskItem(models.Model):
    """One identified risk on a DPA review, owned by whichever function
    (Legal, DPO/Security, Business, Finance, Delivery) needs to act on it.
    `owners` is a comma-separated list of Owner codes rather than a single
    choice — several of the module's own examples (e.g. an unrealistic
    breach notification deadline) are jointly owned by Legal and
    Operations/Business, and a single-owner field can't represent that.
    """

    class Owner(models.TextChoices):
        LEGAL = 'LEGAL', 'Legal'
        HEAD_LEGAL = 'HEAD_LEGAL', 'Head of Legal'
        DPO_SECURITY = 'DPO_SECURITY', 'DPO/Security'
        BUSINESS = 'BUSINESS', 'Business'
        FINANCE = 'FINANCE', 'Finance'
        DELIVERY = 'DELIVERY', 'Delivery'

    class Category(models.TextChoices):
        ROLE_QUALIFICATION = 'ROLE_QUALIFICATION', 'Role Qualification'
        PROCESSING_SCOPE = 'PROCESSING_SCOPE', 'Processing Scope'
        SUBPROCESSOR = 'SUBPROCESSOR', 'Subprocessor / Vendor'
        TRANSFER = 'TRANSFER', 'International Transfer'
        SECURITY = 'SECURITY', 'Security Measures'
        BREACH_NOTIFICATION = 'BREACH_NOTIFICATION', 'Breach Notification'
        DSAR = 'DSAR', 'Data Subject Request Assistance'
        AUDIT = 'AUDIT', 'Audit Rights'
        DELETION = 'DELETION', 'Deletion and Return'
        LIABILITY = 'LIABILITY', 'Liability Conflict'

    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class Confidence(models.TextChoices):
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        NEEDS_HUMAN_CHECK = 'NEEDS_HUMAN_CHECK', 'Needs human check'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        RESOLVED = 'RESOLVED', 'Resolved'
        ACCEPTED_RISK = 'ACCEPTED_RISK', 'Accepted Risk'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'False Positive'
        NEEDS_BUSINESS_INPUT = 'NEEDS_BUSINESS_INPUT', 'Needs Business Input'
        NEEDS_DPO_SECURITY_INPUT = 'NEEDS_DPO_SECURITY_INPUT', 'Needs DPO/Security Input'
        ESCALATED = 'ESCALATED', 'Escalated'

    review_pack = models.ForeignKey(DPAReviewPack, on_delete=models.CASCADE, related_name='risk_items')
    category = models.CharField(max_length=25, choices=Category.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    confidence = models.CharField(max_length=25, choices=Confidence.choices, default=Confidence.MEDIUM)
    owners = models.CharField(max_length=100, help_text='Comma-separated Owner codes, e.g. "LEGAL,DPO_SECURITY"')
    fallback_recommendation = models.TextField(blank=True)
    evidence_text = models.TextField(blank=True, help_text='Verbatim snippet or concise detected excerpt that triggered this finding')
    source_section = models.CharField(max_length=120, blank=True)
    source_field = models.CharField(max_length=120, blank=True)
    detection_rule = models.CharField(max_length=120, blank=True)
    conflict_type = models.CharField(max_length=80, blank=True)
    related_contract_evidence_text = models.TextField(blank=True, help_text='Verbatim snippet or concise detected excerpt from linked MSA/SOW')
    is_cross_document_conflict = models.BooleanField(default=False, help_text='True if this finding compares the DPA against a linked MSA/SOW rather than the DPA alone')
    reviewer_notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    detected_automatically = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-severity', 'category']

    def owner_list(self):
        return [o for o in self.owners.split(',') if o]

    def __str__(self):
        return f'{self.title} ({self.get_severity_display()})'


class DPARiskItemNote(models.Model):
    """Timestamped human reviewer note for one DPA risk item.

    Kept as a child table instead of a mutable TextField so review comments
    preserve actor/time context and can be included in memo export without
    losing history.
    """

    risk_item = models.ForeignKey(DPARiskItem, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_risk_item_notes')
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Note on {self.risk_item_id}'


class DPAApprovalHistoryEntry(models.Model):
    """Structured, DPA-scoped log of every approval_status change — distinct
    from the generic AuditLog (which also records these events for
    org-wide audit purposes). This one exists so the review pack's own
    "Approval History" section can be rendered without filtering the
    generic audit trail by model_name/object_id. Append-only in practice:
    nothing in this module updates or deletes a row once written."""

    review_pack = models.ForeignKey(DPAReviewPack, on_delete=models.CASCADE, related_name='approval_history')
    from_status = models.CharField(max_length=15, choices=DPAReviewPack.ApprovalStatus.choices, blank=True)
    to_status = models.CharField(max_length=15, choices=DPAReviewPack.ApprovalStatus.choices)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dpa_approval_history_entries')
    comment = models.TextField(blank=True)
    risk_counts_by_severity = models.JSONField(default=dict, blank=True)
    unresolved_blocker_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'DPA approval history entries'

    def __str__(self):
        return f'{self.from_status or "—"} → {self.to_status}'


class DPAPlaybookPosition(models.Model):
    """Standing negotiation position for one DPA topic — the fallback
    language and risk note a reviewer is pointed to instead of drafting
    from scratch each time. Org-scoped with a global default (organization
    IS NULL) so a firm can override a topic without duplicating the rest."""

    class Topic(models.TextChoices):
        PROCESSOR_ROLE_WORDING = 'PROCESSOR_ROLE_WORDING', 'Processor Role Wording'
        CONTROLLER_INSTRUCTIONS = 'CONTROLLER_INSTRUCTIONS', 'Controller Instructions'
        SUBPROCESSOR_AUTHORIZATION = 'SUBPROCESSOR_AUTHORIZATION', 'Subprocessor Authorization'
        INTERNATIONAL_TRANSFERS = 'INTERNATIONAL_TRANSFERS', 'International Transfers'
        SCC = 'SCC', 'Standard Contractual Clauses'
        BREACH_NOTIFICATION = 'BREACH_NOTIFICATION', 'Breach Notification'
        AUDIT_RIGHTS = 'AUDIT_RIGHTS', 'Audit Rights'
        DELETION_RETURN = 'DELETION_RETURN', 'Deletion and Return'
        DSAR_ASSISTANCE = 'DSAR_ASSISTANCE', 'DSAR Assistance'
        SECURITY_MEASURES = 'SECURITY_MEASURES', 'Security Measures'
        LIABILITY = 'LIABILITY', 'Liability Under DPA'
        CLIENT_DATA_ACCURACY = 'CLIENT_DATA_ACCURACY', 'Client Data Accuracy Responsibility'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='dpa_playbook_positions')
    topic = models.CharField(max_length=30, choices=Topic.choices)
    our_position = models.TextField()
    fallback_language = models.TextField(blank=True)
    risk_if_deviated = models.TextField(blank=True)
    owner = models.CharField(max_length=15, choices=DPARiskItem.Owner.choices, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['topic']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'topic'], name='unique_dpa_playbook_topic_per_org'),
        ]

    def __str__(self):
        return self.get_topic_display()


class ApprovalRule(models.Model):
    class TriggerType(models.TextChoices):
        VALUE_ABOVE = 'VALUE_ABOVE', 'Contract Value Above'
        JURISDICTION = 'JURISDICTION', 'Specific Jurisdiction'
        CONTRACT_TYPE = 'CONTRACT_TYPE', 'Contract Type'
        RISK_LEVEL = 'RISK_LEVEL', 'Risk Level'
        DATA_TRANSFER = 'DATA_TRANSFER', 'Cross-border Data Transfer'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='approval_rules')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    trigger_value = models.CharField(max_length=200, help_text='Threshold value or matching text')
    approval_step = models.CharField(max_length=20, choices=[
        ('LEGAL', 'Legal Review'),
        ('FINANCE', 'Finance Review'),
        ('PRIVACY', 'Privacy Review'),
        ('EXECUTIVE', 'Executive Approval'),
        ('COMPLIANCE', 'Compliance Review'),
    ])
    approver_role = models.CharField(max_length=20, choices=UserProfile.Role.choices)
    specific_approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_rules')
    sla_hours = models.PositiveIntegerField(default=48, help_text='SLA in hours for approval')
    escalation_after_hours = models.PositiveIntegerField(default=72, help_text='Auto-escalate after hours')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.name} ({self.get_trigger_type_display()})'


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes Requested'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        ESCALATED = 'ESCALATED', 'Escalated'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='approval_requests')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='approval_requests')
    rule = models.ForeignKey(ApprovalRule, on_delete=models.SET_NULL, null=True, blank=True)
    approval_step = models.CharField(max_length=50)
    sort_order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_assignments')
    delegated_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='delegated_approval_assignments')
    delegated_at = models.DateTimeField(null=True, blank=True)
    delegation_reason = models.TextField(
        blank=True,
        help_text='Why coverage was delegated (absence, workload, specialty).',
    )
    delegation_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When delegated coverage ends. Blank means open-ended.',
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_decisions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.contract.title} - {self.approval_step} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        skip_canonical = kwargs.pop('skip_canonical_requirement', False)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if skip_canonical or not is_new:
            return
        try:
            from contracts.models import ApprovalRequirement
            if ApprovalRequirement.objects.filter(legacy_request_id=self.pk).exists():
                return
            from contracts.services.approval_canonical import ensure_requirement_for_legacy_request
            ensure_requirement_for_legacy_request(self)
        except Exception:
            pass

    class Meta:
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['contract', 'sort_order'], name='ar_contract_sort_ix'),
        ]

    def can_transition_to(self, new_status):
        if not new_status:
            return False
        if new_status == self.status:
            return True
        allowed_transitions = {
            self.Status.PENDING: {
                self.Status.CHANGES_REQUESTED,
                self.Status.APPROVED,
                self.Status.REJECTED,
                self.Status.ESCALATED,
            },
            self.Status.ESCALATED: {
                self.Status.CHANGES_REQUESTED,
                self.Status.APPROVED,
                self.Status.REJECTED,
            },
            self.Status.CHANGES_REQUESTED: set(),
            self.Status.APPROVED: set(),
            self.Status.REJECTED: set(),
        }
        return new_status in allowed_transitions.get(self.status, set())

    def can_actor_transition(self, actor):
        if actor is None or not getattr(actor, 'is_authenticated', False):
            return False
        if self.assigned_to_id and self.assigned_to_id == actor.id:
            return True
        if self.organization_id:
            from .permissions import can_manage_organization
            return can_manage_organization(actor, self.organization)
        return False


class ApprovalRequirementQuerySet(models.QuerySet):
    pass


class ApprovalRequirementManager(models.Manager.from_queryset(ApprovalRequirementQuerySet)):
    pass


class ApprovalRequirement(models.Model):
    """Canonical Approval Requirement — why approval is needed (PAR-APR-001)."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        SATISFIED = 'SATISFIED', 'Satisfied'
        REJECTED = 'REJECTED', 'Rejected'
        RETURNED = 'RETURNED', 'Returned'
        INVALIDATED = 'INVALIDATED', 'Invalidated'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class AuthorityBasis(models.TextChoices):
        RULE = 'rule', 'Approval rule'
        MANUAL = 'manual', 'Manual submission'
        WORKFLOW_SUBMIT = 'workflow_submit', 'Workflow submit'
        AI_AD_HOC = 'ai_ad_hoc', 'AI-assisted ad hoc'
        LEGACY_UNKNOWN = 'legacy_unknown', 'Legacy / unknown'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='approval_requirements',
    )
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='approval_requirements')
    legacy_request = models.OneToOneField(
        'ApprovalRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='canonical_requirement',
    )
    rule = models.ForeignKey('ApprovalRule', on_delete=models.SET_NULL, null=True, blank=True)
    approval_step = models.CharField(max_length=50)
    sort_order = models.PositiveSmallIntegerField(default=0)
    authority_basis = models.CharField(
        max_length=32, choices=AuthorityBasis.choices, default=AuthorityBasis.LEGACY_UNKNOWN,
    )
    authority_reference = models.JSONField(default=dict, blank=True)
    contract_status_at_open = models.CharField(max_length=32, blank=True, default='')
    contract_lifecycle_stage_at_open = models.CharField(max_length=32, blank=True, default='')
    document_version = models.ForeignKey(
        'DocumentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_requirements',
    )
    document_version_missing = models.BooleanField(
        default=False,
        help_text='True when no Document Version could be bound at requirement open.',
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_requirements',
    )
    delegated_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='delegated_approval_requirements',
    )
    delegated_at = models.DateTimeField(null=True, blank=True)
    delegation_reason = models.TextField(blank=True, default='')
    delegation_ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateTimeField(null=True, blank=True)
    invalidation_reason = models.TextField(blank=True, default='')
    invalidated_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='opened_approval_requirements',
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ApprovalRequirementManager()

    class Meta:
        ordering = ['sort_order', 'opened_at']
        indexes = [
            models.Index(fields=['contract', 'status'], name='apreq_contract_status_ix'),
            models.Index(fields=['organization', 'status'], name='apreq_org_status_ix'),
        ]

    def __str__(self):
        return f'{self.contract_id} — {self.approval_step} ({self.get_status_display()})'


class ApprovalDecisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        from contracts.services.approval_canonical import IMMUTABLE_DECISION_FIELDS, ApprovalCanonicalError

        blocked = sorted(set(kwargs) & IMMUTABLE_DECISION_FIELDS)
        if blocked:
            raise ApprovalCanonicalError(
                f'QuerySet.update cannot mutate immutable ApprovalDecision fields {blocked}.'
            )
        return super().update(**kwargs)


class ApprovalDecisionManager(models.Manager.from_queryset(ApprovalDecisionQuerySet)):
    pass


class ApprovalDecision(models.Model):
    """Immutable Approval Decision tied to evaluated contract/document state (PAR-APR-001)."""

    class Outcome(models.TextChoices):
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        RETURNED = 'RETURNED', 'Returned'
        REVOKED = 'REVOKED', 'Revoked'
        ABSTAINED = 'ABSTAINED', 'Abstained'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='approval_decisions',
    )
    requirement = models.ForeignKey(
        ApprovalRequirement, on_delete=models.CASCADE, related_name='decisions',
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_decisions_made',
    )
    authority_holder_id = models.IntegerField(null=True, blank=True)
    acting_under_delegation = models.BooleanField(default=False)
    delegation_holder_id = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True, default='')
    contract_status = models.CharField(max_length=32, blank=True, default='')
    contract_lifecycle_stage = models.CharField(max_length=32, blank=True, default='')
    document_version = models.ForeignKey(
        'DocumentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_decisions',
    )
    document_version_missing = models.BooleanField(default=False)
    decided_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ApprovalDecisionManager()

    class Meta:
        ordering = ['-decided_at', '-pk']

    def __str__(self):
        return f'Decision {self.outcome} on requirement {self.requirement_id}'

    def save(self, *args, **kwargs):
        if self.pk:
            from contracts.services.approval_canonical import IMMUTABLE_DECISION_FIELDS, ApprovalCanonicalError

            previous = (
                type(self).objects.filter(pk=self.pk)
                .values(*IMMUTABLE_DECISION_FIELDS)
                .first()
            )
            if previous:
                for field in IMMUTABLE_DECISION_FIELDS:
                    if previous.get(field) != getattr(self, field, None):
                        raise ApprovalCanonicalError(
                            f'ApprovalDecision field "{field}" is immutable after creation.'
                        )
        super().save(*args, **kwargs)


class RoleDefinitionQuerySet(models.QuerySet):
    """Block QuerySet.update from bypassing RoleDefinition governance rules."""

    def update(self, **kwargs):
        from contracts.services.role_definition import IMMUTABLE_ROLE_DEFINITION_FIELDS, RoleDefinitionError

        blocked = sorted(set(kwargs) & IMMUTABLE_ROLE_DEFINITION_FIELDS)
        if blocked:
            raise RoleDefinitionError(
                f'QuerySet.update cannot mutate immutable RoleDefinition fields {blocked}.'
            )
        if 'is_system_managed' in kwargs:
            raise RoleDefinitionError(
                'QuerySet.update cannot change is_system_managed; use governed repair.'
            )
        return super().update(**kwargs)


class RoleDefinitionManager(models.Manager.from_queryset(RoleDefinitionQuerySet)):
    pass


class RoleDefinition(models.Model):
    """Canonical Role Definition catalogue entry (PAR-ID-001 additive slice / ADR-0014).

    Labels do not grant permissions. Runtime resolvers and membership authority
    are unchanged by this model.
    """

    class Category(models.TextChoices):
        WORKSPACE = 'WORKSPACE', 'Workspace'
        WORKFLOW = 'WORKFLOW', 'Workflow'
        APPROVAL = 'APPROVAL', 'Approval'
        SIGNATURE = 'SIGNATURE', 'Signature'
        SYSTEM = 'SYSTEM', 'System'
        LEGACY_UNKNOWN = 'LEGACY_UNKNOWN', 'Legacy unknown'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='role_definitions',
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=32, choices=Category.choices)
    is_active = models.BooleanField(default=True)
    is_system_managed = models.BooleanField(
        default=False,
        help_text='System-seeded definitions; code and category protected from casual edit.',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='role_definitions_created',
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='role_definitions_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RoleDefinitionManager()

    class Meta:
        ordering = ['organization_id', 'category', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'code'],
                name='roledef_org_code_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'category', 'is_active'], name='roledef_org_cat_active_ix'),
            models.Index(fields=['organization', 'is_active'], name='roledef_org_active_ix'),
        ]

    def __str__(self):
        return f'{self.code} ({self.organization_id})'

    def save(self, *args, **kwargs):
        skip_immutability = kwargs.pop('skip_role_definition_immutability', False)
        if self.pk and not skip_immutability:
            previous = (
                type(self).objects.filter(pk=self.pk)
                .values('code', 'organization_id', 'category', 'is_system_managed')
                .first()
            )
            if previous:
                from contracts.services.role_definition import assert_role_definition_immutable

                assert_role_definition_immutable(self, previous=previous)
        super().save(*args, **kwargs)


class BackgroundJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='background_jobs')
    job_type = models.CharField(max_length=80)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_background_jobs')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.job_type} ({self.get_status_display()})'


class ScheduledJobRun(models.Model):
    """Durable, per-run evidence that a scheduled/maintenance job actually ran.

    Replaces the previous reliance on green CI artifacts (which ran against an
    empty SQLite DB) as 'proof' that tenant jobs executed. One row per run, so
    operators can answer 'did renewals/reminders/retention run for org X last
    night, and what did they change?' directly from the production database.

    Never store secrets or full document content here — counts and short
    summaries only.
    """

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', 'Running'
        SUCCESS = 'SUCCESS', 'Success'
        PARTIAL = 'PARTIAL', 'Partial failure'
        FAILED = 'FAILED', 'Failed'
        SKIPPED = 'SKIPPED', 'Skipped (overlap)'

    run_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    job_name = models.CharField(max_length=100)
    # Null = a cross-tenant/global run (e.g. queue dispatch); otherwise the run
    # is scoped to a single organization.
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True,
        related_name='scheduled_job_runs',
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_examined = models.PositiveIntegerField(default=0)
    records_changed = models.PositiveIntegerField(default=0)
    notifications_created = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    alert_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Set when an operator failure-alert email was sent for this run. '
                  'Used for deduplication (one alert per job_name per hour).',
    )

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job_name', '-started_at'], name='sjr_job_started_ix'),
            models.Index(fields=['organization', 'job_name', 'status'], name='sjr_org_job_status_ix'),
        ]

    def __str__(self):
        scope = self.organization.slug if self.organization_id else 'global'
        return f'{self.job_name}[{scope}] {self.status} ({self.run_id})'

    @property
    def duration_seconds(self):
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class ContractVersion(models.Model):
    """Immutable snapshot of a contract at a point in time."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    title_snapshot = models.CharField(max_length=200)
    status_snapshot = models.CharField(max_length=20)
    content_snapshot = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True, help_text='SHA-256 of content_snapshot')
    change_summary = models.CharField(max_length=500, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('contract', 'version_number')
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['contract', '-version_number'], name='cv_contract_ver_ix'),
        ]

    def __str__(self):
        return f'{self.contract.title} v{self.version_number}'

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('ContractVersion records are immutable and cannot be updated.')
        import hashlib
        if self.content_snapshot and not self.content_hash:
            self.content_hash = hashlib.sha256(self.content_snapshot.encode()).hexdigest()
        super().save(*args, **kwargs)


class ClauseRecommendation(models.Model):
    """AI-suggested clause for a contract, optionally accepted by a user."""

    class ClauseType(models.TextChoices):
        LIMITATION_OF_LIABILITY = 'LIMITATION_OF_LIABILITY', 'Limitation of Liability'
        INDEMNIFICATION = 'INDEMNIFICATION', 'Indemnification'
        CONFIDENTIALITY = 'CONFIDENTIALITY', 'Confidentiality'
        TERMINATION = 'TERMINATION', 'Termination'
        GOVERNING_LAW = 'GOVERNING_LAW', 'Governing Law'
        DISPUTE_RESOLUTION = 'DISPUTE_RESOLUTION', 'Dispute Resolution'
        DATA_PROTECTION = 'DATA_PROTECTION', 'Data Protection'
        FORCE_MAJEURE = 'FORCE_MAJEURE', 'Force Majeure'
        PAYMENT_TERMS = 'PAYMENT_TERMS', 'Payment Terms'
        IP_OWNERSHIP = 'IP_OWNERSHIP', 'IP Ownership'
        WARRANTY = 'WARRANTY', 'Warranty'
        OTHER = 'OTHER', 'Other'

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='clause_recommendations')
    clause_type = models.CharField(max_length=40, choices=ClauseType.choices)
    recommendation_text = models.TextField()
    confidence = models.FloatField(default=0.8, help_text='0.0–1.0 confidence score')
    rationale = models.TextField(blank=True, help_text='Why this clause is recommended')
    accepted = models.BooleanField(default=False)
    accepted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_clause_recommendations')
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-confidence', 'clause_type']
        indexes = [
            models.Index(fields=['contract', 'accepted'], name='cr_contract_accepted_ix'),
        ]

    def __str__(self):
        return f'{self.get_clause_type_display()} for {self.contract.title}'


class OrgPolicy(models.Model):
    """Configurable policy controls for an organization."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='policy')
    mfa_required = models.BooleanField(default=False)
    require_approval_above_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Contracts above this value require approval',
    )
    data_transfer_review_required = models.BooleanField(default=True)
    retention_period_days = models.PositiveIntegerField(
        default=2555, help_text='Document retention period (default 7 years)',
    )
    max_api_tokens_per_user = models.PositiveIntegerField(default=5)
    allow_public_sharing = models.BooleanField(default=False)
    ai_features_enabled = models.BooleanField(default=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_org_policies')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Organisation Policy'
        verbose_name_plural = 'Organisation Policies'

    def __str__(self):
        return f'Policy for {self.organization}'


class ClauseUsageEvent(models.Model):
    """Tracks each time a clause template is used in a contract."""

    class Action(models.TextChoices):
        ADDED = 'ADDED', 'Added to contract'
        REMOVED = 'REMOVED', 'Removed from contract'
        ACCEPTED = 'ACCEPTED', 'Accepted during negotiation'
        REJECTED = 'REJECTED', 'Rejected during negotiation'
        MODIFIED = 'MODIFIED', 'Modified before use'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='clause_usage_events')
    clause = models.ForeignKey('ClauseTemplate', on_delete=models.CASCADE, related_name='usage_events')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='clause_usage_events')
    action = models.CharField(max_length=10, choices=Action.choices, default=Action.ADDED)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='clause_usage_events')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.clause.title} {self.action} on {self.contract_id}'


class OnboardingProgress(models.Model):
    """Tracks guided-setup completion state for an organisation."""

    STEPS = [
        'org_profile',
        'invite_members',
        'first_contract',
        'configure_policy',
        'connect_integration',
    ]

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='onboarding')
    steps_completed = models.JSONField(default=list, blank=True)
    current_step = models.CharField(max_length=50, default='org_profile')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Onboarding for {self.organization} ({"done" if self.completed else self.current_step})'

    @property
    def progress_pct(self) -> int:
        total = len(self.STEPS)
        done = len([s for s in self.steps_completed if s in self.STEPS])
        return int(done / total * 100) if total else 0


class BillingPlan(models.Model):
    """Available subscription tiers."""

    class Tier(models.TextChoices):
        FREE = 'FREE', 'Free'
        STARTER = 'STARTER', 'Starter'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional'
        ENTERPRISE = 'ENTERPRISE', 'Enterprise'

    name = models.CharField(max_length=50, choices=Tier.choices, unique=True)
    max_users = models.PositiveIntegerField(default=5)
    max_contracts = models.PositiveIntegerField(default=50)
    max_api_calls_per_month = models.PositiveIntegerField(default=1000)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class OrgBillingSubscription(models.Model):
    """Links an organisation to its current plan and Stripe subscription."""

    class Status(models.TextChoices):
        FREE = 'free', 'Free'
        TRIALING = 'trialing', 'Trialing'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past due'
        CANCELED = 'canceled', 'Canceled'
        INCOMPLETE = 'incomplete', 'Incomplete'

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='billing_subscription')
    plan = models.ForeignKey(BillingPlan, on_delete=models.PROTECT, related_name='subscriptions')
    subscribed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Stripe references — blank until first payment
    stripe_customer_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, default='')
    subscription_status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.FREE
    )
    current_period_end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.organization.name} → {self.plan.name} ({self.subscription_status})'

    @property
    def is_paid(self) -> bool:
        return self.subscription_status in (self.Status.ACTIVE, self.Status.TRIALING)


class UsageRecord(models.Model):
    """Monthly usage snapshot for an organisation."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='usage_records')
    period_start = models.DateField()
    period_end = models.DateField()
    user_count = models.PositiveIntegerField(default=0)
    contract_count = models.PositiveIntegerField(default=0)
    api_call_count = models.PositiveIntegerField(default=0)
    overage_users = models.BooleanField(default=False)
    overage_contracts = models.BooleanField(default=False)
    overage_api_calls = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_start']
        unique_together = ('organization', 'period_start')

    def __str__(self):
        return f'{self.organization.name} usage {self.period_start}'


class SearchTelemetryEvent(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='search_events')
    query = models.CharField(max_length=500)
    result_count = models.PositiveIntegerField(default=0)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='search_events')
    search_type = models.CharField(max_length=20, default='contract')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Search "{self.query}" by {self.performed_by} ({self.search_type})'


class WorkInteractionEvent(models.Model):
    """Lightweight product telemetry for the personal work operating loop.

    Distinct from AuditLog: high-volume discovery/open events live here.
    Outcome mutations still write AuditLog; this table carries surface
    attribution needed to prove whether My Work is the hub.
    """

    class Event(models.TextChoices):
        SURFACED = 'surfaced', 'Work item surfaced'
        OPENED = 'opened', 'Work item opened'
        PRIMARY_ACTION = 'primary_action', 'Primary action taken'
        COMPLETED = 'completed', 'Work completed'
        RETURNED = 'returned', 'Work returned'
        REJECTED = 'rejected', 'Work rejected'
        SLA_BREACHED = 'sla_breached', 'SLA breached / overdue transition'

    class Surface(models.TextChoices):
        MY_WORK = 'my_work', 'My Work'
        APPROVALS = 'approvals', 'Reviews & Approvals'
        OBLIGATIONS = 'obligations', 'Obligations'
        PRIVACY = 'privacy', 'Privacy Reviews'
        TASKS = 'tasks', 'Legal Tasks'
        CONTRACT_DETAIL = 'contract_detail', 'Contract detail'
        API = 'api', 'API'
        JOB = 'job', 'Background job'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='work_interaction_events',
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='work_interaction_events',
    )
    event = models.CharField(max_length=32, choices=Event.choices)
    work_item_id = models.CharField(max_length=80, help_text='Stable row id, e.g. approval:12')
    work_kind = models.CharField(max_length=40, blank=True)
    surface = models.CharField(max_length=32, choices=Surface.choices, default=Surface.MY_WORK)
    contract_id = models.PositiveIntegerField(null=True, blank=True)
    contract_type = models.CharField(max_length=40, blank=True)
    is_restricted = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    is_overdue = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['organization', 'event', 'occurred_at'], name='work_evt_org_evt_ix'),
            models.Index(fields=['organization', 'work_item_id', 'event'], name='work_evt_item_evt_ix'),
            models.Index(fields=['organization', 'surface', 'event'], name='work_evt_surface_ix'),
        ]

    def __str__(self):
        return f'{self.event} {self.work_item_id} via {self.surface}'


class RetentionActionLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='retention_action_logs')
    contract = models.ForeignKey('Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='retention_logs')
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='retention_actions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} on contract {self.contract_id} by {self.performed_by}'


class CVEScanRecord(models.Model):
    packages_checked = models.PositiveIntegerField(default=0)
    issues_found = models.PositiveIntegerField(default=0)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cve_scans')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'CVE scan {self.created_at} ({self.packages_checked} packages)'


class RestoreDrill(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='restore_drills')
    drill_date = models.DateField()
    rto_target_hours = models.FloatField(default=4.0)
    rpo_target_hours = models.FloatField(default=1.0)
    actual_rto_minutes = models.PositiveIntegerField(null=True, blank=True)
    actual_rpo_minutes = models.PositiveIntegerField(null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='restore_drills')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-drill_date']

    def __str__(self):
        return f'Restore drill {self.drill_date} ({self.organization})'


# Alias-first structural migration layer.
# These symbols let care-native code paths move toward case-oriented names
# without changing database tables, migration history, or legacy imports yet.
Case = Contract
CaseMatter = Matter
CaseSignal = LegalTask
CaseRiskSignal = RiskLog
CaseApproval = ApprovalRequest
