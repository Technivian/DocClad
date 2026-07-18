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

async function capture(page, path, marker, name) {
  const response = await page.goto(path);
  expect(response).not.toBeNull();
  expect(response.status()).toBeLessThan(400);
  await expect(page.locator(marker).first()).toBeVisible();
  // Detail routes use the existing .reveal-stagger entrance treatment. Wait
  // for its final rendered state before capturing so a snapshot never records
  // an in-flight opacity frame as the product baseline.
  const revealChildren = page.locator('.reveal-stagger > *');
  if (await revealChildren.count()) {
    await expect(revealChildren.first()).toHaveCSS('opacity', '1');
    await expect(revealChildren.last()).toHaveCSS('opacity', '1');
  }
  await expect(page).toHaveScreenshot(`phase-1-${name}.png`, {
    fullPage: true,
    animations: 'disabled',
  });
}

test.describe('Phase 1 visual baselines', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
  });

  test('dashboard baseline', async ({ page }) => {
    await capture(page, '/dashboard/', '.command-center.cc-v3', 'dashboard');
  });

  test('list baseline', async ({ page }) => {
    await capture(page, '/contracts/', '.page-wrap.cw-page', 'list');
  });

  test('form baseline', async ({ page }) => {
    await capture(page, '/contracts/new/', 'form', 'form');
  });

  test('workspace baseline', async ({ page }) => {
    await capture(page, '/contracts/workflows/', '.workspace-main.hero-shell', 'workspace');
  });

  test('detail baseline', async ({ page }) => {
    await page.goto('/contracts/');
    const detailPath = await page.locator('a[href^="/contracts/"]').evaluateAll((links) => (
      links.map((link) => link.getAttribute('href')).find((href) => /^\/contracts\/\d+\/$/.test(href))
    ));
    expect(detailPath).toBeTruthy();
    await capture(page, detailPath, '.page-wrap', 'detail');
  });
});
