# Casefile Migration Status

Casefile is the application-wide default, not a dashboard theme.

| Layer | Production standard |
|---|---|
| Components | DocClad-owned Django primitives inspired by shadcn/ui composition |
| Styling | Tailwind CSS v4 plus semantic Casefile tokens |
| Icons | Central Lucide-compatible `design_system/icon.html` adapter |
| Typography | Inter, light mode, zero negative tracking |
| Motion | CSS transitions and `DocClad.motion` Web Animations adapter |
| Charts | Framework-neutral `DocClad.chartTheme`; engine loaded only with a real chart |
| Tables | Casefile markup and server/client ownership contract; TanStack Core only for a qualifying client-owned table |
| Command palette | Accessible Django/JavaScript palette around global search |
| Toasts | Shared `DocClad.toast`, including Django server messages |

## Compatibility Policy

Legacy classes remain mapped to Casefile tokens so unchanged domain screens
inherit the same color, type, spacing, focus, and surface language. They are a
migration bridge, not an API for new work.

Shared shell, dashboard, repository, and queue icons must use the central icon
adapter. Custom SVG is reserved for brand marks, diagrams, and domain visuals
that do not exist in Lucide.

## Verification

The design-system test suite enforces light-only core assets, the corrected
spacing scale, central shell icons, shared feedback, data-table ownership, and
runtime motion/chart contracts. Representative desktop and mobile workflows
must also be checked before release.
