# CLM One Design System — "Ledger"

> **Architecture notice (2026-07-12):** This document preserves historical
> rationale and migration context. Its older literal colour values and
> two-accent discussion are not token authority. `DESIGN_CONSTITUTION.md`,
> `docs/design-system/ARCHITECTURE.md`, and
> `theme/static/css/clmone-tokens.css` are authoritative, in that order. New
> frontend work uses canonical teal `--seal`/`--color-brand-primary`; legacy
> copper and `--ds-*` names are compatibility aliases only.

Version: 1.3 · 2026-07-07
Tokens: `theme/static/css/clmone-tokens.css`
Brand authority: `clmone_agent_brand_kit/docs/clmone-approved-brand-board.png`
Governance: `DESIGN_CONSTITUTION.md` §14, §15 (Pipeline Governance)
Research basis: `IRONCLAD_DESIGN_AUDIT.md` (verified from Ironclad's shipped CSS) plus a
verified seven-product sweep (Juro, LinkSquares, Evisort/Workday CLM, Icertis, Spellbook,
Clio, Ironclad) — token-level, from fetched production CSS where available.

**v1.2 changelog**: product direction settled on a two-accent system instead of
v1.1's single rationed copper accent. **Teal reverts to the general accent** — active
nav, links, focus rings, selected states, and lifecycle/progress — while **copper/
burnt-orange becomes CTA-only**: reserved for primary creation/action buttons (e.g.
"New Contract", "New Risk") the way the reference Contract Workspace screen uses it.
This is a deliberate reversal of the v1.1 "copper is the only action accent, teal is
a narrow seal" rule; v1.1's Ironclad-adjacency concern is addressed instead by the
ledger signature (tabular numerals, ruled totals, mono record furniture) and copper
CTA buttons carrying the differentiation, not by suppressing brand teal. Fiduciary
surfaces (§5.2) keep their teal seal treatment but are now differentiated from
general teal accents by the *combination* of signals (seal-bg wash + top rule + mono
eyebrow), not by teal being exclusive to them.

**v1.1 changelog** (superseded by v1.2, kept for history): v1.0 made the product's
action accent a desaturated teal (`#0A7264`). On review this read as adjacent to
Ironclad even though the exact hex values differ (HSL check: hue ~171° vs Ironclad's
~163° — same teal-green family, but CLM One's is far more saturated, 84% vs 48%).
v1.1 re-accented the product on copper (`#B5502E`) instead, demoting teal to a
narrow seal role. v1.2 reverses this — see above.

---

## 1) The problem this system solves

CLM One currently reads as "default Tailwind SaaS" because it *is* default Tailwind SaaS:

| Generic tell (verified across the category) | CLM One today |
|---|---|
| Tailwind blue-600 `#2563EB` as primary | ✗ everywhere |
| Saturated status confetti (`#22C55E`-family badges) | ✗ everywhere |
| Three stacked geometric sans (Inter + Manrope + Sora) | ✗ base.html |
| Shadow-heavy cards, glows, gradient buttons | ✗ (partially removed 2026-07-04) |
| Pure-black-on-white / gray-950 dark surfaces | ✗ dark-first gray-900 UI |
| No relationship between brand assets and interface color | ✗ logo is navy/teal; UI is blue/green |

Meanwhile the approved brand kit (Deep Navy `#0B1330`, Teal `#11B39A`, Inter) appears
in the product only as logo files. The interface has no brand.

## 2) Competitive position (what the research found)

**Category table stakes** — every credible legal-software product does these:
light paper-like canvas (dark mode is a marketing device, never the working surface);
softened near-black ink (`#121212` Juro, `#17191C` Clio, `#221410` Icertis, `#1C212B`
Ironclad); ONE rationed action accent plus a small tinted status vocabulary; grotesque
or humanist sans for working text; borders/hairlines instead of drop shadows; tables
as the core surface.

**Differentiation axes**: warm↔cool (Icertis espresso/oat vs LinkSquares indigo),
serif dosage (Icertis Lora-led ↔ LinkSquares none), radius softness (Juro 24px pills ↔
Spellbook 4px knife-edges), accent temperature (lime, orange, wine, marigold, green).

**Unclaimed territory this system claims**: *the ledger aesthetic*. Nobody in the
category looks like money handled with fiduciary care — tabular numerals, ruled
totals, right-aligned currency, visible reconciliation states. Clio (the closest
product to CLM One's matter/billing/IOLTA scope) hides trust accounting behind
reassurance copy; Ironclad owns "editorial cream + working green." CLM One's actual
differentiators — IOLTA trust accounting and a hash-chained audit trail — point at
exactly the visual territory no one occupies.

## 3) Identity thesis

> **Cool paper. Navy ink. Teal accent. Copper CTA. Ledger precision.**

CLM One should look like the instrument a firm trusts with client money and the
record of every decision: a modern ledger, not a dashboard. Where the category drifts
warm-editorial (Ironclad, Icertis, Juro), CLM One is deliberately **cool and precise**
— which is also exactly what the approved brand palette says (cool light gray, deep
navy, teal). We differentiate by *discipline*, not decoration — and by a two-accent
system (teal + copper) that none of the seven audited competitors use in this split.

Five load-bearing ideas:

1. **The ink is the brand.** Text is navy-derived (`--ink-*` ramp from `#0B1330`),
   never neutral gray. This single move makes every screen quietly branded — the same
   trick Ironclad uses (`#1C212B` ink = logo ink, 648 uses in their bundle).
2. **Teal is the accent, copper is the CTA.** Links, focus rings, active/selected
   states, the active nav item, and lifecycle/progress all use `--primary` (teal,
   `#0A7264` light / `#17BFA5` dark) — the brand teal, restored to a general accent
   role. Copper/burnt-orange (`--btn-gradient`) is rationed to primary creation/action
   buttons only ("New Contract", "New Risk") — it never appears as a link, nav state,
   or focus ring.
3. **Teal also carries fiduciary trust.** Client-funds surfaces (trust accounts,
   disbursements, IOLTA reconciliation) use the same teal family plus additional
   fiduciary grammar — seal-bg wash, a top rule, and a mono eyebrow (§5.2) — so they
   still read as visually distinct from a merely-active nav item or link, even though
   the hue is shared with the general accent.
4. **Numbers are fiduciary.** Tabular numerals everywhere data appears; currency
   right-aligned; accounting rules (single rule above totals, double rule under final
   totals); record IDs/hashes/timestamps in mono. This is the ownable signature.
5. **Paper first.** The product is **light-first** on `--paper #F3F5F7` with white
   working cards. Dark theme survives as "navy night" (brand navy `#0B1330` becomes
   the card surface) but is secondary — every researched competitor works light.

## 4) Tokens (summary — canonical values in clmone-tokens.css)

### Ink ramp (replaces all gray-*/slate-*)
`--ink-900 #0B1330` headings/primary · `--ink-700 #2E3A57` strong body ·
`--ink-600 #46536F` body · `--ink-500 #5F6B85` secondary · `--ink-400 #838DA3` meta ·
`--ink-300 #AAB2C2` disabled · `--line-strong #C9CFDB` · `--line #DEE2EA` ·
`--hairline #EBEEF3` · `--paper #F3F5F7` canvas · `--card #FFFFFF` · `--well #EDF0F4`

### Teal ramp (the general accent — links, focus, active states, progress)
`--primary #0A7264` **default accent, light theme** (5.1:1 on white) ·
`--primary-hover #085C51` pressed · `--primary-light #11A08D` hover/borders (light) ·
`--primary #17BFA5` **default accent, dark theme** · `--primary-subtle` /
`--primary-bg` selected/pill tints. Same hue family as `--seal` — see below.

### Copper ramp (CTA-only — primary creation/action buttons)
`--copper-800 #8A3A1E` pressed (light theme) · `--copper-700 #B5502E` **default CTA
color, light theme** (5.1:1 on white) · `--copper-600 #C96A3E` hover/borders ·
`--copper-500 #CF7248` **default CTA color, dark theme** (5.4:1 on navy card) ·
`--copper-400 #E29368` hover, dark theme. Used only via `--btn-gradient` /
`.btn-primary-grad` — never for links, nav state, or focus rings.

### Seal (teal fiduciary treatment — same hue as the accent, plus extra grammar)
`--seal #0A7264` (light) / `#17BFA5` (dark) · `--seal-bg #DFF4EE` (light) /
`rgba(17,179,154,0.14)` (dark). Client-funds surfaces pair this with a top rule and
mono eyebrow (§5.2) so they stay legible as fiduciary even though teal is no longer
exclusive to them.

### Status vocabulary (tinted pills — fg on bg)
| Meaning | fg | bg | Replaces |
|---|---|---|---|
| positive (active/executed/paid) | `#0A7264` | `#DBF2EC` | green-500 confetti |
| pending (waiting on someone) | `#8A5A14` | `#F6EDD8` | yellow-400 |
| progress (in-flight) | `#3F569B` | `#E8EDF8` | blue-500 |
| danger (overdue/expired/debit) | `#A63A2B` | `#F8E8E3` | red-500 |
| neutral (draft/archived) | `#5F6B85` | `#ECEFF4` | gray-500 |
| special (rare: escalated/matching) | `#6D4E8E` | `#F0EAF7` | purple-500 |

Semantic mapping stays in `status_badge_class`/`phase_badge_class`
(`contracts/templatetags/clmone_format.py`) — templates never pick colors.

### Type
**Inter only** in product (brand mandate). Weights 400/500/600 — retire 700/800/900
from chrome; authority comes from ink and spacing, not shouting. Manrope and Sora are
**retired**. Scale: display 28/34 · title 22/28 · heading 16/24 · body 14/22 ·
small 13/18 · meta 12/16 · data 13/20 tabular. Eyebrows are mono 11px uppercase
+0.14em tracking. Negative tracking (-0.02em) on titles only.
Marketing surfaces may add one serif accent face (e.g. Source Serif 4 italic) —
the product never uses it.

### Shape & elevation
Radii: 6px controls · 10px cards · 12px panels · pills for status/people chips only.
**Borders over shadows**: working surfaces are 1px `--line` on `--card`; shadows
(`--shadow-overlay`, ink-tinted) exist only for popovers/modals/drawers.
No glows, no gradients, no background orbs (constitution §13 already bans these).

## 5) Signature elements (what makes it CLM One, not generic)

1. **Ledger rules** — `.rule-total` (1px `--ledger-rule` top border above a totals
   row) and `.rule-final` (3px double bottom border under a final total). Any surface
   that sums money uses them: invoices, trust balances, budget rollups.
2. **Fiduciary surface grammar** — any UI touching client funds (trust accounts,
   disbursements, IOLTA reconciliation) gets: `--seal-bg` background/top accent, 2px
   `--seal` top rule, and a mono eyebrow (`CLIENT FUNDS · IOLTA`). Client money must
   be *visibly different* from firm money everywhere it appears — the top rule +
   eyebrow combination, not the color alone, is what marks it fiduciary now that teal
   is the general accent too. Implemented on `trust_account_detail.html` /
   `trust_account_list.html`.
3. **The seal mark** — audit-verified states (hash-chain verified, executed,
   reconciled) render a teal circled-check chip labeled in mono (`SEALED`, `VERIFIED`).
   Echoes the brand board's teal check. Copper is never used for this — verification
   and general navigation/action state are both teal signals; creation CTAs are the
   copper one.
4. **Record furniture in mono** — IDs, hashes, timestamps, clause refs set in
   `--mono` at meta size. The audit trail should *look like evidence*.
5. **The fold** — the logo's folded document corner, reused as a corner detail on
   "source of truth" document cards and empty-state glyphs only. Sparingly.

## 6) Component recipes (core set)

- **Button / primary (CTA)**: `--btn-gradient` (copper) bg, white text, radius 6,
  8×16 padding. Reserved for primary creation/action buttons ("New Contract", "New
  Risk"). No gradients beyond the solid copper fill.
- **Button / secondary**: `--card` bg, 1px `--line`, `--ink-700` text; hover border
  `--ink-400`.
- **Button / quiet**: transparent, `--ink-500` text; hover `--well` bg.
- **Destructive**: outline style with `--msg-error-text`; solid red only in modals.
- **Status pill**: radius pill, 3×10 padding, 11px/600, tinted pair from the table
  above (these stay independent of the brand accent — status is universal software
  convention, not a brand statement). Countdown numbers inside pills use tabular nums.
- **Table**: header 11px mono uppercase `--ink-400` on `--well` with `--line-strong`
  bottom rule; 44px rows (52px comfortable); `--hairline` separators; no zebra;
  hover `--well`; selected teal tint + 2px `--primary` left rule; money columns
  right-aligned tabular.
- **Card/panel**: `--card`, 1px `--line`, radius 10; header row with `--hairline`
  underline; no shadow.
- **Inputs**: `--card` bg, 1px `--line`, radius 6, focus border `--primary` (teal) +
  3px focus ring; error border `--msg-error-text`.
- **Nav (sidebar)**: follows the page theme (white rail on paper / navy rail on navy
  night) — not fixed to one color, since `--sidebar-hover`/`--sidebar-active-*` are
  shared with other card-level components (views-rail, arch-status-tab) and can't be
  hardcoded to a single surface without breaking those. Active item = teal left
  rule + teal text/tint.
- **Lifecycle stepper** (`lc-*`): done/current dots and track use `--primary`
  (teal) — matches every other "this is the active/actionable thing" signal.
- **Fiduciary surfaces** (trust accounts): teal (`--seal`/`--seal-bg`) plus the top
  rule + mono eyebrow grammar from §5.2 — see there for why the combination, not
  color alone, marks it fiduciary now that teal is the general accent.

## 7) Migration map (apply across the app)

The app already routes almost everything through CSS variables in `base.html` —
migration is mostly *re-pointing those vars at tokens*, not rewriting templates:

| base.html var (today) | becomes |
|---|---|
| `--primary: #2563EB` | `#0A7264` teal (light) / `#17BFA5` teal (dark) |
| `--accent: #22C55E` | same teal as `--primary` — retire the separate hue |
| `--bg / --surface / --card-bg` grays | `--paper / --well / --card` |
| `--text-primary/secondary/muted/dim` | `--ink-900/500/400/300` |
| `--border / --card-border` | `--line / --hairline` |
| `--btn-gradient` | solid copper, CTA buttons only (kill gradients) |
| badge-green/yellow/red/blue/purple/gray | the six status pairs (unchanged by the accent pivot) |
| Manrope/Sora font rules | Inter + scale tokens |
| default `data-theme="dark"` | `data-theme="light"` default; dark = navy night |
| brand teal (`#11B39A` family) | general accent (`--primary`) plus fiduciary surfaces (§5.2) |

Suggested rollout order (each a reviewable slice): ① re-point base.html vars +
fonts + light-first default → instantly rebrands ~90% of chrome; ② status pills +
stepper + tables; ③ ledger/fiduciary treatments on billing, trust, budget surfaces;
④ landing/marketing alignment; ⑤ sweep stragglers (hardcoded hex, `text-gray-*`
overrides) — the constitution's existing rules already forbid new ones.

## 8) Rules (enforceable)

1. No Tailwind palette literals (`#2563EB`, `#22C55E`, `#6B7280`…) in any template
   or stylesheet. Grep-testable.
2. Teal (`--primary`) is the general accent: links, active/selected states, focus
   rings, active nav item, lifecycle/progress. Copper is not a substitute for it.
3. Copper (`--btn-gradient`) only for: primary creation/action CTA buttons. If
   copper shows up as a link, nav state, or focus ring, that's a bug.
4. Every money value: tabular numerals + right alignment. Every total: ledger rules.
5. Every client-funds surface: fiduciary grammar (§5.2).
6. One typeface in product (Inter, 400–650). No 700+ chrome, no second sans.
7. Borders for working surfaces; shadows for overlays only.
8. Status colors come from the six pairs via the template filters — never hand-picked,
   and never repurposed as the brand accent (copper and status-positive-green are
   deliberately different hues).
9. Dark theme is derived from tokens only — no `[data-theme="dark"] .foo` one-offs
   for new work.

## 9) Pipeline governance — why the process rules exist

`DESIGN_CONSTITUTION.md` §15 adds process rules (single-PR token/template
atomicity, a logged-exceptions table) on top of the token/component rules
above. The rationale:

- **Why single-PR, not just "keep them close in time":** a token value and
  the markup that consumes it are one unit of meaning — a token renamed or
  repointed without its consuming template change (or the reverse) leaves a
  window where deployed styles don't match the documented token values, which
  is exactly the kind of silent drift this system exists to prevent (see the
  "Generic tell" table in §1 — CLM One drifted to default-Tailwind precisely
  through accumulated small, disconnected changes).
- **Why logged exceptions instead of inline comments:** a `// temporary, see
  ticket #123` comment buried in a template is invisible to anyone auditing
  the design system as a whole. A single table in the constitution makes
  every outstanding deviation from Ledger visible in one place, with an
  expiry date that forces a decision (migrate or renew) instead of the
  exception quietly becoming permanent.
- **Authority order:** `DESIGN_CONSTITUTION.md` is the enforceable rule set;
  this document explains why those rules exist and how to apply them when a
  new page or component doesn't map cleanly onto an existing primitive. When
  the two disagree, the constitution wins and this document is stale and
  needs updating — not the other way around.
- **No claim of automated enforcement:** as of this writing, compliance with
  §15 is a pull-request review responsibility, not a CI gate. Nothing in this
  system currently blocks a merge automatically for a raw hex value or
  misplaced copper usage. Treat any statement to the contrary as out of date
  until a linter/grep step is actually wired into the test suite and named
  here.
