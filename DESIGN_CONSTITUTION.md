# DESIGN CONSTITUTION - CMS Aegis

> **HISTORICAL — SUPERSEDED**
>
> Superseded by [`GOVERNANCE_CHARTER.md`](GOVERNANCE_CHARTER.md) on 2026-07-20
> per [ADR-0009](docs/adr/0009-governance-charter-supersession.md).
>
> Retained for traceability only. **Do not implement** requirements from this
> file when they conflict with the current CLM One Governance Charter.

Version: 1.5
Status: Historical (superseded)
Last amended: 2026-07-07 (§15 — Pipeline Governance: single-PR rule for token+template changes, exceptions convention)
Purpose: enforce one coherent enterprise-grade product language across all pages

## 1) Non-Negotiable Principles

1. Consistency over novelty.
2. Semantic components over ad-hoc utility combinations.
3. Accessibility and clarity are product requirements.
4. State communication must be explicit and predictable.
5. New UI patterns require standardization before reuse.

## 2) Layout and Spacing Rules

Spacing scale:

- Base spacing tokens: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Do not introduce one-off spacing values unless added to tokens.

Page rhythm:

- Standard page container width and horizontal padding defined by shell.
- Header-to-content spacing is fixed by page type (dashboard/list/detail/form).
- Components must align to shared grid and vertical rhythm.

Density modes:

- Use only two density modes: relaxed and compact.
- Density is selected per page type, not per component instance.

## 3) Typography Hierarchy

Heading levels:

- H1: page title only.
- H2: primary section headers.
- H3: subsection headers.
- No decorative heading size jumps.

Body text:

- Use standard body and secondary body styles only.
- Avoid arbitrary text-size combinations inside the same component type.

Metadata text:

- Labels, helper text, and timestamps use canonical metadata styles.

## 4) Color and Token Rules

Token authority:

- Color, spacing, radius, shadows, and transitions come from shared tokens.
- Hardcoded hex values are not allowed in templates except approved temporary migration notes.

Semantic color usage:

- Primary: primary actions and selected key affordances.
- Neutral: default surfaces and secondary actions.
- Success/warning/error/info: status only, not decorative emphasis.

Theme parity:

- Light and dark variants must both be defined for every semantic component state.

## 5) Component Rules

Buttons:

- Allowed variants: primary, secondary, ghost, soft-primary, danger, link.
- Allowed sizes: sm, md, lg.
- Every button variant must define default, hover, active, focus, disabled, loading.
- Class map: `btn-primary-grad` (primary), `btn-ghost` (ghost/secondary), `btn-soft-primary` (soft-primary), `btn-primary-sm` (primary small).

Retired button-adjacent classes:

- `action-chip` — retired 2026-05-18. Was used only in `dashboard.html` (3 instances) for co-equal page-header quick actions. Defined in `base.html` but never documented, lacked focus/active/disabled states. Replacement: use `btn-ghost` for co-equal multi-action page header clusters. Remove `action-chip` CSS from `base.html` after `dashboard.html` migration is complete.
- Rule: multiple co-equal actions in `.page-actions` use `btn-ghost`. One primary action uses `btn-primary-grad`. One mid-weight action uses `btn-soft-primary`.

Cards/Panels:

- One card shell style per density mode.
- Card headers and body spacing must use shared slots.
- Avoid custom border/radius/shadow per page.

Tables:

- One canonical table scaffold with optional compact mode.
- Required behavior: row hover, clear selected state, sortable header affordance style.
- Actions column alignment and width must be standardized.

Row state tints:

- Semantic row-state classes are token-backed. Do not use raw Tailwind background utilities for row state.
- Canonical row-state classes: `row-unread` (unread notification/message), `row-overdue` (deadline or SLA breach), `row-expiring` (approaching expiry — border accent).
- CSS variables: `--row-unread-bg`, `--row-overdue-bg`. Both are defined for dark and light themes in `base.html`.
- Dark theme values: `rgba(37,99,235,0.08)` (unread), `rgba(239,68,68,0.08)` (overdue).
- Light theme values: `#EFF6FF` (unread), `#FEF2F2` (overdue).
- Do not use `bg-blue-50`, `bg-red-50`, or other raw color utilities for row-state tinting. Added: 2026-05-18.

