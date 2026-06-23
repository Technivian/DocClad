# DocClad Pilot Activation Sprint

**Document Version:** 1.0  
**Date:** 2026-06-23  
**Status:** Ready for Operator Execution

---

## SECTION 1: RELEASE CANDIDATE FREEZE

**Final Approved Commit:**
```
Commit Hash: 7515448
Message: fix(5L-closure): restore strict audit trigger, fix delivery URL, repair upload success path
Branch: remediation/phase1-correctness-security
Date: 2026-06-23
```

**RC Tag:** `rc-pilot-phase5`

**Migration Head:** `0060_auditlog_restore_strict_trigger`  
(Restores strict append-only trigger; no runtime bypass)

**Approved Feature Flags (LOCKED):**
```
ENABLED:
  - contract_repository=true
  - approvals_workflow=true
  - document_storage=true
  - audit_chain=true
  - mfa_required=true
  - expiration_automation=true
  - operator_job_alerts=true

DISABLED:
  - saml_enabled=false
  - esign_enabled=false
  - renewal_reminders=false
  - obligation_reminders=false
  - billing=false
```

**Deployment Topology:**
```
Web:    Render FastAPI/Gunicorn (auto-scaled, 1+ instances)
Worker: Render RQ background jobs (auto-scaled, 1+ instances)
Cron:   Render APScheduler (single instance, no auto-scale)
DB:     PostgreSQL 14+ (direct connection, port 5432, NOT pooler)
Cache:  Redis (shared rate-limiting, sessions)
Storage: S3-compatible (versioning enabled, private ACLs)
Email:   Resend (production account, verified domain)
```

**Pilot Scope (User-Facing Features):**
- ✅ Contract creation, editing, lifecycle management
- ✅ Organization invitations with MFA
- ✅ Document upload, download, soft-delete (with audit)
- ✅ Approval workflows
- ✅ Password reset (with canonical URLs)
- ✅ Scheduled job execution (contract expiration)
- ✅ Operator job-failure alerts

**Known Accepted Limitations:**
- Document version restore: Operator recovery via S3 API only (no user-facing UI)
- Orphaned object recovery: Operator manual reconciliation (no automated job yet)
- Monitoring: Manual dashboard (no automated 3rd-party alerting yet)
- SAML: Disabled pending IdP configuration
- E-signature: Disabled pending provider integration

**Code Freeze:** No new features until pilot is stable and sign-off complete.

---

## SECTION 2: ACTIVATION CONDITIONS CHECKLIST

### CONDITION 1: Production PostgreSQL

**Requirement:**  PostgreSQL 14+ direct connection on port 5432 (NOT transaction-mode pooler)

**Evidence Needed:**
- [ ] Connection string configured and tested
- [ ] pg_version returns >= 14
- [ ] Django system check passes: `python manage.py check`
- [ ] Full test suite passes: `python manage.py test tests --create-db` exits 0

**Verification Command:**
```bash
# Operator runs:
psql -h $DB_HOST -p 5432 -U $DB_USER -d $DB_NAME -c "SELECT version();"
# Expected: PostgreSQL 14.x or higher

DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py check
# Expected: System check identified no issues (0 silenced).
```

**Closure Evidence:**
```
[ ] Operator: Connection test successful
[ ] Operator: System check passed
[ ] Operator: Test suite runs cleanly (if possible in staging)
```

**Owner:** Technical Owner  
**Blocker if missing:** YES — application cannot start

---

### CONDITION 2: S3-Compatible Storage with Versioning

**Requirement:** Durable S3 (or S3-compatible) bucket with versioning enabled, private ACLs

**Evidence Needed:**
- [ ] Bucket created and credentials configured
- [ ] Versioning enabled on bucket
- [ ] Public access blocked (all ACLs: Block=True)
- [ ] Test file upload succeeds
- [ ] Test file download via signed URL succeeds

**Verification Command:**
```bash
# Operator runs:
aws s3api get-bucket-versioning --bucket $BUCKET_NAME
# Expected: Status: Enabled

aws s3api get-public-access-block --bucket $BUCKET_NAME
# Expected: All BlockPublic*: true

# Test upload:
echo "test content" | aws s3 cp - s3://$BUCKET_NAME/test-pilot.txt
aws s3 cp s3://$BUCKET_NAME/test-pilot.txt /tmp/test-download.txt
# Expected: Both commands succeed
```

**Closure Evidence:**
```
[ ] Operator: Versioning enabled
[ ] Operator: Public access blocked
[ ] Operator: Test file uploaded and downloaded
[ ] Operator: Signed URL generated and works
```

**Owner:** Technical Owner  
**Blocker if missing:** YES — documents cannot be stored

---

### CONDITION 3: Resend Production Account & Credentials

**Requirement:** Resend upgraded from sandbox to production account with API key

