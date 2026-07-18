const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_owner';
const password = process.env.E2E_PASSWORD || 'e2e_pass_123';

async function login(page) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await expect(page).not.toHaveURL(/\/login\/?$/);
}

test('Phase 2B.3 status routes and the populated contract drawer remain responsive', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page);

  await page.goto('/contracts/documents/');
  await expect(page.locator('.page-title')).toContainText('Document Management');

  await page.goto('/contracts/repository/');
  const row = page.locator('tr.contract-row').first();
  await expect(row).toBeVisible();
  const stageBadge = row.locator('.dc-ds-badge--sm');
  await expect(stageBadge).toHaveClass(/dc-ds-badge--(?:success|progress|attention|danger|special|neutral)/);
  const contractId = await row.getAttribute('data-contract-id');
  await page.goto(`/contracts/repository/?contractId=${contractId}`);
  const drawerStatus = page.locator('#details-drawer .dc-ds-badge--sm');
  await expect(drawerStatus).toBeVisible();
  await expect(drawerStatus).toHaveClass(/dc-ds-badge--(?:success|progress|attention|danger|special|neutral)/);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator('tr.contract-row').first()).toBeVisible();
});
