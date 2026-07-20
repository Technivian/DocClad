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

async function expectNoHorizontalPageOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
}

test.describe('Phase 5C workspace scaffold', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('keeps the MSA and contract-detail shared scaffold responsive and focusable', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/contracts/workflows/2/');
    const workspace = page.locator('.dc-ds-workspace');
    await expect(workspace).toBeVisible();
    await expect(workspace.locator('.dc-ds-workspace__header')).toBeVisible();
    await expect(workspace.locator('.dc-ds-workspace__timeline')).toBeVisible();
    const action = workspace.locator('.dc-ds-workspace__actions button').first();
    await action.focus();
    await expect(action).toBeFocused();

    await page.goto('/contracts/1/');
    await expect(page.locator('.dc-ds-workspace__metadata-grid')).toBeVisible();
    await expect(page.locator('.dc-ds-workspace__rail')).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.locator('.dc-ds-workspace')).toBeVisible();
    await expectNoHorizontalPageOverflow(page);
  });

  test('keeps the DPA drafting tabs keyboard-operable at 390px', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/contracts/workflows/1/');
    const workspace = page.locator('.dc-ds-workspace');
    await expect(workspace.locator('[data-workspace-drafting]')).toBeVisible();
    const tabs = workspace.locator('.dc-ds-workspace-tabs__tab');
    await expect(tabs.first()).toBeVisible();
    await tabs.nth(1).focus();
    await expect(tabs.nth(1)).toBeFocused();
    await tabs.nth(1).press('Enter');
    await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');
    await expectNoHorizontalPageOverflow(page);
  });
});
