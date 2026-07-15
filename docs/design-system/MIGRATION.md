# Casefile Migration Status

Casefile is the application-wide default. The production Command Center is its
visual and layout reference, not a separate dashboard theme.

| Layer | Production standard |
|---|---|
| Components | CLM One-owned Django primitives inspired by shadcn/ui composition |
| Styling | Tailwind CSS v4 plus semantic Casefile tokens |
| Icons | Central Lucide-compatible `design_system/icon.html` adapter |
| Typography | Inter, light mode, zero negative tracking |
| Motion | CSS transitions and `CLMOne.motion` Web Animations adapter |
| Charts | Framework-neutral `CLMOne.chartTheme`; engine loaded only with a real chart |
| Tables | Casefile markup and server/client ownership contract; TanStack Core only for a qualifying client-owned table |
| Command palette | Accessible Django/JavaScript palette around global search |
| Toasts | Shared `CLMOne.toast`, including Django server messages |

## Compatibility Policy

Legacy classes remain mapped to the same Command Center-backed tokens so
unchanged domain screens inherit its canvas, type, spacing, focus, surface,
control, table, and semantic-state language. They are a migration bridge, not
an API for new work.

Migration proceeds in the phases defined in
[`ARCHITECTURE.md`](ARCHITECTURE.md). Primary operating surfaces use canonical
markup directly; specialist legacy workflows inherit the same visual contract
through compatibility styles. Compatibility styles and `--ds-*` aliases remain
until repository-wide usage is zero.

Shared shell, dashboard, repository, and queue icons must use the central icon
adapter. Custom SVG is reserved for brand marks, diagrams, and domain visuals
that do not exist in Lucide.

## Verification

The design-system test suite enforces light-only core assets, the corrected
spacing scale, central shell icons, shared feedback, data-table ownership, and
runtime motion/chart contracts. Representative desktop and mobile workflows
must also be checked before release.