**Evidence Needed:**
- [ ] Resend account upgraded (not sandbox)
- [ ] Production API key generated and stored in environment
- [ ] Test email sent successfully
- [ ] OPERATOR_ALERT_EMAIL environment variable set

**Verification Command:**
```bash
# Operator runs test:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py shell <<'EOF'
from contracts.services.notifications import send_operator_job_failure_alert
from unittest.mock import MagicMock

# Create a mock job_run object
mock_job = MagicMock()
mock_job.job_name = "pilot-test-alert"
mock_job.run_id = "test-pilot-001"
mock_job.organization_id = None
mock_job.organization = MagicMock(slug="system")
mock_job.started_at = None
mock_job.duration_seconds = 1.5
mock_job.records_examined = 100
mock_job.records_changed = 50
mock_job.error_summary = "Test alert"
mock_job.pk = 9999

result = send_operator_job_failure_alert(mock_job)
print(f"Alert sent: {result}")
EOF
# Expected: Alert sent: True (or False if OPERATOR_ALERT_EMAIL not set, which is ok)
```

**Closure Evidence:**
```
[ ] Operator: Resend account is production (not sandbox)
[ ] Operator: API key configured in environment
[ ] Operator: OPERATOR_ALERT_EMAIL set to real operator email
[ ] Operator: Test alert email received in inbox
```

**Owner:** Pilot Operator  
**Blocker if missing:** YES — notifications fail silently

---

### CONDITION 4: SPF, DKIM, DMARC Records

**Requirement:** DNS records created and verified for sender domain

**Evidence Needed:**
- [ ] SPF record published and verified
- [ ] DKIM record published and verified by Resend
- [ ] DMARC record published
- [ ] Resend domain verification shows "Verified"

**Verification Command:**
```bash
# Operator runs:
dig TXT sender.docclad.com
# Expected: SPF record present

dig TXT default._domainkey.sender.docclad.com
# Expected: DKIM record present

dig TXT _dmarc.sender.docclad.com
# Expected: DMARC policy present

# Resend verification (via dashboard):
# Login to Resend → Sending Domain → "Verified" status
```

**Closure Evidence:**
```
[ ] Operator: SPF record published and resolves
[ ] Operator: DKIM record published and Resend shows "Verified"
[ ] Operator: DMARC record published
[ ] Operator: Screenshot of Resend dashboard showing "Verified"
```

**Owner:** Pilot Operator  
**Blocker if missing:** YES — emails may be rejected as spam

---

### CONDITION 5: Production Environment Variables

**Requirement:** All required environment variables set correctly for production

**Required Variables:**
```
SECRET_KEY                 — 50+ random chars (not hardcoded)
DEBUG                      — false
ALLOWED_HOSTS              — production domain(s)
CSRF_TRUSTED_ORIGINS       — production domain(s)
APP_BASE_URL               — https://production.domain (HTTPS required)
DATABASE_URL               — postgresql://user:pass@host:5432/dbname
OPERATOR_ALERT_EMAIL       — ops@company.com
RESEND_API_KEY             — re_xxxxxxxxxxxxxxxxxxxxxxxx
REDIS_URL                  — redis://host:6379/0
DEFAULT_FROM_EMAIL         — noreply@sender.docclad.com
DJANGO_SETTINGS_MODULE     — config.settings_production
```

**Verification Command:**
```bash
# Operator audit (without exposing secrets):
env | grep -E "^(DEBUG|ALLOWED_HOSTS|APP_BASE_URL|OPERATOR_ALERT_EMAIL|DEFAULT_FROM_EMAIL)" | sort

# Expected output (redacted):
ALLOWED_HOSTS=pilot.docclad.com
APP_BASE_URL=https://pilot.docclad.com
DEBUG=false
DEFAULT_FROM_EMAIL=noreply@pilot.docclad.com
OPERATOR_ALERT_EMAIL=ops@company.com

# Verify no hardcoded secrets in code:
grep -r "SECRET_KEY\s*=" config/settings_production.py
# Expected: SECRET_KEY = os.getenv('SECRET_KEY')  (or similar)
```

**Closure Evidence:**
```
[ ] Operator: Environment variable audit completed
[ ] Operator: SECRET_KEY is random and non-repeating
[ ] Operator: DEBUG=false in production
[ ] Operator: All HTTPS URLs enforce https://
[ ] Operator: No hardcoded credentials in code
```

**Owner:** Pilot Operator  
**Blocker if missing:** YES — application cannot start securely

---

### CONDITION 6: Backup Storage & Schedule

**Requirement:** pg_dump backup storage configured; first backup created and restore tested

**Evidence Needed:**
- [ ] Backup storage location defined (S3, managed backup service, etc.)
- [ ] First pg_dump backup created successfully
- [ ] Backup can be restored to fresh PostgreSQL instance
- [ ] Restored database is clean and consistent

