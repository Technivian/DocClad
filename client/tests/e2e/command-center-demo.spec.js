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

test('Command Center demo shows DPA, MSA, and NDA workflows with workspace links', async ({ page }) => {
  test.slow();
  await login(page);

  await expect(page.getByRole('heading', { name: 'Command Center' })).toBeVisible();
  await expect(page.getByText('Privacy reviews')).toBeVisible();
  await expect(page.getByText('Commercial reviews')).toBeVisible();
  await expect(page.getByText('Self-serve ready')).toBeVisible();

  const scenarios = [
    {
      title: 'Northwind DPA Privacy Review Workflow',
      workspaceMarker: 'Generated DPA Draft',
    },
    {
      title: 'Acme MSA Commercial Review Workflow',
      workspaceMarker: 'Generated MSA Draft',
    },
    {
      title: 'Brightlane NDA Self-Serve Workflow',
      workspaceMarker: 'Generated NDA Draft',
    },
  ];

  for (const scenario of scenarios) {
    const row = page.locator(`[data-workflow-title="${scenario.title}"]`);
    await expect(row).toBeVisible();
    await expect(row.getByRole('link', { name: 'Open workspace' })).toBeVisible();
    await row.getByRole('link', { name: 'Open workspace' }).click();
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
    await expect(page.getByText(scenario.workspaceMarker, { exact: true }).first()).toBeVisible();
    await page.goto('/dashboard/');
  }
});