Semantic text color utilities:

- Do not use raw `style="color:..."` inline overrides. Use canonical text color classes.
- Canonical text color classes (all defined in `base.html`):
  - `c-primary` — primary text (maps to `--text-primary`)
  - `c-muted` — secondary/muted text (maps to `--text-muted`)
  - `c-danger` — error/critical emphasis (`#F87171`, red-400)
  - `c-warning` — warning/amber emphasis (`#F59E0B`, amber-500) — Added: 2026-05-18
  - `c-info` — informational/blue emphasis (`#60A5FA`, blue-400) — Added: 2026-05-18
  - `c-success` — positive/paid/success emphasis (`#16A34A`, green-700) — Added: 2026-05-18
  - `c-success-soft` — positive/green soft emphasis (`#86EFAC`, green-300)
  - `c-primary-brand` — brand accent color (maps to `--primary`)
- Use these classes instead of raw `text-*` Tailwind utilities for semantic meaning.

Forms:

- Required structure: label, control, helper text, error text.
- Required states: default, focus, disabled, error, read-only.
- Do not embed raw utility style strings in Python form constants long-term.

Modals/Drawers:

- Standard size tiers and spacing.
- Standard close behavior (escape, click outside if allowed, explicit close control).
- Focus trap required for accessibility.

Navigation:

- Primary nav, contextual nav, and tab navigation have separate canonical patterns.
- Do not invent custom tab pills without updating design primitives.

Board/Kanban surfaces (WorkspacePage/BoardView subvariant):

- Governed via three dedicated primitives: `board-track`, `board-col`, `board-card`.
- Board columns use `badge-sm` for item counts. Card priority/status use `badge-sm` semantic variants.
- Card actions use canonical link style (`c-link`) or `btn-ghost`. No inline `onclick` handlers.
- Keyboard navigation: every interactive card control must be focusable and operable via keyboard.
- ARIA: each column must have `role="region"` and `aria-label`. Each card must have `role="article"`.
- Mobile: `board-track` uses `overflow-x: auto` for horizontal scroll. Column width is fixed.
- When not to use: do not use `board-*` primitives for non-status-column layouts. Queue/list views use QueuePage table primitives instead.
- CSS to add to `base.html` when first board page is migrated:
  - `.board-track { display: flex; gap: 16px; overflow-x: auto; padding-bottom: 8px; }`
  - `.board-col { width: 320px; flex-shrink: 0; background: var(--surface); border-radius: 10px; padding: 16px; }`
  - `.board-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 16px; transition: box-shadow 0.15s; }`
  - `.board-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); }`
  - `.board-col-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }`



Loading:

- Every async region must expose loading with skeleton or spinner and label.

Empty:

- Every list/dashboard panel must define empty state with title + explanation + next action.

Error:

- Error state must include human-readable summary and next-step guidance.

Success:

- Success feedback is concise and non-blocking unless user confirmation is required.

Permission/No-access:

- Distinct from generic error; must explain missing permission path.

## 7) Messaging and Tone

Tone:

- Professional, concise, operationally clear.
- Avoid decorative marketing tone in authenticated app surfaces.

Microcopy:

- Use action-oriented labels and explicit outcomes.
- Avoid ambiguous status text.

## 8) Accessibility Minimums

- Visible keyboard focus for all interactive controls.
- Semantic labels for all inputs and icon-only actions.
- Sufficient contrast for text and status indicators.
- Keyboard-reachable primary workflows.
- Motion respects reduced-motion preference.

## 9) Implementation Governance

Forbidden in new/updated pages:

- New inline style blocks in templates.
- New inline event handlers (onclick/onmouseover/onmouseout/onchange).
- New one-off component variants without design-system update.

Required in pull requests touching UI:

- Identify reused canonical primitives.
- Confirm state coverage (loading/empty/error/success).
- Confirm accessibility checks for changed controls.
- Include before/after screenshots for high-impact views.

## 10) Change Control

- Any new primitive must be proposed with:

  - intended use cases,
  - states,
  - accessibility behavior,
  - migration plan for overlaps.

- Constitution updates require explicit approval and version bump.

## 11) Definition of Done for UI Work