**Verification Command:**
```bash
# Operator runs:
# 1. Create backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > /backup/docclad-pilot-$(date +%Y%m%d-%H%M%S).sql.gz

# 2. Upload to backup storage (S3 or managed service)
aws s3 cp /backup/docclad-pilot-*.sql.gz s3://backup-bucket/docclad-pilot/

# 3. Create fresh test database and restore
createdb docclad_test_restore
gunzip -c /backup/docclad-pilot-*.sql.gz | psql -d docclad_test_restore

# 4. Verify restoration
psql docclad_test_restore -c "SELECT COUNT(*) FROM auth_user;"
psql docclad_test_restore -c "SELECT COUNT(*) FROM contracts_organization;"
# Expected: Non-zero counts

# 5. Verify audit trigger exists
psql docclad_test_restore -c "SELECT proname FROM pg_proc WHERE proname = 'contracts_auditlog_append_only';"
# Expected: contracts_auditlog_append_only
```

**Closure Evidence:**
```
[ ] Operator: First backup created and timestamped
[ ] Operator: Backup uploaded to durable storage
[ ] Operator: Backup size recorded (for future trend analysis)
[ ] Operator: Restore to fresh DB completed successfully
[ ] Operator: Restored DB has data integrity (row counts match)
[ ] Operator: Audit trigger exists on restored DB
[ ] Operator: Backup schedule configured (daily, retention policy)
```

**Owner:** Pilot Operator  
**Blocker if missing:** YES — no disaster recovery possible

---

### CONDITION 7: Monitoring & Alerting Dashboard

**Requirement:** Dashboard set up to monitor pilot-critical signals

**Signals to Monitor:**
- Web service uptime (Render health check)
- Worker queue depth (RQ queue length)
- Cron job execution (APScheduler logs)
- Database connection errors (application logs)
- 5xx error rate (Render metrics)
- Job failure alerts (OPERATOR_ALERT_EMAIL)
- Audit chain status (manual: `python manage.py verify_audit_chain`)

**Evidence Needed:**
- [ ] Monitoring dashboard created (Render, Datadog, custom, etc.)
- [ ] All signals added to dashboard
- [ ] Pilot Operator trained on dashboard interpretation
- [ ] Escalation path defined (who to contact if alert fires)

**Verification Command:**
```bash
# Operator creates dashboard with these panels:
# 1. Render web uptime (last 24h)
# 2. Render worker uptime (last 24h)
# 3. RQ queue depth trend
# 4. 5xx error rate (last 1h)
# 5. Application logs (ERROR, WARNING level)
# 6. Database connection pool status (if available)
# 7. Job execution history (from DB: ScheduledJobRun)

# Manual audit check command:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py verify_audit_chain --all-organizations
# Expected: All organizations show VERDICT_VALID
```

**Closure Evidence:**
```
[ ] Operator: Dashboard created and accessible
[ ] Operator: All required signals added
[ ] Operator: Pilot Operator trained (walkthrough completed)
[ ] Operator: Escalation contacts documented
[ ] Operator: Alert thresholds set (e.g., queue depth > 100 = alert)
```

**Owner:** Technical Owner  
**Blocker if missing:** NO — pilot can run with manual checks, but increases risk

---

### CONDITION 8: MFA & SAML Policy

**Requirement:** MFA policy documented and enforced; SAML disabled or explicitly configured

**Evidence Needed:**
- [ ] MFA required by default for pilot organizations
- [ ] Test user enrolled in MFA
- [ ] MFA recovery codes generated and stored securely
- [ ] SAML explicitly disabled (feature flag = false) OR configured with live IdP
- [ ] MFA bypass attempts are logged

**Verification Command:**
```bash
# Operator creates test organization and user:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py shell <<'EOF'
from django.contrib.auth import get_user_model
from contracts.models import Organization, OrganizationMembership

# Create test org
org = Organization.objects.create(name="Pilot Test Org", slug="pilot-test")

# Create test user
User = get_user_model()
user = User.objects.create_user(
    username="pilot-test-user",
    email="pilot@example.com",
    password="TestPilot!123"
)

# Add to org with MFA required
OrganizationMembership.objects.create(
    organization=org,
    user=user,
    role="OWNER",
    is_active=True,
    mfa_required=True  # If field exists; otherwise check org-level setting
)

print(f"Test org: {org.id}, user: {user.id}")
EOF

# Test MFA login:
# 1. Navigate to /login
# 2. Enter test-user credentials
# 3. Verify redirected to MFA challenge page
# 4. No login succeeds without MFA code
```

