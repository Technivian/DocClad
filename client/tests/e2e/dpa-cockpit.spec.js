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

async function expectNoHorizontalPageOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
}

test('DPA intake exposes the current accessible heading', async ({ page }) => {
  await login(page);
  await page.goto('/contracts/new/dpa/');
  await expect(page.getByRole('heading', { name: /^New DPA\b/ })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'DPA intake steps' })).toBeVisible();
});

test('DPA governed workspace keeps drafting layout, clause-link, and overflow contracts', async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/contracts/workflows/1/');

  const workspace = page.locator('.dc-ds-workspace');
  await expect(workspace).toBeVisible();
  await expect(page.getByText('Lifecycle')).toBeVisible();
  await expect(workspace.locator('[data-workspace-layout]')).toBeVisible();
  await expect(workspace.locator('.dc-ds-workspace__doc')).toBeVisible();

  const riskLink = workspace.locator('[data-clause-link]').first();
  if (await riskLink.count()) {
    const anchor = await riskLink.getAttribute('data-clause-link');
    await riskLink.click();
    await expect(workspace.locator(`.dc-ds-workspace__clause#${anchor}`).first()).toHaveClass(/is-linked/);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator('[data-workspace-drafting]')).toBeVisible();
  await expectNoHorizontalPageOverflow(page);
});
