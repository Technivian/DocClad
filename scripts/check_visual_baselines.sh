#!/usr/bin/env bash
# Compare committed Playwright visual baselines. Never regenerates snapshots.
# Intentional updates require an explicit local run with PLAYWRIGHT_UPDATE_SNAPSHOTS=1.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

for arg in "$@"; do
  case "$arg" in
    --update-snapshots|--update-snapshots=*|*-u)
      echo "[visual-baselines] Refusing snapshot regeneration in the CI check path." >&2
      echo "[visual-baselines] For intentional updates, run locally:" >&2
      echo "  PLAYWRIGHT_UPDATE_SNAPSHOTS=1 npm --prefix client run test:e2e -- tests/e2e/visual-baselines.spec.js --update-snapshots" >&2
      exit 2
      ;;
  esac
done

if [[ "${PLAYWRIGHT_UPDATE_SNAPSHOTS:-}" == "1" && "${CI:-}" == "true" ]]; then
  echo "[visual-baselines] PLAYWRIGHT_UPDATE_SNAPSHOTS is forbidden when CI=true." >&2
  exit 2
fi

export CI="${CI:-true}"
export UPDATE_SNAPSHOTS=none

echo "[visual-baselines] Comparing baselines with --update-snapshots=none (fail on drift)..."
npm --prefix client ci >/dev/null
npm --prefix client exec playwright install chromium >/dev/null

npm --prefix client exec -- playwright test \
  --config=client/playwright.config.js \
  tests/e2e/visual-baselines.spec.js \
  --update-snapshots=none \
  "$@"

echo "[visual-baselines] OK — no unexplained drift."