**Closure Evidence:**
```
[ ] Operator: MFA required=true for pilot organizations (verified in DB)
[ ] Operator: Test user enrolled in MFA (TOTP secret generated)
[ ] Operator: Test MFA challenge page works
[ ] Operator: Recovery codes generated and can be downloaded
[ ] Operator: SAML disabled or explicitly configured
[ ] Operator: MFA bypass attempts are logged
```

**Owner:** Pilot Operator  
**Blocker if missing:** YES — security risk

---

### CONDITION 9: Feature Flag Lock

**Requirement:** Pilot-excluded features are disabled and cannot be accidentally activated

**Evidence Needed:**
- [ ] Feature flags for excluded features set to false
- [ ] Code paths for excluded features are unreachable (or guarded by feature checks)
- [ ] Settings audit shows no accidental enables

**Verification Command:**
```bash
# Operator audit:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py shell <<'EOF'
from config.feature_flags import (
    is_saml_enabled,
    is_esign_enabled,
    is_renewal_reminders_enabled,
    is_obligation_reminders_enabled,
)

print(f"SAML enabled: {is_saml_enabled()}")  # Expected: False
print(f"E-sign enabled: {is_esign_enabled()}")  # Expected: False
print(f"Renewal reminders: {is_renewal_reminders_enabled()}")  # Expected: False
print(f"Obligation reminders: {is_obligation_reminders_enabled()}")  # Expected: False
EOF

# Grep for hardcoded enables:
grep -r "FEATURE.*=.*True" config/settings_production.py
# Expected: No matches (all should be from environment)
```

**Closure Evidence:**
```
[ ] Operator: Feature flag audit completed
[ ] Operator: All pilot-excluded features = false
[ ] Operator: Settings contain no hardcoded true values
[ ] Operator: Environment audit confirms flags are environment-driven
```

**Owner:** DevOps  
**Blocker if missing:** NO — low risk if other controls in place, but best practice

---

### CONDITION 10: Signed Operator Runbook

**Requirement:** Documented runbook for daily operations, emergencies, and recovery

**Sections Required:**
1. **Daily Checks** — what to verify each morning
2. **Emergency Response** — actions for web outage, DB failure, email failure
3. **Rollback Procedure** — steps to rollback or roll-forward
4. **Job Recovery** — how to retry failed jobs without duplication
5. **Password Reset Troubleshooting** — MFA issues, token expiry
6. **Audit Verification** — how to verify chain integrity post-incident
7. **Contact Escalation** — who to contact for each severity level

**Evidence Needed:**
- [ ] Runbook document created and reviewed
- [ ] All 7 sections complete
- [ ] Pilot Operator and Technical Owner have signed off
- [ ] Runbook is version-controlled or stored in shared location

**Verification Command:**
```bash
# Operator creates runbook document with sections above
# Example location: /docs/PILOT_OPERATIONS_RUNBOOK.md

# Checklist for Pilot Operator review:
# [ ] I understand daily monitoring tasks
# [ ] I can execute emergency rollback
# [ ] I can verify audit chains
# [ ] I know who to contact for each severity
# [ ] I have tested backup restore process
```

**Closure Evidence:**
```
[ ] Operator: Runbook document exists and is accessible
[ ] Operator: All 7 sections are complete
[ ] Operator: Runbook is reviewed by Pilot Operator
[ ] Operator: Runbook is reviewed by Technical Owner
[ ] Operator: Sign-off signatures collected
```

**Owner:** Technical Owner  
**Blocker if missing:** NO — pilot can run with ad-hoc procedures, but increases risk

---

## SECTION 3: DEPLOYMENT TO PILOT ENVIRONMENT

### 3.1 Pre-Deployment Checklist

Before deploying, verify:
- [ ] All 10 activation conditions above are CLOSED
- [ ] RC commit hash is correct: `7515448`
- [ ] No new commits have been made to the branch since RC freeze
- [ ] Database is at migration `0060_auditlog_restore_strict_trigger` (or empty)
- [ ] Backup of any existing pilot data has been created

### 3.2 Deployment Steps

**Step 1: Deploy Application Code**
```bash
# Operator runs (via Render or deployment pipeline):
git checkout rc-pilot-phase5
git pull origin rc-pilot-phase5
# Verify HEAD is at commit 7515448
git rev-parse HEAD
# Expected output: 7515448

# Deploy to Render:
# - Set environment variables (see CONDITION 5)
# - Trigger deploy via Render dashboard or CLI
# - Wait for all services to show "Active"
```

**Step 2: Run Migrations**
```bash
# Operator runs (via Render console or SSH):
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py migrate --noinput

# Expected output:
# Running migrations:
#   Applying contracts.0060_auditlog_restore_strict_trigger... OK
```

