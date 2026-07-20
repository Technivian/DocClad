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

test.describe('Phase 3B standard record-list scaffolds', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('repository keeps shell navigation and keyboard-operable list tabs', async ({ page }) => {
    await page.goto('/contracts/repository/');
    await expect(page.locator('.topbar-page-title')).toHaveText('Contracts');
    await expect(page.locator('.topbar-page-subtitle')).toContainText('governed repository');
    await expect(page.locator('.topbar-back-link')).toHaveCount(0);
    const tabs = page.locator('.repo-view-tabs.dc-ds-list-tabs a');
    await tabs.first().focus();
    await expect(tabs.first()).toBeFocused();
    await expect(page.locator('.repo-filter-shell')).toHaveClass(/dc-ds-list-toolbar/);
  });

  test('document and clause-library headers preserve action hierarchy on compact screens', async ({ page }) => {
    await page.goto('/contracts/documents/');
    await expect(page.locator('.dc-ds-page.dc-ds-list-page')).toBeVisible();
    await expect(page.locator('.topbar-page-title')).toHaveText('Document Management');
    await expect(page.locator('.dc-ds-list-header .dc-ds-button--quiet')).toHaveCount(1);
    await expect(page.locator('.dc-ds-list-header .dc-ds-button--primary')).toHaveCount(1);
    await page.setViewportSize({ width: 390, height: 844 });
    const primary = page.locator('.dc-ds-list-header .dc-ds-button--primary');
    await primary.focus();
    await expect(primary).toBeFocused();
    expect(await page.locator('.dc-ds-page.dc-ds-list-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();

    await page.goto('/contracts/clause-library/');
    await expect(page.locator('.topbar-page-title')).toHaveText('Clause Library');
    const longPrimary = page.locator('.dc-ds-list-header .dc-ds-button--primary');
    await longPrimary.evaluate((element) => { element.textContent = 'Add a governed clause library record with a long action label'; });
    expect(await page.locator('.dc-ds-page.dc-ds-list-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  });

  test('approval administration keeps its title, tabs, and table route semantics', async ({ page }) => {
    await page.goto('/contracts/approvals/');
    await expect(page.locator('.topbar-page-title')).toHaveText('Approvals');
    await expect(page.locator('.dc-ds-list-header .dc-ds-button--primary')).toBeVisible();
    const tab = page.locator('.wq-tabs.dc-ds-list-tabs [role="tab"]').first();
    await tab.focus();
    await expect(tab).toBeFocused();
    await expect(page.locator('.approvals-queue-body .dc-ds-table').first()).toBeVisible();

    await page.goto('/contracts/approval-rules/');
    await expect(page.locator('.dc-ds-page.dc-ds-list-page')).toBeVisible();
    await expect(page.locator('.topbar-page-title')).toHaveText('Approval Rules');
  });
});
