# BATCH 5 POST-MIGRATION AUDIT

Date: 2026-05-19
Scope: All 10 Batch 5 templates (Steps 1–7)
Auditor: Automated + manual inspection pass
Reference: DESIGN_CONSTITUTION.md v1.1, DESIGN_ARCHETYPE_PATTERNS.md, DESIGN_ARCHETYPE_MAP.md

---

## Templates Audited

| Template | Assigned Archetype | Steps |
|---|---|---|
| `contracts/invoice_list.html` | QueuePage | Step 2 |
| `contracts/invoice_detail.html` | WorkspacePage | Step 2 |
| `contracts/invoice_form.html` | CommandPage | Step 2 |
| `contracts/retention_policy_list.html` | QueuePage | Step 4 |
| `contracts/retention_policy_form.html` | CommandPage | Step 4 |
| `settings_hub.html` | WorkspacePage | Step 6 Slice A |
| `contracts/organization_security_settings.html` | WorkspacePage | Step 6 Slice A |
| `contracts/organization_session_audit.html` | QueuePage | Step 6 Slice A |
| `contracts/organization_identity_settings.html` | WorkspacePage | Step 6 Slice A |
| `contracts/organization_activity.html` | QueuePage | Step 7 |

---

## Validation Results

### Template Parse

| Template | Result |
|---|---|
| `contracts/invoice_list.html` | ✅ OK |
| `contracts/invoice_detail.html` | ✅ OK |
| `contracts/invoice_form.html` | ✅ OK |
| `contracts/retention_policy_list.html` | ✅ OK |
| `contracts/retention_policy_form.html` | ✅ OK |
| `settings_hub.html` | ✅ OK |
| `contracts/organization_security_settings.html` | ✅ OK |
| `contracts/organization_session_audit.html` | ✅ OK |
| `contracts/organization_identity_settings.html` | ✅ OK |
| `contracts/organization_activity.html` | ✅ OK |

### Django System Check

```
System check identified no issues (0 silenced).
```

✅ Pass

### Test Suite

```
Ran 3 tests in 0.236s — OK
```

✅ Pass

---

## Archetype Compliance

### invoice_list.html — QueuePage ✅

- `page-wrap` ✅
- `page-header` / `page-title` / `page-subtitle` / `page-actions` ✅
- `panel` / `tbl-head` / `tbl-th` / `tbl-row` / `tbl-td` ✅
- `badge-sm` invoice status badges ✅
- `btn-primary-grad` / `btn-ghost` ✅
- `empty-state` ✅
- No CSRF (read-only list) ✅

### invoice_detail.html — WorkspacePage ✅

- `page-wrap` ✅
- `page-header` / `page-title` / `page-subtitle` / `page-actions` ✅
- `panel` / `panel-inner` / `panel-head` / `panel-title` ✅
- `badge-sm` invoice status ✅
- `c-success` on paid amounts ✅ (Step 3 token applied)
- `c-muted` / `c-danger` / `c-warning` ✅
- No CSRF (read-only detail) ✅

### invoice_form.html — CommandPage ✅

- `page-wrap` ✅
- `page-header` / `page-title` ✅
- `panel` / `panel-inner` ✅
- `form-label` ✅
- `btn-primary-grad` (submit) / `btn-ghost` (cancel) ✅
- CSRF token present ✅
- Exception: `grid grid-cols-1 md:grid-cols-2 gap-4` — documented structural responsive grid (see Exceptions section)

### retention_policy_list.html — QueuePage ✅

- `page-wrap` ✅
- `page-header` / `page-title` / `page-subtitle` / `page-actions` ✅
- `panel` / `tbl-head` / `tbl-th` / `tbl-row` / `tbl-td` ✅
- `badge-sm` status badges ✅
- `btn-primary-grad` / `btn-ghost` ✅
- `empty-state` ✅

### retention_policy_form.html — CommandPage ✅

