# Phase 5K Scope: Notification Delivery & Webhook Integration

**Status:** Ready to begin (Phase 5J approved 2026-06-23)  
**Approval Date:** 2026-06-23  
**MFA Verification:** ✅ COMPLETE — MFA infrastructure verified production-ready
**Notification Scope:** Product-approved  
**Key Clarification:** Phase 5K implements email communications ONLY; renewal/obligation/signature notifications deferred to Phase 5L

---

## Approved Mandatory Notifications

These notifications **must** be implemented before pilot launch:

### 1. Password Reset / Recovery ⏳ HIGH PRIORITY
- **Scope:** MANDATORY for all pilots
- **Requirement:** Users must be able to reset forgotten passwords
- **Current state:** Django password reset middleware available; email path not hardened
- **Phase 5K tasks:**
  1. Locate password reset email generation (likely in Django auth or custom backend)
  2. Replace any `request.build_absolute_uri()` calls with `build_canonical_url()`
  3. Add tests to verify:
     - URL uses APP_BASE_URL
     - No localhost URLs in production
     - No Host header injection possible
     - Token not leaked in audit logs
  4. Test end-to-end through Resend sandbox
  5. Verify authorization (only authenticated user can trigger reset)
- **Files to modify:** Password reset views, email templates
- **New files:** Tests for password reset canonical URLs
- **Estimated effort:** Medium (1-2 days)

### 2. MFA Communication Emails ⏳ HIGH PRIORITY
- **Scope:** MANDATORY for all pilots
- **Requirement:** Users must receive emails for MFA enrollment, verification, and recovery codes
- **Current state:** ✅ **MFA infrastructure verified production-ready** (see MFA_IMPLEMENTATION_AUDIT.md)
  - Password-login MFA flow: ✅ Fail-closed, no exception swallowing
  - MFA enrollment: ✅ Hash-based codes, 10-minute TTL
  - MFA challenge: ✅ OTP + recovery code fallback
  - Recovery codes: ✅ Consumed, audited, prevents replay
  - Session verification: ✅ Per-request middleware checks
  - Route exemptions: ✅ Exact match, fail-secure (Phase 4F hardened)
  - SAML integration: ✅ Assertion validation (signature, audience, issuer, freshness)
  - Tenant isolation: ✅ Verified (with note: user profiles shared across orgs acceptable for pilot)

**Phase 5K Email Communication Tasks (No Infrastructure Changes):**
  1. **MFA Enrollment Email** — Send when user initiates MFA setup:
     - Include 6-digit enrollment code (valid 10 minutes)
     - Subject: "Set up two-factor authentication"
     - Use `build_canonical_url()` for `/mfa/enroll/` link
  
  2. **MFA Verification Confirmation** — Send when enrollment completes:
     - Subject: "Two-factor authentication enabled"
     - Confirmation message (no codes/tokens in email body)
     - Security tips and next steps
  
  3. **MFA Challenge Email** — Send during login when MFA required:
     - Subject: "Your login verification code"
     - Include 6-digit OTP code (valid 10 minutes)
     - Include resend link and recovery code option (use `build_canonical_url()`)
  
  4. **MFA Recovery Codes Email** — Send when user generates backup codes:
     - Subject: "Your MFA recovery codes — Save these in a secure location"
     - Display 8 backup codes (clearly formatted, one per line)
     - Include expiration info and link to security settings (use `build_canonical_url()`)

- **Files to modify:** MFA email sending (likely in _send_mfa_email or signals)
- **New files:** MFA email service/templates, tests for canonical URLs
- **Estimated effort:** Low-Medium (1-2 days) — infrastructure already verified
- **Key Point:** This is email implementation ONLY; MFA infrastructure is production-ready and does NOT require changes

### 3. Operator Job Failure Alerts ⏳ HIGH PRIORITY
- **Scope:** MANDATORY before pilot launch
- **Requirement:** Operators must be notified when background jobs fail (expiration checks, renewal tasks, lifecycle transitions)
- **Current state:** Jobs have error handling; no operator notification implemented
- **Phase 5K tasks:**
  1. Identify all scheduled jobs (APScheduler, Celery, Django management commands)
  2. Add failure exception handlers to each job class/function
  3. Create job failure alert email sender:
     - Template with job name, error type, timestamp, action link
     - No stack trace, no secrets, safe error classification only
     - Link to operator dashboard (if available) using `build_canonical_url()`
  4. Add rate limiting to prevent email spam on repeated failures (e.g., 1 alert per job type per hour)
  5. Configure operator email address (environment variable or settings)
  6. Add audit logging for job failures
  7. Test via Resend sandbox
  8. Add monitoring dashboard (optional but recommended)
