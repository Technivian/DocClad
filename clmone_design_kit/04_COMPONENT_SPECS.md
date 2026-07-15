# Component Specs

## AppShell

Use one shell across all pages.

Structure:

- fixed dark navy sidebar
- top bar
- page content area with off-white background
- content max-width only when useful; operational pages may use full width

## SidebarNav

Width: 260–280px.
Background: deep navy.
Logo: top, compact.
Navigation groups:

- Workspace
- Execution
- Risk & Compliance
- Reference

Active item:

- subtle navy/teal-tinted background
- teal left border/accent
- readable white text
- icon in light teal/white

Inactive item:

- muted light text
- thin line icon
- hover background slightly lighter navy

## TopBar

Height: 64–72px.
Background: white.
Border-bottom: subtle.
Contents:

- global search
- firm selector
- utility icons
- orange `+ New Contract` button
- avatar/menu

## PageHeader

Contains:

- title
- optional status chip
- subtitle
- right actions

Use consistent spacing:

- title row 28–32px high
- subtitle 14–15px muted
- action buttons aligned right

## Buttons

Primary:

- burnt orange
- used only for creation/commit actions
- examples: Create Contract, New Contract, Send for Signature, Launch Approval

Secondary:

- white with border
- examples: Preview draft, Export, View Repository

Tertiary:

- text button
- examples: Cancel, Clear filters

Danger:

- only destructive actions
- never use orange for destructive action

## Cards

White surface, subtle border, minimal shadow.

Card types:

- Main work card: larger padding, focal area
- Support card: right rail, smaller padding
- Queue card: table container
- Metadata card: compact definition rows

## FormField

Labels:

- 14–15px, semibold, navy
- required asterisk in restrained red

Inputs:

- 40–44px height
- 8px radius
- border `--dc-border`
- focus ring teal at low opacity

## WorkflowRail

Use for contract lifecycle stages and approval flows.

Rules:

- active/completed: teal
- future: muted gray
- label below or beside marker
- avoid large numbered bubbles unless process numbers are essential
- should feel like a legal status rail, not a generic wizard

Standard lifecycle:

- Draft
- Legal Review
- Business Approval
- Signature
- Executed

## DataTable

Tables are central to CLM pages.

Rules:

- compact header with muted uppercase or semibold labels
- row height 52–60px
- clear action column
- status chips quiet and consistent
- avoid zebra stripes unless readability suffers
- use hover row background very subtly

## RightRailCard

Use for supportive workflow context.

Good content:

- completion state
- routing preview
- deadlines
- risk watch
- recent activity
- missing metadata
- next steps

Bad content:

- vanity analytics
- decorative graphs
- motivational copy

## Status Chips

Use a restrained palette:

- Draft: muted teal/gray
- Legal Review: teal
- Approval: muted navy/gray
- Signature: muted navy/gray
- Executed: teal/success
- Overdue/High Risk: restrained red
- Medium Risk: restrained amber
- Low Risk: muted gray/teal
