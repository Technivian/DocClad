# Django Partials Inventory

These partials live under `theme/templates/design_system/`. They are not used by existing pages yet.

## `page_scaffold.html`

Purpose: top-level page wrapper and optional right-rail layout.

Inputs:

- `wide`
- `class_name`
- `with_rail`
- `main_template`
- `rail_template`

Use for:

- Settings pages
- Command Center surfaces
- Detail workspaces

## `page_hero.html`

Purpose: canonical page heading with optional actions.

Inputs:

- `eyebrow`
- `title`
- `subtitle`
- `actions_template`
- `primary_action_label`
- `primary_action_href`
- `secondary_action_label`
- `secondary_action_href`
- `class_name`

Use for:

- Page headers
- Workspace headers
- Settings headers

## `surface_card.html`

Purpose: bordered white work surface/card.

Inputs:

- `title`
- `labelledby`
- `meta_template`
- `body_template`
- `class_name`

Use for:

- Cards
- Tables
- Form sections
- Detail panels

## `metric_card.html`

Purpose: compact KPI/metric card.

Inputs:

- `label`
- `value`
- `note`
- `class_name`

Use for:

- Command Center summary counts
- Settings/status summaries
- Operational counters

## `status_badge.html`

Purpose: semantic badge.

Inputs:

- `label`
- `tone`
- `class_name`

Supported tones:

- `trust`
- `success`
- `attention`
- `danger`
- `phase`

Use for:

- Status
- Risk
- Approval state
- Type labels

## `workflow_phase_badge.html`

Purpose: workflow-specific phase badge.

Inputs:

- `label`
- `class_name`

Use for:

- Intake
- Draft
- Review
- Approval
- Signature
- Repository

## `attention_banner.html`

Purpose: alert/attention/status banner.

Inputs:

- `tone`
- `role`
- `icon`
- `title`
- `message`
- `body_template`
- `class_name`

Supported tones:

- `attention`
- `danger`
- `success`

Use for:

- Risk warnings
- Blocking errors
- Success/ready states

## `work_queue_row.html`

Purpose: reusable operational queue row.

Inputs:

- `title`
- `meta`
- `type_label`
- `type_tone`
- `stage_label`
- `risk_label`
- `risk_tone`
- `href`
- `action_label`
- `class_name`

Use for:

- Command Center queue
- Approval queue
- Task queue
- Review queue

## `context_rail.html`

Purpose: right-side rail wrapper.

Inputs:

- `rail_template`
- `aria_label`
- `class_name`

Use for:

- Governance rail
- Support rail
- Audit rail
- Settings rail

## `action_zone.html`

Purpose: primary next-action panel.

Inputs:

- `label`
- `title`
- `actions_template`
- `class_name`

Use for:

- Primary next action
- Workflow controls
- Review/send/generate actions

## `empty_state.html`

Purpose: empty state block.

Inputs:

- `title`
- `copy`
- `actions_template`
- `class_name`

Use for:

- Empty tables
- Empty queues
- No search results
- Empty registries

## `audit_timeline_item.html`

Purpose: one audit/activity timeline event.

Inputs:

- `title`
- `meta`
- `class_name`

Use for:

- Audit trail preview
- Activity rail
- Workflow history

## `filter_search_bar.html`

Purpose: GET search/filter form shell.

Inputs:

- `method`
- `action`
- `search_name`
- `search_value`
- `placeholder`
- `filters_template`
- `submit_label`
- `class_name`

Use for:

- Repository filters
- Directory filters
- Queue filters

## `settings_section.html`

Purpose: two-column settings section.

Inputs:

- `title`
- `copy`
- `body_template`
- `class_name`

Use for:

- Organization settings
- Security settings
- Identity settings
- Profile settings

## Usage Pattern

Example future use:

```django
{% include "design_system/page_hero.html" with title="Settings" subtitle="Manage organization controls." %}
```

Do not include these partials in existing pages until that page is actively being migrated.