- `page-wrap` ✅
- `page-header` / `page-title` ✅
- `panel` / `panel-inner` ✅
- `form-label` ✅
- `btn-primary-grad` (submit) / `btn-ghost` (cancel) ✅
- CSRF token present ✅

### settings_hub.html — WorkspacePage ✅

- `page-wrap` ✅ (was `page-container`)
- `page-header` / `page-title` / `page-subtitle` / `page-actions` ✅
- Settings-block primitives: `settings-grid`, `settings-card`, `heading-xl`, `text-subtitle` ✅
- No forms / no CSRF needed ✅

### organization_security_settings.html — WorkspacePage ✅

- `page-wrap` ✅
- `heading-xl` / `text-subtitle` (settings heading primitives) ✅
- `badge-sm` MFA status ✅ (was `ds-badge`)
- `btn-primary-grad` (save) / `btn-ghost` (revoke sessions) ✅
- `form-grid` / `form-field` / `form-label` ✅
- `input-base w-180 px-3 py-2 rounded-lg border` on timeout field — documented exception (see below)
- 2 CSRF tokens ✅
- Destructive guard: `onsubmit="return confirm('Revoke sessions for all active organization members?')"` ✅ preserved

### organization_session_audit.html — QueuePage ✅

- `page-wrap` ✅
- `heading-xl` / `text-subtitle` ✅
- `table-wrapper` / `table-base` / `table-head-row` / `table-body-row` / `table-cell-pad` / `table-cell-primary` (settings-block table primitives) ✅
- `panel-item` replacing raw border div ✅
- `btn-ghost` ✅
- CSRF token ✅
- Destructive guard: `onsubmit="return confirm('Revoke this session now?')"` ✅ preserved

### organization_identity_settings.html — WorkspacePage ⚠️ (documented exception)

- `page-max-w` instead of `page-wrap` — documented exception (see below) ⚠️
- `heading-xl` / `text-subtitle` / `heading-lg` / `text-desc-sm` ✅
- `section-grid` / `settings-card-lg` / `form-grid` / `form-field` / `form-label` ✅
- `code-label` / `code-block` ✅
- `btn-primary-grad` (save) / `btn-ghost` (rotate token buttons) ✅
- 3 CSRF tokens ✅
- 2 destructive guards: SCIM token rotation + API token rotation ✅ preserved

### organization_activity.html — QueuePage ✅

- `page-wrap` ✅
- `page-header` / `page-title` / `page-subtitle` / `page-actions` ✅
- `panel` / `tbl-head` / `tbl-th` / `tbl-row` / `tbl-td` / `c-muted` ✅
- `badge-sm badge-{green,blue,red,yellow,gray}` per action ✅
- `select-base` / `input-base` with `sr-only` accessible labels ✅
- `btn-primary-grad` / `btn-ghost` ✅
- `empty-state` ✅
- `nav[aria-label="Pagination"]` ✅
- GET filter form (no CSRF needed) ✅
- `onchange="this.form.submit()"` preserved ✅

---

## Inline Style Scan

| Template | Inline styles | Result |
|---|---|---|
| All 10 templates | 0 | ✅ Clean |

---

## Inline Handler Review

| Template | Handler | Count | Classification |
|---|---|---|---|
| `organization_security_settings.html` | `onsubmit="return confirm(...)"` | 1 | ✅ Acceptable — intentional destructive guard |
| `organization_session_audit.html` | `onsubmit="return confirm(...)"` | 1 | ✅ Acceptable — intentional destructive guard |
| `organization_identity_settings.html` | `onsubmit="return confirm(...)"` | 2 | ✅ Acceptable — intentional destructive guards |
| `organization_activity.html` | `onchange="this.form.submit()"` | 2 | ✅ Acceptable — progressive enhancement filter |

**Total acceptable inline handlers: 6**
**Handlers needing JS migration: 0**
**Handlers deferred for safety: 0**

All inline handlers are pre-existing intentional patterns. No new inline handlers were introduced.

---

## Retired / Undefined Class Scan

