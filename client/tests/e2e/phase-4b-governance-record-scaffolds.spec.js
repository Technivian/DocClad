const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_owner';
const password = process.env.E2E_PASSWORD || 'e2e_pass_123';

async function login(page) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.goto('/dashboard/');
  await expect(page).not.toHaveURL(/\/login\/?$/);
}

test.describe('Phase 4B counterparty and governance record scaffolds', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('counterparty and privacy record forms use the shell header, shared form actions, and keyboard focus', async ({ page }) => {
    await page.goto('/contracts/counterparties/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Counterparty');
    await expect(page.locator('.topbar-back-link')).toHaveAttribute('aria-label', 'Back to counterparties');
    const counterpartyForm = page.locator('form.dc-ds-record-form');
    const firstControl = counterpartyForm.locator('input:not([type="hidden"]), select, textarea').first();
    await firstControl.focus();
    await expect(firstControl).toBeFocused();
    await expect(counterpartyForm.locator('.dc-ds-form-actions button')).toHaveText('Save');
    await counterpartyForm.evaluate((element) => { element.noValidate = true; });
    await counterpartyForm.locator('button[type="submit"]').click();
    await expect(counterpartyForm.locator('.dc-ds-form-field--error').first()).toBeVisible();

    await page.goto('/contracts/privacy/data-inventory/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Data Inventory Record');
    await expect(page.locator('form.dc-ds-record-form .dc-ds-form-actions button')).toHaveText('Save');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.locator('.dc-ds-record-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  });

  test('compliance and governance forms retain subtitles, action hierarchy, and compact layout', async ({ page }) => {
    await page.goto('/contracts/compliance/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Compliance Checklist');
    await expect(page.locator('.topbar-page-subtitle')).toHaveText('Create a new compliance checklist.');
    await expect(page.locator('.dc-ds-form-actions a')).toHaveText('Cancel');

    await page.goto('/contracts/privacy/legal-holds/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Legal Hold');
    await expect(page.locator('.topbar-back-link')).toHaveAttribute('aria-label', 'Back to legal holds');
    await page.locator('.dc-ds-form-actions button').focus();
    await expect(page.locator('.dc-ds-form-actions button')).toBeFocused();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.locator('.dc-ds-record-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  });
});
