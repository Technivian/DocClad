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

async function detailPath(page) {
  await page.goto('/contracts/');
  const path = await page.locator('a[href^="/contracts/"]').evaluateAll((links) => (
    links.map((link) => link.getAttribute('href')).find((href) => /^\/contracts\/\d+\/$/.test(href))
  ));
  expect(path).toBeTruthy();
  return path;
}

test.describe('Phase 2A shared components', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('list controls retain keyboard focus and responsive sizing', async ({ page }) => {
    await page.goto('/contracts/repository/');
    const search = page.locator('#search-input');
    await expect(search).toHaveClass(/dc-ds-control/);
    await search.focus();
    await expect(search).toBeFocused();
    await expect(search).toHaveCSS('border-color', /rgb/);

    const filterToggle = page.locator('#repo-filter-toggle');
    await filterToggle.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#repository-filters')).toHaveClass(/is-open/);
    await expect(page).toHaveScreenshot('phase-2a-list-controls.png', { fullPage: true, animations: 'disabled' });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(search).toBeVisible();
    const bounds = await search.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds.width).toBeLessThanOrEqual(390);
  });

  test('contract form retains canonical actions and validation feedback', async ({ page }) => {
    await page.goto('/contracts/new/');
    await expect(page.locator('#submit-contract-btn')).toHaveClass(/dc-ds-button--primary/);
    // The approved launcher permits submission and renders validation feedback;
    // it deliberately does not block the submit action client-side.
    await expect(page.locator('#submit-contract-btn')).toBeEnabled();
    await expect(page.locator('#id_title')).toHaveClass(/dc-ds-control/);
    await expect(page.locator('.cform-intake-panel.dc-ds-surface').first()).toBeVisible();
    await page.locator('#contract-form').evaluate((form) => {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
    await expect(page.locator('[role="alert"]').first()).toBeVisible();
    await expect(page).toHaveScreenshot('phase-2a-form-validation.png', { fullPage: true, animations: 'disabled' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.locator('#id_title')).toBeVisible();
  });

  test('detail modal uses canonical actions and controls', async ({ page }) => {
    await page.goto(await detailPath(page));
    await expect(page.locator('.dc-ds-badge--sm').first()).toBeVisible();
    await page.locator('[data-open-note-dialog]').first().click();
    const dialog = page.locator('#contract-note-dialog');
    await expect(dialog).toHaveAttribute('open', '');
    await expect(dialog.locator('.dc-ds-control').first()).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(dialog.locator('.dc-ds-button--primary')).toBeVisible();
    await expect(page).toHaveScreenshot('phase-2a-note-modal.png', { fullPage: true, animations: 'disabled' });
  });
});