**Step 3: Verify Health**
```bash
# Operator runs:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py check

# Expected: System check identified no issues (0 silenced).

# Check service status via Render:
# - Web service: health check passing
# - Worker service: RQ listening and no errors in logs
# - Cron service: APScheduler running

# Check database:
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM auth_user;"
# Expected: Non-zero (or zero if fresh pilot DB)

# Check audit trigger:
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "\df+ contracts_auditlog_append_only"
# Expected: Function contracts_auditlog_append_only exists
```

### 3.3 Deployment Verification

Record:
```
[ ] Deployment timestamp: __________
[ ] Commit hash verified: 7515448
[ ] Migration 0060 applied successfully
[ ] Web service health: OK
[ ] Worker service health: OK
[ ] Cron service health: OK
[ ] Database accessible: OK
[ ] Audit trigger exists: OK
[ ] Operator: Signed off on deployment
```

---

## SECTION 4: LIVE SMOKE TESTS

Run these tests in order. Use one pilot organization and one test user created during CONDITION 8.

### 4.1 Authentication & MFA

**Test 4.1.1: Login with MFA**
```
Precondition: Test user exists with MFA required, TOTP secret generated
Steps:
  1. Open https://pilot.docclad.com/login
  2. Enter username: pilot-test-user, password: TestPilot!123
  3. Verify redirected to MFA challenge page
  4. Open authenticator app (or use recovery code)
  5. Enter 6-digit code
  6. Verify redirected to dashboard
Expected: Login succeeds; user is authenticated

Record:
[ ] Login page loads
[ ] MFA challenge page loads
[ ] MFA code accepted
[ ] Dashboard accessible
[ ] Audit event: auth.login_succeeded logged
```

**Test 4.1.2: Password Reset**
```
Precondition: Test user exists
Steps:
  1. Navigate to /forgot-password
  2. Enter test user email: pilot@example.com
  3. Verify email received within 60 seconds
  4. Click reset link in email
  5. Verify link uses https://pilot.docclad.com (not localhost or request.host)
  6. Enter new password
  7. Verify login works with new password
  8. Re-enable MFA if needed
Expected: Password reset succeeds; link uses canonical APP_BASE_URL

Record:
[ ] Forgot-password form works
[ ] Email received within 60 seconds
[ ] Reset link is canonical (https://pilot.docclad.com/...)
[ ] New password works
[ ] Old password no longer works
[ ] Audit event: auth.password_reset_completed logged
```

### 4.2 Organization & Invitations

**Test 4.2.1: Invite User**
```
Precondition: Test organization exists; test user is OWNER
Steps:
  1. Login as test user (with MFA)
  2. Navigate to /contracts/organizations/team
  3. Click "Invite Member"
  4. Enter invite email: pilot-invite@example.com
  5. Select role: MEMBER
  6. Click "Send Invitation"
  7. Verify invitation email received within 60 seconds
  8. Click accept link in email
  9. Verify invitee is added to organization
Expected: Invitation accepted; user can login

Record:
[ ] Invitation form works
[ ] Email received within 60 seconds
[ ] Invitation link is canonical (https://pilot.docclad.com/...)
[ ] Accept link works
[ ] Invitee added to org
[ ] Audit events logged: invite_created, invite.delivery_succeeded
```

### 4.3 Document Upload & Download

**Test 4.3.1: Upload Document**
```
Precondition: Test organization exists; test user is logged in
Steps:
  1. Navigate to /contracts/documents
  2. Click "Upload Document"
  3. Select file: sample.pdf (or .txt)
  4. Enter title: "Pilot Test Document"
  5. Click "Upload"
  6. Verify file appears in document list within 30 seconds
Expected: Upload succeeds; document is searchable

Record:
[ ] Upload form works
[ ] File appears in list
[ ] Document has metadata (size, type, hash)
[ ] Audit event: document.uploaded logged
[ ] S3 object exists (verify via AWS CLI)
```

**Test 4.3.2: Download Document**
```
Precondition: Document uploaded in previous test
Steps:
  1. Navigate to document detail
  2. Click "Download"
  3. Verify file downloads within 30 seconds
  4. Verify file content matches original
  5. Verify signed URL is canonical (https://pilot.docclad.com or S3 signed URL)
Expected: Download succeeds; no localhost URLs

Record:
[ ] Download link works
[ ] File downloads correctly
[ ] File content intact
[ ] Download logged in audit
```

### 4.4 Contract Lifecycle

**Test 4.4.1: Create Contract**
```
Precondition: Test organization exists; test user is logged in
Steps:
  1. Navigate to /contracts/new
  2. Enter title: "Pilot Test Contract"
  3. Select status: DRAFT
  4. Click "Create"
  5. Verify contract appears in contract list
Expected: Contract created; status is DRAFT

Record:
[ ] Creation form works
[ ] Contract appears in list
[ ] Lifecycle stage is DRAFTING (default)
[ ] Audit event: contract.created logged
```

