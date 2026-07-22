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
  await page.emulateMedia({ reducedMotion: 'reduce' });
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
  const options = {
    fullPage: true,
    animations: 'disabled',
  };
  // The Command Center expresses live relative due dates and activity age.
  // These are intentionally covered by its functional tests but cannot form
  // a stable visual fixture across a date boundary.
  if (name === 'dashboard') {
    options.mask = [
      page.locator('.cc-v3-action-date'),
      page.locator('.cc-v3-date-status'),
      page.locator('.cc-v3-table tbody td:last-child'),
    ];
  }
  await expect(page).toHaveScreenshot(`phase-1-${name}.png`, options);
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
    await capture(page, '/contracts/repository/', '.dc-ds-list-page.repo-page', 'list');
  });

  test('form baseline', async ({ page }) => {
    await capture(page, '/contracts/new/start/', '.ctp-page', 'form');
  });

  test('workspace baseline', async ({ page }) => {
    await capture(page, '/contracts/workflows/', '#workflow-ops-root, .workflow-ops-page', 'workspace');
  });

  test('detail baseline', async ({ page }) => {
    await page.goto('/contracts/workflows/');
    const detailPath = await page.locator('a[href^="/contracts/workflows/"]').evaluateAll((links) => (
      links.map((link) => link.getAttribute('href')).find((href) => /^\/contracts\/workflows\/\d+\/$/.test(href))
    ));
    expect(detailPath).toBeTruthy();
    await capture(page, detailPath, '.dc-ds-workspace--nda, .dc-ds-workspace--record, .workspace-main.hero-shell', 'detail');
  });
});
