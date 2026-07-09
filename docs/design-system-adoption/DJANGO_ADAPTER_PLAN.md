# Django Design-System Adapter Plan

Date: 2026-07-09  
Status: additive adapter layer created; no page migration performed.

## Goal

Prepare DocClad to adopt the extracted Carelane visual system without introducing React/Radix or changing current pages. The adapter translates the design-system ideas into Django-template-compatible CSS classes and include partials.

## Constraints

- No React.
- No Radix.
- No page migration in this step.
- No backend/view/form/permission/model/route changes.
- Existing DocClad tokens remain in place.
- New classes are namespaced with `dc-ds-*`.
- New tokens are namespaced with `--ds-*`.

## Files Added

CSS:

- `theme/static_src/src/design-system/tokens.css`
- `theme/static_src/src/design-system/components.css`
- `theme/static_src/src/design-system/index.css`

Template partials:

- `theme/templates/design_system/page_scaffold.html`
- `theme/templates/design_system/page_hero.html`
- `theme/templates/design_system/surface_card.html`
- `theme/templates/design_system/metric_card.html`
- `theme/templates/design_system/status_badge.html`
- `theme/templates/design_system/workflow_phase_badge.html`
- `theme/templates/design_system/attention_banner.html`
- `theme/templates/design_system/work_queue_row.html`
- `theme/templates/design_system/context_rail.html`
- `theme/templates/design_system/action_zone.html`
- `theme/templates/design_system/empty_state.html`
- `theme/templates/design_system/audit_timeline_item.html`
- `theme/templates/design_system/filter_search_bar.html`
- `theme/templates/design_system/settings_section.html`

Documentation:

- `docs/design-system-adoption/DJANGO_ADAPTER_PLAN.md`
- `docs/design-system-adoption/DJANGO_PARTIALS_INVENTORY.md`
- `docs/design-system-adoption/TOKEN_PORTING_NOTES.md`

## CSS Integration

`theme/static_src/src/styles.css` imports:

```css
@import "./design-system/index.css";
```

This makes the adapter available in the generated CSS bundle, but no existing page uses these classes yet.

## Adapter Strategy

The adapter ports visual concepts, not implementation technology:

- Carelane/Radix component structure becomes Django include partials.
- React props become Django include variables.
- CVA variants become CSS modifier classes such as `dc-ds-button--primary` and `dc-ds-badge--attention`.
- Radix interactions are deferred. Menus, dialogs, popovers, tabs, and accordions need Django-safe behavior before use.

## Migration Rules

Future page migrations should:

1. Pick one page.
2. Preserve existing form fields, routes, IDs, and `data-*` hooks.
3. Replace only presentation wrappers and classes.
4. Use these partials where they fit.
5. Add focused tests/manual checks.
6. Avoid touching backend code.

## Recommended First Page

Recommended first migration remains `settings_hub.html`.

Reason: it exercises page hero, settings sections, cards, and actions without workflow creation, approval routing, or complex forms.

## Known Limitations

- This adapter does not implement interactive Radix behaviors.
- It does not include icon primitives yet; current templates mostly use inline SVG.
- It does not replace existing `.btn`, `.card`, `.badge`, `.table`, or `arch-*` classes.
- It does not establish final dark-mode behavior for the adapter.
- It does not guarantee visual parity with Carelane because no Carelane source files were present in this repo to diff against.