| Class | Templates | Result |
|---|---|---|
| `action-chip` | 0 | ✅ Fully retired |
| `btn-secondary` | 0 | ✅ Fully replaced |
| `btn-primary` (bare) | 0 | ✅ Fully replaced |
| `ds-badge` | 0 | ✅ Fully replaced |
| `checkbox-primary` | 0 | ✅ Fully removed |
| `page-container` | 0 | ✅ Fully replaced |
| `bg-gray-*` / `text-gray-*` color utilities | 0 | ✅ Clean |
| `bg-blue-*` / `text-blue-*` color utilities | 0 | ✅ Clean |
| `bg-green-*` / `text-green-*` color utilities | 0 | ✅ Clean |
| `bg-red-*` / `text-red-*` color utilities | 0 | ✅ Clean |
| `text-green-600` | 0 | ✅ Replaced by `c-success` (Step 3) |

---

## Undocumented Primitive Scan

Remaining non-canonical classes found in Batch 5 templates are exclusively standard Tailwind structural utilities with no color or brand semantic meaning:

| Class | Template | Classification |
|---|---|---|
| `p-4` | `invoice_list.html` | Structural Tailwind — acceptable |
| `text-left` | `invoice_list.html`, `organization_activity.html` | Structural Tailwind — acceptable |
| `text-right` | `invoice_list.html`, `retention_policy_list.html` | Structural Tailwind — acceptable |
| `pt-2` | `invoice_detail.html` | Structural Tailwind — acceptable |
| `pt-4` | `invoice_form.html` | Structural Tailwind — acceptable |

**Verdict: No undocumented custom primitives introduced in Batch 5.**

---

## Behavior-Sensitive Element Review

### Forms and CSRF

| Template | Forms | CSRF | POST Actions |
|---|---|---|---|
| `invoice_form.html` | 1 | ✅ 1 | Create/Update invoice |
| `retention_policy_form.html` | 1 | ✅ 1 | Create/Update retention policy |
| `organization_security_settings.html` | 2 | ✅ 2 | Save MFA policy; Revoke all sessions |
| `organization_session_audit.html` | 1/row | ✅ per form | Revoke individual session |
| `organization_identity_settings.html` | 3 | ✅ 3 | Save IdP settings; Rotate SCIM token; Rotate API token |

All CSRF tokens preserved across all forms. ✅

### Destructive Guards

| Template | Guard text | Status |
|---|---|---|
| `organization_security_settings.html` | `Revoke sessions for all active organization members?` | ✅ Preserved |
| `organization_session_audit.html` | `Revoke this session now?` | ✅ Preserved |
| `organization_identity_settings.html` | `Rotate the SCIM token? This will invalidate the existing token.` | ✅ Preserved |
| `organization_identity_settings.html` | `Rotate the API token? This will invalidate the existing token value.` | ✅ Preserved |

### Filters and Pagination

| Template | Filters | Pagination | Status |
|---|---|---|---|
| `organization_activity.html` | action, model, start_date, end_date | ✅ is_paginated / page_obj | ✅ Preserved |
| `invoice_list.html` | status filter | — | ✅ Preserved |
| `retention_policy_list.html` | — | — | ✅ Preserved |

### Permission and Conditional Logic

All `{% if perms.* %}`, `{% if is_owner %}`, `{% if user.* %}` conditionals preserved across all templates. No permission gates were added or removed.

---

## Documented Exceptions Review

### Exception 1: `page-max-w` in organization_identity_settings.html

- **What:** Uses `page-max-w` (980px settings-specific max-width) instead of `page-wrap` (1400px standard max-width).
- **Why:** Identity settings use a narrower content width appropriate for a settings form. The settings-specific design system intentionally limits width for readability of dense configuration forms.
- **Decision: KEEP DOCUMENTED** — no migration needed. `page-max-w` is defined in base.html and is a legitimate settings-context wrapper.

### Exception 2: `input-base w-180 px-3 py-2 rounded-lg border` in organization_security_settings.html

