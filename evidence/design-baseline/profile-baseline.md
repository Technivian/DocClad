# Design Refactor — /profile/ Vertical Slice Baseline

Captured 2026-06-23, dark theme, logged in as e2e_owner.

## Why this page
`/profile/` (UserProfileForm) exhibits the core inconsistency on a single screen:
four distinct button classes with no coherent hierarchy, plus form controls
carrying hardcoded light-mode Tailwind classes.

## Buttons present (computed styles BEFORE)
| Label | Class | Background | Text color | Border |
|---|---|---|---|---|
| New Contract (header) | `btn-primary-sm` | transparent (gradient img) | white | none |
| Save Changes | `btn-primary` | `rgb(37,99,235)` solid blue | white | none |
| Send verification code | `btn-secondary` | transparent | `rgb(156,163,175)` gray | `rgb(31,41,55)` |
| Generate recovery codes | `btn-green` | `rgba(34,197,94,.08)` | `rgb(74,222,128)` | `rgba(34,197,94,.3)` |

Two "primary" buttons (`btn-primary` solid vs `btn-primary-sm` gradient) render
differently — the visible inconsistency the user reported.

## Form controls (BEFORE)
- All inputs carry: `w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm` (+ `bg-white` on selects).
- Inputs render dark only because a base.html global override beats the class — the class names lie (split authority / specificity fight).
- The **MFA-enabled checkbox renders as a white box** — the light-mode `bg-white`/`border-gray-300` leaks through visually. Concrete bug.

## Screenshots
- profile-top-before / profile-buttons-before (captured in session)

## Success criteria for the slice
1. One primary style, one secondary style, one destructive/soft style — consistent.
2. Checkbox renders correctly in dark theme (no white box).
3. UserProfileForm carries no hardcoded Tailwind class strings.
4. Existing form/UI tests pass.