A UI task is not done unless:

1. It uses canonical primitives.
2. It satisfies state standards.
3. It passes accessibility minimums.
4. It avoids banned implementation patterns.
5. It preserves coherence with shell and token system.

---

## 12) Batch 5 Primitives (added 2026-05-18)

### status-dot

Already defined in `base.html`. Use `<span class="status-dot {color}" aria-hidden="true"></span>` for inline colored circular indicators.

Colors: `green`, `blue`, `yellow`, `red`, `gray`.

- Always add `aria-hidden="true"` — color alone never conveys state; pair with visible text or `sr-only` label.
- `status-dot.yellow` = amber/warning indicator (replaces raw `bg-yellow-400 w-2 h-2 rounded-full`).
- Do not use raw `bg-{color}-{n} rounded-full` for status dots; use `status-dot {color}` instead.

### pre-output

For AI/LLM/code output areas rendered in `<pre>` elements.

```html
<pre class="pre-output c-muted" aria-live="polite" aria-label="[descriptive label]">…</pre>
```

- Uses `var(--surface)` background and `var(--card-border)` border — fully token-backed.
- Always add `aria-live="polite"` when content is dynamically injected (screen readers will announce new content).
- Always add `aria-label` describing what the output area contains.
- May be combined with `hidden` class — the `aria-live` region is still registered by screen readers before content arrives.
- Do not use raw `bg-gray-50 border border-gray-200 rounded-lg text-xs whitespace-pre-wrap`; use `pre-output` instead.

### panel-item

For list items rendered inside `panel-inner` — sub-cards or preset rows within a panel.

```html
<div class="panel-item">
  <div>…content…</div>
  <div>…actions…</div>
</div>
```

- Horizontal flex, `space-between`, `8px 12px` padding, token-backed border and radius.
- Use inside `panel-inner` to group an item's content and trailing action.
- Do not use raw `flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-3 py-2`; use `panel-item` instead.

### Responsive Grid Guidance

`dash-grid` is a fixed 3-column grid with no breakpoints. For layouts requiring responsive columns:

- Accepted pattern: raw Tailwind responsive grid utilities (`grid grid-cols-1 md:grid-cols-3`, `lg:grid-cols-[2fr_1fr]`, etc.).
- These are **documented structural exceptions** — not design token violations.
- Do not introduce new ad-hoc breakpoint patterns without noting them as exceptions.
- A `dash-grid--responsive` variant is deferred to a future design system release.

### Chart Container Accessibility

For JS-rendered chart containers (bar charts, ring charts, etc.):

```html
<div id="chart-id"
     class="…"
     role="img"
     aria-label="[Descriptive label including chart type and data range]">
</div>
```

- Add `role="img"` and `aria-label` to the chart container `<div>`.
- The label should describe: chart type, metric shown, and time/data range if applicable.
- Example: `aria-label="Monthly billing bar chart, last 6 months"`.
- JavaScript className strings (e.g., `element.className = 'text-gray-500'`) are exempt from canonical class rules — CSS classes cannot be referenced in JS strings without a build pipeline.

## 13) Ironclad Audit Amendments (added 2026-07-04, v1.2)

Rationale and source findings: `IRONCLAD_DESIGN_AUDIT.md`.

### Status badges are pills with canonical mapping

- `badge-sm` is fully rounded (`border-radius: 9999px`). Tinted background +
  same-hue text in both themes (unchanged).
- Status→color mapping is code, not template markup. Templates MUST use the
  `status_badge_class` / `phase_badge_class` filters from `clmone_format`:
  `<span class="badge-sm {{ contract.status|status_badge_class }}">`.
  Hand-rolled `{% if status == … %}badge-…{% endif %}` chains are retired — they
  caused 5 of 9 statuses to silently render gray.
- Every enum value must have a mapping entry. Semantics: green = healthy or
  terminal-good, yellow = waiting on someone, blue = in-flight process,
  red = expired/terminated, gray = neutral/inert. Color is semantic, never
  decorative.

### Lifecycle stepper primitive (`lc-*`)

- Detail pages show lifecycle as a stepper driven by `contract.lifecycle_stage`
  via the `{% lifecycle_steps contract %}` tag — never a hardcoded badge chain.