- **What:** The session timeout input uses `input-base` alongside structural Tailwind padding/radius classes.
- **Why:** `input-base` in the settings block provides theming (bg/border color tokens) only. Structural classes (`px-3 py-2 rounded-lg`) are needed for proper sizing. `w-180` is a settings-block fixed width defined in base.html.
- **Decision: KEEP DOCUMENTED** — pattern is already used in settings pages and is safe.

### Exception 3: `onsubmit="return confirm(...)"` destructive guards (4 instances)

- **What:** Inline `onsubmit` confirm dialogs on destructive action forms in settings templates.
- **Why:** These are intentional UX safety guards for irreversible actions (revoking sessions, rotating tokens). The JS is minimal and semantically appropriate.
- **Decision: KEEP AS ACCEPTABLE** — do not migrate to external JS bindings at this time. These are stable patterns that should not be touched without a dedicated UX/accessibility pass.

### Exception 4: `onchange="this.form.submit()"` filter handlers in organization_activity.html (2 instances)

- **What:** Filter selects auto-submit on change.
- **Why:** Standard Django filter pattern providing progressive enhancement. Works without JS (manual submit button still present).
- **Decision: KEEP AS ACCEPTABLE**

### Exception 5: `grid grid-cols-1 md:grid-cols-2 gap-4` in invoice_form.html

- **What:** Responsive grid layout for form fields.
- **Why:** Two-column form layout at medium+ viewports. No canonical replacement exists — responsive grid guidance documents this as a structural exception per DESIGN_CONSTITUTION.md §12.
- **Decision: KEEP DOCUMENTED** — structural Tailwind grid; not a design token violation.

### Exception 6: Settings heading classes (`heading-xl`, `heading-lg`, `text-subtitle`, `text-desc-sm`)

- **What:** Settings pages use their own heading hierarchy defined in base.html (lines 727–771) rather than `page-title`/`page-subtitle`.
- **Why:** Settings pages have a distinct visual sub-system with tighter typographic hierarchy. These classes are all defined in base.html.
- **Decision: KEEP DOCUMENTED** — settings heading system is canonical for settings context.

---

## Security-Sensitive Risk Assessment

| Template | Sensitivity | Risk | Notes |
|---|---|---|---|
| `organization_security_settings.html` | HIGH | ✅ Controlled | MFA policy form + session revocation. All guards preserved. No JS changes. |
| `organization_identity_settings.html` | HIGH | ✅ Controlled | SAML/SCIM/API token management. Rotation confirmations preserved. CSRF×3 intact. |
| `organization_session_audit.html` | HIGH | ✅ Controlled | Per-session revoke. CSRF intact. Confirm guard preserved. |
| All other templates | LOW–MEDIUM | ✅ Low | No security-sensitive operations |

---

## Remaining High-Risk Templates Assessment

### organization_team.html — Defer

| Factor | Detail |
|---|---|
| Lines | 150 |
| Raw Tailwind density | 45 bg-/text- hits |
| Forms | 7 forms, multiple POST routes |
| Routes | `update_membership_role`, `revoke_member_sessions`, `deactivate_organization_member`, `reactivate_organization_member`, `resend_organization_invite`, `revoke_organization_invite` |
| Destructive actions | 2 (Revoke Sessions button, Revoke Invite button) — no confirm guards currently present |
| Special logic | `{% if membership.role == 'OWNER' and not is_owner %}disabled{% endif %}` on role select/save |
| CSRF | Multiple per-row forms, each requiring individual CSRF tokens |
| **Verdict** | **DEFER** — high form density, destructive actions without confirm guards, owner-gating logic. Safe to migrate in Batch 6 with careful review. |

### profile.html — Defer Indefinitely

