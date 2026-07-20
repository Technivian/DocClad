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

test('login page renders and SSO entry is wired', async ({ page }) => {
  await page.goto('/login/');

  await expect(page.locator('input[name="username"]')).toBeVisible();
  await expect(page.locator('input[name="password"]')).toBeVisible();

  const ssoLink = page.locator('a[href*="/oidc/authenticate/"]');
  if (await ssoLink.count()) {
    await expect(ssoLink.first()).toBeVisible();
  }
});

test('local login works and key pages load', async ({ page }) => {
  await login(page);

  // Some deployments keep /login in history; assert authenticated access directly.
  const dashboardResponse = await page.goto('/dashboard/');
  expect(dashboardResponse).not.toBeNull();
  expect(dashboardResponse.status()).toBeLessThan(400);
  await expect(page).not.toHaveURL(/\/login\/?$/);

  const paths = ['/dashboard/', '/contracts/', '/contracts/repository/'];
  for (const path of paths) {
    const response = await page.goto(path);
    expect(response).not.toBeNull();
    expect(response.status()).toBeLessThan(400);
  }
});

test('redesigned workspace shells render on key frontend pages', async ({ page }) => {
  await login(page);

  const cases = [
    {
      path: '/dashboard/',
      title: /^Command Center$/,
      summaryText: /Governance controls/,
      marker: '.cc-v3-kpis',
      shell: '.command-center.cc-v3',
    },
    {
      path: '/contracts/',
      title: /Contract Workspace/,
      summaryText: /Contracts/,
      marker: '.cw-toolbar',
      shell: '.page-wrap.cw-page',
    },
    {
      path: '/contracts/workflows/',
      title: /Workflow Designer/,
      summaryText: /Active workflows/,
      marker: '.workflow-ops-page',
      shell: '#workflow-ops-root',
    },
    {
      path: '/contracts/workflows/templates/',
      title: /Workflow Designer/,
      summaryText: /Create template|No workflow templates yet/,
      marker: '.workflow-templates-page',
      shell: '.workflow-templates-page',
    },
  ];

  for (const item of cases) {
    const response = await page.goto(item.path);
    expect(response).not.toBeNull();
    expect(response.status()).toBeLessThan(400);
    await expect(page.locator(item.shell).first()).toBeVisible();
    await expect(page.locator(item.marker).first()).toBeVisible();
    await expect(page.getByText(item.title).first()).toBeVisible();
    await expect(page.getByText(item.summaryText).first()).toBeVisible();
  }
});