- **Files to modify:** Job definitions, error handlers
- **New files:** Job failure alert email service, tests
- **Estimated effort:** Medium-High (2-3 days)

### 4. Signature Request Notification ⏳ CONDITIONAL
- **Scope:** MANDATORY only if e-signature is pilot-enabled
- **Requirement:** Signers must receive email with signature request and link to accept/decline
- **Current state:** Signature request workflow exists (Phase 5F); email notification not yet implemented
- **Phase 5K tasks (if pilot-enabled):**
  1. Locate signature request creation flow
  2. Create signature request email template with:
     - Recipient name
     - Contract title/reference
     - Signer action (accept/decline/view)
     - Link using `build_canonical_url()` for signature URL
     - Action deadline
  3. Add signature request delivery service:
     - Use `build_canonical_url()` for all URLs
     - Include signer authorization in URL (not email context)
     - No sensitive contract data in email (just title/reference)
  4. Add tests:
     - URL uses canonical builder
     - No Host injection possible
     - Signer can only access their own signature requests
     - Cross-tenant isolation verified
  5. Test through Resend sandbox
- **Files to modify:** Signature request views, email templates
- **New files:** Signature request email service, tests
- **Condition:** Only implement if e-signature is in pilot scope
- **Estimated effort:** Medium (1-2 days, if enabled)

### 5. Renewal Reminder ⏳ CONDITIONAL
- **Scope:** MANDATORY only if renewal journey is pilot-enabled
- **Requirement:** Contract stakeholders receive reminder email before renewal deadline
- **Current state:** Renewal logic exists; email notification not yet implemented
- **Phase 5K tasks (if pilot-enabled):**
  1. Locate renewal scheduler/job
  2. Create renewal reminder email template with:
     - Contract title/reference
     - Current expiration date
     - Renewal action deadline
     - Link to renewal page using `build_canonical_url()`
  3. Schedule reminder timing (e.g., 30 days and 7 days before expiration)
  4. Add authorization checks (only contract stakeholders receive reminders)
  5. Add tests:
     - URL uses canonical builder
     - No Host injection possible
     - Only authorized users can access renewal link
     - Cross-tenant isolation verified
  6. Test through Resend sandbox
- **Files to modify:** Renewal scheduler, email templates
- **New files:** Renewal reminder service, tests
- **Condition:** Only implement if renewal journey is in pilot scope
- **Estimated effort:** Low-Medium (1 day, if enabled)

### 6. Obligation/Deadline Reminder ⏳ CONDITIONAL
- **Scope:** MANDATORY only if obligation tracking is pilot-enabled
- **Requirement:** Responsible parties receive reminder email before obligation deadline
- **Current state:** Obligation tracking exists; email notification not yet implemented
- **Phase 5K tasks (if pilot-enabled):**
  1. Locate obligation tracker and deadline scheduler
  2. Create obligation reminder email template with:
     - Obligation description
     - Deadline date
     - Responsible party
     - Action link using `build_canonical_url()`
  3. Schedule reminder timing (e.g., 7 days and 1 day before deadline)
  4. Add authorization checks (only responsible parties receive reminders)
  5. Add tests:
     - URL uses canonical builder
     - No Host injection possible
     - Only authorized users can access obligation link
     - Cross-tenant isolation verified
  6. Test through Resend sandbox
- **Files to modify:** Obligation tracker, email templates
- **New files:** Obligation reminder service, tests
- **Condition:** Only implement if obligation journey is in pilot scope
- **Estimated effort:** Low-Medium (1 day, if enabled)

---

## Phase 5K Implementation Requirements

### For ALL Notifications (3 mandatory + 3 conditional):

#### 1. Canonical URL Requirement (Phase 5J Hardening)
   - All email links must use `build_canonical_url()` from `contracts.services.url_builder`
   - No `request.build_absolute_uri()` calls anywhere
   - No hard-coded URLs
   - Test: Host header injection attempts must not influence generated URLs