**Test 4.4.2: Transition Contract**
```
Precondition: Contract created in previous test
Steps:
  1. Open contract detail
  2. Click "Approve" (or next workflow state)
  3. Verify status updates
  4. Verify audit event logged
Expected: Transition succeeds; audit trail updated

Record:
[ ] Transition works
[ ] Status updated
[ ] Timestamp updated
[ ] Audit event logged
```

### 4.5 Scheduled Jobs & Expiration

**Test 4.5.1: Contract Expiration Check**
```
Precondition: Contract exists with expiration_date < today + 30 days
Steps:
  1. Wait for cron to execute (or manually trigger via Django shell)
  2. Check ScheduledJobRun table for recent run
  3. Verify job status is SUCCESS or PENDING
  4. If contract is expired, verify lifecycle_stage changed to EXPIRED
Expected: Cron executes; contracts are marked as expired

Record:
[ ] Cron job executed
[ ] Job run logged in DB
[ ] Contract status updated if expired
[ ] Audit event logged
[ ] No job duplication (same job not run twice)
```

### 4.6 Operator Job Failure Alert

**Test 4.6.1: Trigger Job Failure Alert**
```
Precondition: OPERATOR_ALERT_EMAIL is set to a monitored email address
Steps:
  1. Create a test job that will fail (via Django shell or test script)
  2. Wait for job execution or manually execute
  3. Verify error is logged in ScheduledJobRun.error_summary
  4. Verify alert email received within 2 minutes
  5. Verify alert does NOT contain raw exception; only error class name
Expected: Alert sent with safe error summary

Record:
[ ] Job failure logged
[ ] Alert email received
[ ] Alert contains: job name, run ID, error class (not raw exception)
[ ] Alert does NOT contain: stack trace, credentials, raw payload
[ ] Audit event logged
```

### 4.7 Audit Chain Verification

**Test 4.7.1: Verify Audit Chain**
```
Precondition: Multiple audit events created during previous tests
Steps:
  1. Run: python manage.py verify_audit_chain --all-organizations
  2. Verify all organizations show VERDICT_VALID
  3. Check for any missing seq numbers or broken links
Expected: All chains pass integrity verification

Record:
[ ] Audit chain verification completed
[ ] All organizations: VERDICT_VALID
[ ] No broken links
[ ] No missing seq numbers
[ ] System chain (NULL org) also validates
```

### 4.8 Backup Creation & Restore

**Test 4.8.1: Create Backup & Restore**
```
Precondition: Pilot database has data from previous tests
Steps:
  1. Create backup: pg_dump ... | gzip > backup.sql.gz
  2. Create fresh test database: createdb docclad_test_restore
  3. Restore: gunzip -c backup.sql.gz | psql docclad_test_restore
  4. Verify restored DB has same data:
     - SELECT COUNT(*) FROM contracts_contract; (should match original)
     - SELECT COUNT(*) FROM contracts_auditlog; (should match original)
  5. Verify audit trigger exists on restored DB
Expected: Restore succeeds; data is consistent; trigger preserved

Record:
[ ] Backup created successfully
[ ] Backup size: _______ MB
[ ] Restore to fresh DB completed
[ ] Data row counts match original
[ ] Audit trigger exists on restored DB
[ ] Audit chain verification passes on restored DB
```

---

## SECTION 5: EXTERNAL DEPENDENCIES VERIFICATION

### 5.1 Email Delivery

