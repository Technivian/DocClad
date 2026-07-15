# CLM One Brand Kit

This kit was created directly from the approved CLM One brand board and preserves the chosen visual lockup.

## Approved colours

- Deep Navy: `#0B1330`
- Teal: `#11B39A`
- White: `#FFFFFF`
- Light Gray: `#F2F4F7`

## Core assets

- `clmone-logo-primary.svg`
  Primary horizontal logo. Use on light backgrounds.

- `clmone-logo-white.svg`
  Full white version for dark backgrounds.

- `clmone-logo-black.svg`
  Monochrome black version.

- `clmone-mark-primary.svg`
  Symbol-only mark for compact navigation, favicons and app icons.

## Usage rules

1. Treat these files as the single source of truth.
2. Do not redraw or regenerate the logo.
3. Do not replace the wordmark with live text.
4. Do not alter colours, spacing or proportions.
5. Do not stretch, skew, rotate or crop the assets.
6. Do not add shadows, outlines, gradients or glow.
7. Use the full logo in spacious contexts.
8. Use the mark-only version in collapsed navigation and very small spaces.
9. Size with CSS height and automatic width.
10. Preserve clear space around the logo.

## React example

```tsx
import { CLMOneLogo } from "@/components/brand/CLMOneLogo";

<CLMOneLogo
  variant="primary"
  layout="full"
  className="h-10"
/>
```

## Technical note

The SVG assets preserve the approved artwork exactly by embedding the final raster artwork. They are not manually redrawn vector paths. This avoids introducing small shape changes through automatic tracing.
