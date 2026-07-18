const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_owner';
const password = process.env.E2E_PASSWORD || 'e2e_pass_123';

test('Phase 2B.2 canonical badge semantics render in dense and responsive layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.goto('/contracts/design-system/');

  for (const tone of ['success', 'progress', 'attention', 'danger', 'special', 'neutral']) {
    await expect(page.locator(`.dc-ds-badge--${tone}`).first()).toBeVisible();
  }
  await expect(page.locator('.dc-ds-table .dc-ds-badge').first()).toBeVisible();
  await expect(page).toHaveScreenshot('phase-2b2-badge-semantics.png', {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixels: 20,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator('.dc-ds-badge--special').first()).toBeVisible();
});
