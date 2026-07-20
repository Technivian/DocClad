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
  await expect(page.locator('section[aria-label="Operational queues"]')).toBeVisible();
  await expect(page.getByText('Governance controls')).toBeVisible();

  const scenarios = [
    {
      title: 'Northwind DPA Privacy Review Workflow',
      workspaceMarker: 'Guided drafting',
    },
    {
      title: 'Acme MSA Commercial Review Workflow',
      workspaceMarker: 'Guided drafting',
    },
    {
      title: 'Brightlane NDA Self-Serve Workflow',
      workspaceMarker: 'Guided drafting',
    },
  ];

  for (const scenario of scenarios) {
    const openWorkspaceLink = page.getByRole('link', { name: new RegExp(scenario.title) }).first();
    await expect(openWorkspaceLink).toBeVisible();
    await openWorkspaceLink.click();
    await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
    await expect(page.getByText(new RegExp(scenario.workspaceMarker, 'i')).first()).toBeVisible();
    await page.goto('/dashboard/');
  }
});