**Evidence to Collect:**
- [ ] Real email from Resend was accepted (not bounced/rejected)
- [ ] Email arrived in inbox (not spam folder)
- [ ] Sender domain passes SPF/DKIM/DMARC checks
- [ ] Email contains canonical app URL (https://pilot.docclad.com/)

**Verification:**
```
# Check Resend dashboard:
# 1. Navigate to Resend dashboard → "Emails" tab
# 2. Verify sent emails show "Delivered" status (not Bounced)
# 3. For each email, verify:
#    - Recipient address correct
#    - Subject matches expected
#    - Sent timestamp matches test time
# 4. Check SPF/DKIM/DMARC results: All should show "Pass"
```

**Record:**
```
[ ] Email delivery: Confirmed
[ ] Sender domain authentication: Passed
[ ] Email in inbox (not spam): Confirmed
[ ] Content includes canonical URL: Confirmed
```

### 5.2 Object Storage Durability

**Evidence to Collect:**
- [ ] Document uploaded and stored in S3
- [ ] Document survives application restart/redeploy
- [ ] Signed URL works after 5+ minute delay
- [ ] Versioning prevents data loss on overwrite

**Verification:**
```bash
# After document upload in Test 4.3.1:
# 1. Verify S3 object exists:
aws s3 ls s3://pilot-bucket/documents/

# 2. Redeploy application (or restart web service)
# 3. Verify document is still downloadable:
#    - Login to app
#    - Navigate to document
#    - Click download
#    - File downloads successfully

# 4. Test signed URL persistence:
#    - Get signed URL from document detail page
#    - Wait 5+ minutes
#    - Click URL again
#    - File downloads successfully

# 5. Verify versioning:
#    - Upload same file twice (different content)
#    - List object versions: aws s3api list-object-versions --bucket ...
#    - Both versions should exist
```

**Record:**
```
[ ] S3 object created and accessible: Confirmed
[ ] Document survives restart: Confirmed
[ ] Signed URL works after 5+ min: Confirmed
[ ] Versioning works (multiple versions exist): Confirmed
```

### 5.3 Background Job Execution

**Evidence to Collect:**
- [ ] Real scheduled job touches pilot database
- [ ] Job execution is logged (ScheduledJobRun row created)
- [ ] Job deduplication works (same job not run twice in same window)
- [ ] Worker process is healthy and processing jobs

**Verification:**
```bash
# 1. Trigger a scheduled job (via Django shell or wait for cron):
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py shell <<'EOF'
from contracts.services.background_jobs import queue_background_job
queue_background_job("run_expiration_checks", organization_id=None)
EOF

# 2. Monitor job execution:
watch -n 5 'psql -h ... -U ... -d ... -c "SELECT * FROM contracts_scheduledjobrun ORDER BY id DESC LIMIT 5;"'

# 3. Verify RQ worker is processing:
# - Check worker service logs (Render, systemd, etc.)
# - Look for "Job ... started" / "Job ... finished" messages

# 4. Verify no job duplication:
# - In same organization, run same job multiple times (different queue entries)
# - Verify only one execution succeeds, others are skipped (if dedup active)
```

**Record:**
```
[ ] Job execution triggered: Confirmed
[ ] Job execution logged in DB: Confirmed
[ ] Job run row created with correct timestamps: Confirmed
[ ] Worker processed job without errors: Confirmed
[ ] No duplication detected: Confirmed
```

### 5.4 Monitoring Detection

**Evidence to Collect:**
- [ ] Operator can detect a forced failure via dashboard/logs
- [ ] Manual check command works: `python manage.py verify_audit_chain`

**Verification:**
```bash
# 1. Create a forced error (temporary):
# - Temporarily disable Redis connection
# - Or trigger a 500 error in application
# - Or kill a service instance

# 2. Verify detection:
# - Error appears in application logs within 60 seconds
# - 5xx rate increases on dashboard
# - Operator can read logs and diagnose issue

# 3. Manual audit check:
DJANGO_SETTINGS_MODULE=config.settings_production \
  python manage.py verify_audit_chain --all-organizations
# Expected: Shows any issues (or VALID if all good)

# 4. Restore and verify recovery:
# - Fix the error
# - Restart service or wait for auto-recovery
# - Verify no orphaned state
```

**Record:**
```
[ ] Forced error was detectable in logs: Confirmed
[ ] Dashboard showed elevated 5xx rate: Confirmed
[ ] Manual audit check command works: Confirmed
[ ] System recovered cleanly: Confirmed
```

### 5.5 Database Role Privileges

**Evidence to Collect:**
- [ ] Production DB role cannot disable triggers
- [ ] Production DB role cannot bypass audit immutability
- [ ] Test UPDATE on AuditLog fails (trigger rejects it)

**Verification:**
```bash
# Connect as production role (the role the application uses):
psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c "..."

# 1. Try to alter trigger (should fail):
psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c \
  "ALTER TABLE contracts_auditlog DISABLE TRIGGER contracts_auditlog_no_update;"
# Expected error: must be superuser to alter table

# 2. Try to change session_replication_role (should fail):
psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c \
  "SET session_replication_role = 'replica';"
# Expected error: permission denied / must be superuser

# 3. Try to UPDATE AuditLog (trigger should reject):
psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c \
  "INSERT INTO contracts_auditlog (action, model_name, object_id) VALUES ('TEST', 'Test', 1) RETURNING id;" \
  && psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c \
  "UPDATE contracts_auditlog SET action='MODIFIED' WHERE action='TEST';"
# Expected error: contracts_auditlog is append-only: UPDATE is not permitted

# 4. Verify INSERT is still allowed (append-only):
psql -h $DB_HOST -U $PROD_ROLE -d $DB_NAME -c \
  "INSERT INTO contracts_auditlog (action, model_name, object_id) VALUES ('APPEND_TEST', 'Test', 2);"
# Expected: INSERT succeeds
```

**Record:**
```
[ ] Production role cannot ALTER TRIGGER: Confirmed
[ ] Production role cannot SET session_replication_role: Confirmed
[ ] Trigger rejects UPDATE (audit immutability): Confirmed
[ ] Trigger rejects DELETE (audit immutability): Confirmed
[ ] Trigger allows INSERT (append-only permit): Confirmed
```

---

## SECTION 6: SIGN-OFF & GO/NO-GO DECISION

### 6.1 Sign-Off Roles

Required sign-offs from:
1. **Technical Owner** — infrastructure, deployments, rollback readiness
2. **Pilot Operator** — daily operations, runbook readiness, monitoring
3. **Security/Compliance Owner** (if applicable) — audit, MFA, data protection
4. **Product Owner** — feature scope, pilot cohort readiness

### 6.2 Sign-Off Checklist

**Technical Owner Sign-Off:**
```
Name: _______________________
Date: _______________________

I have verified:
[ ] PostgreSQL 14+ direct connection, no pooler
[ ] All 10 activation conditions are closed
[ ] Deployment successful; services healthy
[ ] Smoke tests 4.1-4.8 all passed
[ ] Backup/restore process tested
[ ] Audit trigger prevents UPDATE/DELETE at DB level
[ ] Production DB role cannot bypass immutability

Signature: _______________________
```

**Pilot Operator Sign-Off:**
```
Name: _______________________
Date: _______________________

I have verified:
[ ] Runbook reviewed and ready for daily operations
[ ] Monitoring dashboard set up and tested
[ ] I can execute rollback procedure
[ ] I have OPERATOR_ALERT_EMAIL configured
[ ] I understand MFA enrollment and recovery
[ ] I understand job failure alert response
[ ] I can verify audit chain integrity

Signature: _______________________
```

**Security/Compliance Owner Sign-Off (if required):**
```
Name: _______________________
Date: _______________________

I have verified:
[ ] MFA is required; bypass cannot occur
[ ] Audit metadata contains no secrets/tokens/passwords
[ ] Tenant isolation is enforced
[ ] DEBUG mode is disabled in production
[ ] HTTPS/secure cookies configured
[ ] Backup/restore preserves audit integrity

Signature: _______________________
```

**Product Owner Sign-Off:**
```
Name: _______________________
Date: _______________________

I have verified:
[ ] Pilot scope is correct (features enabled/disabled as planned)
[ ] Pilot cohort (organizations) is prepared
[ ] Users understand MFA enrollment requirement
[ ] Known limitations are documented

Signature: _______________________
```

### 6.3 Final Go/No-Go Decision

**Decision Template:**

```
╔════════════════════════════════════════════════════════════════╗
║                     PILOT ACTIVATION DECISION                 ║
╚════════════════════════════════════════════════════════════════╝

Date: _______________________
Decided By: _______________________

FINAL DECISION (choose one):

[ ] GO — Ready for pilot launch

[ ] CONDITIONAL GO — Ready with noted conditions below

[ ] NO-GO — Not ready; blockers documented below


IF CONDITIONAL GO:
───────────────────────────────────────────────────────────────
Condition #1:
  Description: _______________________________
  Owner: _______________________________
  Closure Evidence: _______________________________
  Target Date: _______________________________

(Repeat for each condition)


IF NO-GO:
───────────────────────────────────────────────────────────────
Blocker #1:
  Description: _______________________________
  Root Cause: _______________________________
  Remediation: _______________________________
  Target Resolution: _______________________________

(Repeat for each blocker)


SIGN-OFF:
───────────────────────────────────────────────────────────────
Technical Owner: _______________________ Date: _______
Pilot Operator: _______________________ Date: _______
Security Owner (if required): _______________________ Date: _______
Product Owner: _______________________ Date: _______

═══════════════════════════════════════════════════════════════════
```

---

## SECTION 7: PILOT LAUNCH HANDOFF

Upon GO or CONDITIONAL GO decision, transfer these artifacts to operations:

1. **Pilot Activation Report** (this document, fully completed)
2. **Production Environment Snapshot** (all env vars, feature flags, topology)
3. **Operations Runbook** (/docs/PILOT_OPERATIONS_RUNBOOK.md)
4. **Monitoring Dashboard** (screenshots + link)
5. **Backup/Restore Procedure** (pg_dump commands, storage location)
6. **Escalation Contact List** (phone, email, Slack channels)
7. **Known Limitations List** (scope document)
8. **Rollback Procedure** (step-by-step with decision tree)
9. **First 48-Hour Checklist** (daily health checks)
10. **Smoke Test Playbook** (reproducible test script)

---

**END OF PILOT ACTIVATION SPRINT**

This document is the operator's toolkit for executing the real pilot launch. No code changes needed. All work is configuration, verification, and operational readiness.

**Next Step:** Operators execute Section 2 (10 conditions), Section 3 (deployment), Section 4 (smoke tests), Section 5 (external deps), and Section 6 (sign-off). Return the completed sign-off template to proceed with GO decision.
