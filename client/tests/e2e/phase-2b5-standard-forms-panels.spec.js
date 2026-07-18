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

test.describe('Phase 2B.5 standard record and admin forms', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('record form preserves canonical controls, validation, and responsive layout', async ({ page }) => {
    await page.goto('/contracts/clients/new/');
    const form = page.locator('form.dc-ds-surface');
    await expect(form).toHaveClass(/dc-ds-surface/);
    await expect(form.locator('.dc-ds-form-field').first()).toBeVisible();
    const control = form.locator('.dc-ds-form-field__control input, .dc-ds-form-field__control select').first();
    await control.focus();
    await expect(control).toBeFocused();
    await form.evaluate((element) => { element.noValidate = true; });
    await form.locator('button[type="submit"]').click();
    await expect(form.locator('.dc-ds-form-field--error').first()).toBeVisible();
    await expect(page).toHaveScreenshot('phase-2b5-record-form-error.png', { fullPage: true, animations: 'disabled' });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(form).toBeVisible();
    const bounds = await form.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds.width).toBeLessThanOrEqual(390);
  });

  test('admin approval form uses the shared field partial and canonical panels', async ({ page }) => {
    await page.goto('/contracts/approvals/new/');
    const form = page.locator('form.dc-ds-record-form');
    await expect(page.locator('.dc-ds-record-layout__main.dc-ds-surface')).toBeVisible();
    await expect(form.locator('.dc-ds-form-field').first()).toBeVisible();
    await expect(page.locator('.dc-ds-record-rail .dc-ds-surface')).toHaveCount(2);
    await expect(page).toHaveScreenshot('phase-2b5-admin-form.png', { fullPage: true, animations: 'disabled' });
  });
});
