# Interaction Guidelines

## Motion

Motion reinforces causality and orientation. It is not decoration.

- Hover/focus transitions: 120ms.
- Panels, drawers, and state changes: 180ms.
- Prefer opacity and transform; avoid layout animation unless it clarifies a
  meaningful reordering.
- Respect `prefers-reduced-motion`.
- Use CSS transitions and the Web Animations API by default. Adopt Motion only
  when a future React surface needs coordinated layout or gesture behavior.

## Focus And Keyboard

- Every interactive control must be keyboard reachable.
- Use the shared forest focus ring; never remove focus without replacement.
- `Cmd/Ctrl+K` opens the command palette.
- `Escape` closes the active non-destructive overlay.
- Dialog focus returns to the control that opened it.

## Loading

- Preserve component dimensions while loading.
- Use skeletons for structured content and spinners for bounded commands.
- Disable duplicate submission while preserving the action label.
- Long-running legal/AI operations show stage, elapsed state, and a safe exit.

## Success And Error

- Toasts confirm non-blocking actions such as save, copy, or queue updates.
- Inline errors stay next to the field or decision that needs correction.
- Banners are reserved for page-level conditions.
- Destructive or irreversible actions require explicit confirmation.
- Error text states what failed and the recovery action; never expose raw
  exceptions to users.

## Empty States

- Initial workspace: show activation actions, not zero dashboards.
- Filtered result: preserve filters and offer clear/reset.
- Permission state: explain access without suggesting impossible actions.
- Operational zero: preserve context and state that no action is required.

## Command Palette

The palette is navigation and retrieval, not a hidden settings surface. It
contains available sidebar destinations and global search. Commands respect the
same permission and workspace-mode rules as visible navigation.

## Toasts

Toasts are announced through an `aria-live` region. They auto-dismiss after a
short duration, pause while hovered, and never contain required decisions.
