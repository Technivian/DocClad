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

test.describe('Phase 4A standard record and form scaffolds', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('client record creation keeps shell title, validation, and keyboard focus', async ({ page }) => {
    await page.goto('/contracts/clients/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Client');
    await expect(page.locator('.topbar-page-subtitle')).toBeEmpty();
    const form = page.locator('.dc-ds-record-content form.dc-ds-surface');
    const control = form.locator('.dc-ds-form-field__control input, .dc-ds-form-field__control select').first();
    await control.focus();
    await expect(control).toBeFocused();
    await form.evaluate((element) => { element.noValidate = true; });
    await form.locator('button[type="submit"]').click();
    await expect(form.locator('.dc-ds-form-field--error').first()).toBeVisible();
  });

  test('clause-library forms use labelled list back navigation without duplicated canvas titles', async ({ page }) => {
    await page.goto('/contracts/clause-categories/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Clause Category');
    const categoryBack = page.locator('.topbar-back-link');
    await categoryBack.focus();
    await expect(categoryBack).toBeFocused();
    await expect(categoryBack).toHaveAttribute('aria-label', 'Back to clause categories');
    await expect(page.locator('.dc-ds-record-page .page-title, .dc-ds-record-page .arch-title')).toHaveCount(0);

    await page.goto('/contracts/clause-library/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Clause Template');
    await page.locator('.topbar-page-title').evaluate((element) => { element.textContent = 'New clause template with an intentionally long governed record title'; });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.locator('.dc-ds-record-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  });

  test('approval administration keeps its notice, rail, actions, and compact layout', async ({ page }) => {
    await page.goto('/contracts/approvals/new/');
    await expect(page.locator('.topbar-page-title')).toHaveText('New Approval Request');
    await expect(page.locator('.dc-ds-record-notice[role="status"]')).toBeVisible();
    const actions = page.locator('.dc-ds-form-actions');
    await expect(actions.locator('a')).toHaveText('Cancel');
    await actions.locator('button').focus();
    await expect(actions.locator('button')).toBeFocused();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.locator('.dc-ds-record-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
    await expect(page.locator('.dc-ds-record-rail .dc-ds-surface')).toHaveCount(2);
  });
});
