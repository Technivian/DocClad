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

const pages = [
  { path: '/contracts/new/start/', root: '.ctp-page', title: 'New Contract' },
  { path: '/contracts/repository/', root: '.repo-page', title: 'Contracts' },
  { path: '/contracts/dpa-reviews/', root: '.dpa-review-page', title: 'DPA Reviews' },
  { path: '/contracts/obligations/', root: '.obligations-page', title: 'Obligations' },
];

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: '390px mobile', width: 390, height: 844 },
]) {
  test(`canonical workspaces fit ${viewport.name} without page overflow`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await login(page);

    for (const item of pages) {
      const response = await page.goto(item.path);
      expect(response).not.toBeNull();
      expect(response.status()).toBeLessThan(400);
      await expect(page.locator(item.root)).toBeVisible();
      await expect(page.locator('.topbar-page-title')).toHaveText(item.title);

      const overflow = await page.evaluate(() => ({
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        bodyWidth: document.body.scrollWidth,
      }));
      expect(overflow.documentWidth, `${item.path} document overflow`).toBeLessThanOrEqual(overflow.viewportWidth);
      expect(overflow.bodyWidth, `${item.path} body overflow`).toBeLessThanOrEqual(overflow.viewportWidth);
    }
  });
}