#### 2. Security Requirements
   - **Authorization:** Only authenticated users can access links in emails
   - **Cross-tenant isolation:** Never leak other org data; user can't access other org links
   - **Error handling:** Safe classification only (no stack traces, secrets, or tokens in emails or logs)
   - **Audit logging:** Email delivery events logged with organization_id and safe error categories
   - **Session verification:** Links require valid authenticated session when accessed

#### 3. Test Requirements
   - **Canonical URL tests:** Verify `build_canonical_url()` used for all links
   - **Host injection tests:** Confirm malicious Host headers don't influence URLs
   - **Authorization tests:** Verify cross-tenant isolation, role-based access, session requirements
   - **End-to-end tests:** Verify email delivery through Resend sandbox (all paths)
   - **Production validation:** Verify no localhost URLs appear in production mode

#### 4. Email Template Standards
   - **Subject line:** Clear, descriptive action-oriented message
   - **Body:** Plain text + HTML variant (both versions tested)
   - **Action deadline:** Include expiration/urgency where relevant
   - **No secrets:** Never include codes, tokens, or sensitive data in email headers (body OK for codes)
   - **Codes in email body:** 6-digit MFA codes and recovery codes displayed prominently (email is secure channel)
   - **Footer:** Optional: help link, unsubscribe (if applicable)
   - **Branding:** "CLM One" only; no CMS Aegis legacy references

#### 5. Configuration & Deployment
   - **Environment variables:** Operator alert email address, reminder timings
   - **Resend integration:** SMTP credentials in render.yaml, from-address from DEFAULT_FROM_EMAIL
   - **Rate limiting:** Job failure alerts capped at 1 per job type per hour (prevent spam)
   - **Operator training:** Runbook documents alert monitoring, escalation procedures

#### 6. Documentation
   - **Email templates:** Subject, plain text body, HTML body (separate files)
   - **Service functions:** Parameters, return values, exception handling
   - **Test coverage report:** Which paths tested, which edge cases covered
   - **Configuration guide:** Environment variable setup, rate limiting, operator workflow

---

## Phase 5K Delivery Gates

### Before Merging Each Notification:

- [ ] Canonical URL builder usage verified (code review + tests)
- [ ] Authorization and isolation tests passing
- [ ] Resend sandbox delivery tested end-to-end
- [ ] No secrets in error messages or audit logs
- [ ] Production startup validation passes
- [ ] Full test suite passes (should be 1148+ tests)

### Before Pilot Launch:

- [ ] All 6 mandatory notifications (or conditional subset) implemented and tested
- [ ] Operator runbook complete with:
  - Alert email address configuration
  - Job failure alert monitoring instructions
  - Escalation procedures
- [ ] Bounce/complaint webhook configured (if available in Resend tier)
- [ ] Smoke test: create org, invite user, reset password, set up MFA (if enabled)
- [ ] Monitor logs for errors in first 24 hours of pilot

---

## Phase 5K Workplan Recommendations

### Phase 5K (Mandatory Notifications Only — Revised Estimates)

**Effort Reduction Reason:** MFA infrastructure already verified production-ready; Phase 5K focuses on email implementation, not infrastructure changes.

#### Week 1: Mandatory Notifications (3-4 days)

1. **Day 1: Password Recovery Email**
   - Implement password reset link email using `build_canonical_url()`
   - Template: subject, plain text, HTML
   - Tests: canonical URL, host injection, authorization, Resend sandbox
   - Effort: 1 day

2. **Day 1-2: MFA Communication Emails** (parallel with password recovery)
   - Implement 4 MFA emails (enrollment, verification, challenge, recovery codes)
   - Templates: subject, plain text, HTML for each
   - Verify integration with existing _send_mfa_email() function
   - Tests: canonical URLs, host injection, authorization, complete MFA flow
   - Effort: 1.5 days (infrastructure already verified)

3. **Day 3: Operator Job Failure Alerts**
   - Identify scheduled jobs (APScheduler, Celery, Django commands)
   - Add failure handlers with email notification
   - Template: job name, error type, timestamp, retry info
   - Rate limiting: 1 alert per job type per hour
   - Tests: job failure triggering, rate limiting, Resend sandbox
   - Effort: 1 day

4. **Day 4: Integration & Testing**
   - End-to-end testing through Resend sandbox (all paths)
   - Full test suite run (should be 1200+ tests)
   - Production validation (no localhost URLs)
   - Runbook documentation

#### Week 2: NOT IN PHASE 5K
- ❌ Renewal reminders (Phase 5L)
- ❌ Obligation reminders (Phase 5L)
- ❌ Signature notifications (Phase 5L)