- Compact headers show **record status · workflow stage** (e.g. `In progress · Drafting`).
  Never label the record status “Draft”; drafting is a stage only. See
  `docs/glossary-lifecycle-dimensions.md` and PDR 0002.
- Classes: `lc-track` (container, `role="list"`), `lc-step` + state modifier
  (`lc-done`, `lc-current`, `lc-upcoming`), `lc-dot`, `lc-label`.
- The current step carries `aria-current="step"`; the track carries an
  `aria-label` naming the current stage. Dots are `aria-hidden`.

### Decoration reduction (color = meaning)

- Background orbs and scanline overlays are retired from the app shell.
- `status-dot` variants no longer carry glow `box-shadow`s.
- Do not add glows, decorative gradients, or ambient color washes to
  authenticated app surfaces. Marketing/landing surfaces are exempt.
- Duplicate KPI strips on a single page are a defect: one metric renders once.

## 14) Token Authority — "Ledger" Design Language (added 2026-07-05, v1.3)

- `theme/static/css/clmone-tokens.css` is the canonical token layer;
  `CLMONE_DESIGN_SYSTEM.md` is the spec and rationale. Both derive from the
  approved brand board (`clmone_agent_brand_kit/docs/`).
- New/updated UI must consume `--ink-*`, `--seal-*`, `--status-*`, `--paper/--card/
  --well`, `--line/--hairline` tokens. The legacy `--primary #2563EB` / `--accent
  #22C55E` values and raw Tailwind palette literals are deprecated: do not introduce
  new usages; migrate on touch.
- Product typeface is Inter only (weights 400–650). Manrope and Sora are retired;
  remove on touch.
- The product is light-first; dark theme derives from the same tokens ("navy night").
- Fiduciary surfaces (anything displaying or moving client funds) must use the
  fiduciary grammar of CLMONE_DESIGN_SYSTEM.md §5: seal-wash background, seal top
  rule, mono eyebrow. Money values are always tabular-numeral and right-aligned;
  totals carry ledger rules.

### aria-live Guidance

Dynamic output regions (AI assistant, search results loaded asynchronously, status messages) must include:

- `aria-live="polite"` for non-urgent updates (AI output, background loading)
- `aria-live="assertive"` only for critical errors that interrupt workflow
- The `aria-live` region must exist in the DOM before content is injected (not created dynamically)

## 15) Pipeline Governance (added 2026-07-07, v1.5)

### Single-PR rule for Ledger token changes

- Any change to a token in `theme/static/css/clmone-tokens.css` must ship in the
  same pull request as the Django template changes that consume it. Token edits
  and their consuming markup are never split across separate PRs — a token
  landing without its consumer (or vice versa) is a review-blocking defect,
  since it leaves deployed styles and token values out of sync for the window
  between merges.
- This is a review criterion enforced at pull-request review time. There is no
  automated CI check for this yet — do not describe this rule as CI-enforced
  until a lint/grep step actually exists in the test suite.

### Exceptions convention

Temporary deviations from a Ledger rule (e.g., a raw hex value used under
engineering urgency, a one-off spacing value, a component variant that hasn't
been standardized yet) are permitted only if logged in the table below —
never hardcoded silently into a template.

| Location (file:line) | Rule bypassed | Reason | Ticket | Expiry |
|---|---|---|---|---|
| _(none currently logged)_ | | | | |

- Every row requires a ticket reference and a hard expiry date. An exception
  past its expiry date is a defect, not a grandfathered pattern — it must be
  resolved (migrated to a token/primitive) or the exception renewed with a new
  ticket and date, not left in place silently.
- This table lives in this document, not scattered as inline comments, so a
  reviewer can audit all outstanding exceptions in one place.

### Aspirational vs. actual enforcement

- Rules in this document describe **mandatory pull-request review criteria**
  unless explicitly stated otherwise. None of the rules above are currently
  backed by an automated CI gate (no linter or grep step rejects raw hex
  values or non-CTA copper usage today).
- If automated enforcement is added later, this section must be updated to
  name the specific check and where it runs — do not leave enforcement
  claims ambiguous between "reviewers must catch this" and "CI will catch
  this."
