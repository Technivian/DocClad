const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_owner';
const password = process.env.E2E_PASSWORD || 'e2e_pass_123';

async function login(page) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.goto('/dashboard/');
}

test.describe('Phase 2B.1 canonical buttons and badges', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('list family keeps canonical actions and semantic badges responsive', async ({ page }) => {
    await page.goto('/contracts/clients/');
    await expect(page.locator('.dc-ds-button--primary').first()).toBeVisible();
    await expect(page.locator('.dc-ds-badge--sm').first()).toBeVisible();
    await page.locator('.dc-ds-button--primary').first().focus();
    await expect(page.locator('.dc-ds-button--primary').first()).toBeFocused();
    await expect(page).toHaveScreenshot('phase-2b1-list-buttons-badges.png', { fullPage: true, animations: 'disabled' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.locator('.dc-ds-button--primary').first()).toBeVisible();
  });

  test('standard detail and modal actions preserve keyboard focus', async ({ page }) => {
    await page.goto('/contracts/');
    const path = await page.locator('a[href^="/contracts/"]').evaluateAll((links) => (
      links.map((link) => link.getAttribute('href')).find((href) => /^\/contracts\/\d+\/$/.test(href))
    ));
    await page.goto(path);
    await page.locator('[data-open-note-dialog]').first().click();
    const dialog = page.locator('#contract-note-dialog');
    await expect(dialog).toHaveAttribute('open', '');
    await expect(dialog.locator('.dc-ds-control').first()).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(dialog.locator('.dc-ds-button--primary')).toBeVisible();
    await expect(page).toHaveScreenshot('phase-2b1-detail-modal-buttons-badges.png', { fullPage: true, animations: 'disabled' });
  });

  test('admin settings preserve destructive and primary actions', async ({ page }) => {
    await page.goto('/contracts/privacy/data-controls/');
    await expect(page.locator('.dc-ds-button--danger, .dc-ds-button--primary').first()).toBeVisible();
    await expect(page).toHaveScreenshot('phase-2b1-admin-buttons.png', { fullPage: true, animations: 'disabled' });
  });
});