**Total Phase 5K Effort:** 4-5 days (vs. 10-14 days if conditional notifications included)

### Operator Parallel Work (Product Side)

- [ ] Resend account promotion from sandbox
- [ ] DKIM/SPF/DMARC DNS configuration
- [ ] Operator alert email address setup
- [ ] APP_BASE_URL configuration for production
- [ ] MFA requirement toggled on (if pilot-enabling MFA)
- [ ] Password reset enabled (if pilot-enabling password recovery)

---

## Success Criteria for Phase 5K

✅ **Phase 5K is complete when (3 Mandatory Notifications Only):**

### Mandatory Notification Implementation
1. **Password Recovery Email** ✅ Complete
   - Password reset link uses `build_canonical_url()`
   - Templates: subject, plain text, HTML
   - Tests: canonical URL, host injection, authorization, Resend sandbox

2. **MFA Communication Emails** ✅ Complete
   - 4 emails: enrollment, verification, challenge, recovery codes
   - All links use `build_canonical_url()`
   - Templates: subject, plain text, HTML for each
   - Tests: canonical URLs, host injection, MFA flow integration, Resend sandbox

3. **Operator Job Failure Alerts** ✅ Complete
   - All scheduled jobs have failure handlers
   - Alert email uses canonical URLs for any action links
   - Rate limiting: 1 alert per job type per hour
   - Tests: job failure triggering, rate limiting, Resend sandbox

### Quality Gates (All Must Pass)
4. ✅ 1200+ tests passing (1148 existing + new email/job tests)
5. ✅ Full backend suite passes: `exit 0`
6. ✅ Resend sandbox delivery tested end-to-end for each notification type
7. ✅ No `request.build_absolute_uri()` in any email-generation code
8. ✅ No localhost URLs possible in production (production settings validation)
9. ✅ Authorization and cross-tenant isolation verified for all email paths

### Documentation & Readiness
10. ✅ Email templates documented (subject, body for each notification type)
11. ✅ Operator runbook complete and reviewed
12. ✅ Ready for Resend live promotion and pilot launch

### Explicitly NOT in Phase 5K
- ❌ Renewal reminder emails (Phase 5L)
- ❌ Obligation reminder emails (Phase 5L)
- ❌ Signature notification emails (Phase 5L)

---

## ❌ EXPLICITLY NOT IN PHASE 5K (Deferred to Phase 5L)

**Product Decision (2026-06-23):** The following notification emails are MANDATORY, but implementation is deferred to Phase 5L:

- ❌ **Renewal Reminder Emails** → Phase 5L
- ❌ **Obligation Deadline Reminder Emails** → Phase 5L  
- ❌ **Signature Request Notification Emails** → Phase 5L

**Rationale:** These notifications are conditional on journey enablement (renewal journey, obligation tracking, e-signature). Phase 5K focuses on core mandatory notifications (password recovery, MFA, job alerts). Phase 5L will implement conditional journeys after pilot feedback.

---

## Known Deferred (Post-Pilot)

- Signature request reminder emails (send reminders to slow signers)
- Contract expiration reminders (alternative to renewal)
- Contract archived/deleted notifications (silent operation for pilot)
- Document upload notifications (collaborator notifications deferred)
- Approval request/decision notifications (can use in-app notifications for pilot)
- Invoice/billing notifications (billing out of pilot scope)
- Bounce/complaint processing (Phase 5K if Resend tier supports; Phase 5L if advanced features needed)

---

## Approval & Sign-Off

**Product Scope Approved:** 2026-06-23
- ✅ Invitations (Phase 5J complete)
- ✅ Password recovery (mandatory)
- ✅ MFA communication (mandatory)
- ✅ Operator failure alerts (mandatory)
- ✅ Signature notifications (conditional on e-signature pilot)
- ✅ Renewal reminders (conditional on renewal pilot)
- ✅ Obligation reminders (conditional on obligation pilot)

**Phase 5J Status:** ✅ COMPLETE (1148 tests passing, canonical URL hardening verified)

**Phase 5K Status:** ⏳ READY TO BEGIN (approved scope document, requirements clear, implementation plan ready)

**Blocking Condition:** Do NOT begin Phase 5K until Phase 5J approval released.

**Next Step:** Begin Phase 5K implementation of mandatory and conditional notifications.