| Factor | Detail |
|---|---|
| Lines | 65 |
| Raw Tailwind density | 25 bg-/text- hits |
| Forms | 1 form, 3 named submit actions: `update_profile`, `send_mfa_code`, `generate_mfa_recovery_codes` |
| MFA gates | `{% if mfa_required and not profile.mfa_enabled %}`, `{% if mfa_admin_user %}` |
| MFA fields | `mfa_enrollment_code`, `mfa_recovery_code` — special rendering logic |
| Destructive risk | MFA enrollment state change; recovery code generation |
| **Verdict** | **DEFER INDEFINITELY** — MFA enrollment flow. Any visual change risks breaking the MFA gate. Requires dedicated MFA-aware review pass before migration. |

---

## Batch 5 Consistency Verdict

**✅ PASS**

All 10 Batch 5 templates:
- Follow their assigned archetypes
- Contain no retired, undefined, or undocumented custom classes
- Contain no inline styles
- Contain no new inline event handlers beyond pre-existing acceptable patterns
- Preserve all forms, CSRF tokens, POST actions, destructive guards, filters, pagination, context variables, and permission logic
- Are consistent with DESIGN_CONSTITUTION.md v1.1

---

## Regression Verdict

**✅ No regressions detected.**

- Template parse: 10/10 ✅
- manage.py check: 0 issues ✅
- Test suite: 3/3 ✅
- All behavior-sensitive elements verified intact
- No security guards removed or weakened

---

## Exception Decision Table

| Exception | Location | Decision | Rationale |
|---|---|---|---|
| `page-max-w` instead of `page-wrap` | `organization_identity_settings.html` | **Keep documented** | Narrower settings width is intentional |
| `input-base w-180 px-3 py-2 rounded-lg border` | `organization_security_settings.html` | **Keep documented** | Structural classes alongside theming token are acceptable |
| `onsubmit="return confirm(...)"` × 4 | 3 settings templates | **Keep as acceptable** | Intentional destructive guards; do not touch |
| `onchange="this.form.submit()"` × 2 | `organization_activity.html` | **Keep as acceptable** | Progressive enhancement filter; stable pattern |
| `grid grid-cols-1 md:grid-cols-2 gap-4` | `invoice_form.html` | **Keep documented** | Structural responsive grid; §12 exception |
| Settings heading classes | 3 settings templates | **Keep documented** | Defined in base.html settings block |

---

## Token / Primitive Gaps Discovered

None new in Batch 5. All gaps identified in Batch 4 audit were resolved in Batch 5 Step 1:
- `status-dot` ✅ documented
- `pre-output` ✅ documented + applied
- `panel-item` ✅ documented + applied
- `c-success` ✅ added + applied
- Responsive grid guidance ✅ documented
- Chart container a11y guidance ✅ documented
- `aria-live` guidance ✅ documented

---

## Accessibility Gaps

| Gap | Templates | Risk | Status |
|---|---|---|---|
| Organization team destructive buttons lack confirm guards | `organization_team.html` | Medium | Deferred with template |
| Chart containers (reports/identity dashboards) | Batch 4 templates | Low | Documented, deferred |
| Profile MFA flow `sr-only` labels | `profile.html` | Low | Deferred with template |

---

## Recommended Batch 6 Scope

### High Priority
- `organization_team.html` — WorkspacePage migration (HIGH risk, schedule for Batch 6 Step 1 with dedicated review)

### Medium Priority (NetworkPage wave)
- `client_list.html` — NetworkPage
- `client_detail.html` — NetworkPage
- `client_form.html` — NetworkPage

### Lower Priority
- `budget_detail.html` — WorkspacePage
- `clause_template_detail.html` — WorkspacePage
- `legal_task_board.html` — BoardView / WorkspacePage

### Defer
- `profile.html` — MFA-critical, defer indefinitely
- Shell templates (`base.html`, `base_fullscreen.html`, `base_redesign.html`) — architectural decision needed

---

## Status

**Batch 5 audit complete. All 10 templates pass. Zero regressions. Zero security risks introduced.**

**organization_team.html can begin in Batch 6 with dedicated review.**
**profile.html remains deferred indefinitely.**
