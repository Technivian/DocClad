const { test, expect } = require('@playwright/test');

const username = 'payrollminds_admin';
const password = 'CLMOneMVP!2026';

async function login(page) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await expect(page).not.toHaveURL(/\/login\/?$/);
}

async function openRepositoryContract(page, title) {
  await page.goto(`/contracts/repository/?q=${encodeURIComponent(title)}`);
  const link = page.getByRole('link', { name: title }).first();
  await expect(link).toBeVisible();
  await link.click();
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
}

test('Payrollminds buyer demo tells a complete contract lifecycle story', async ({ page }) => {
  test.slow();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page);

  await page.goto('/contracts/repository/');
  await expect(page.locator('.topbar-page-title')).toHaveText('Contracts');
  for (const title of [
    'Payrollminds Master Services Agreement',
    'Atlas Workforce Order Confirmation 2026',
    'Consultancy Services Agreement — HRIS rollout',
    'Data Processing Agreement — Cloud payroll',
    'Mutual NDA — FinTalent partnership',
    'Addendum — 2026 pricing and service levels',
  ]) {
    await expect(page.getByRole('link', { name: title }).first()).toBeVisible();
  }

  await openRepositoryContract(page, 'Payrollminds Master Services Agreement');
  await expect(page.getByText('Agreement family', { exact: true })).toBeVisible();
  await expect(page.getByText('Atlas Workforce Order Confirmation 2026', { exact: true })).toBeVisible();
  await expect(
    page.locator('#tab-overview').getByText('Payrollminds MSA — executed agreement', { exact: true }),
  ).toBeVisible();

  await page.getByRole('tab', { name: 'Documents' }).click();
  await expect(page.getByText('Payrollminds MSA — negotiated draft', { exact: true })).toBeVisible();
  await expect(
    page.locator('#tab-documents').getByText('Payrollminds MSA — executed agreement', { exact: true }),
  ).toBeVisible();

  await page.getByRole('tab', { name: 'Workflow' }).click();
  await expect(page.getByText('Elise van Dijk', { exact: true })).toBeVisible();
  await expect(page.getByText('Signed', { exact: true }).first()).toBeVisible();

  await openRepositoryContract(page, 'Atlas Workforce Order Confirmation 2026');
  await expect(page.getByText(/^Governing agreement/)).toBeVisible();
  await expect(page.getByText('Payrollminds Master Services Agreement', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Workflow' }).click();
  await expect(page.getByText('Legal Review', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Finance Review', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Pending', { exact: true }).first()).toBeVisible();

  await page.goto('/contracts/dpa-reviews/');
  const dpaLink = page.getByRole('link', { name: 'Data Processing Agreement — Cloud payroll' });
  await expect(dpaLink).toBeVisible();
  await dpaLink.click();
  await expect(page.getByText('DPA overrides the MSA liability cap', { exact: true })).toBeVisible();
  await expect(page.getByText('24-hour breach notice is operationally unrealistic', { exact: true })).toBeVisible();
  await expect(page.getByText('Payrollminds Master Services Agreement', { exact: true })).toBeVisible();

  await page.goto('/contracts/obligations/');
  for (const obligation of [
    'MSA renewal decision',
    'Review next subprocessor notification',
    'Approve HRIS discovery milestone',
    'Review 2027 pricing indexation',
    'Confirm NDA term before partnership launch',
  ]) {
    await expect(page.getByText(obligation, { exact: true })).toBeVisible();
  }
});

test('Payrollminds repository and contract detail fit a 390 px mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);

  for (const path of ['/contracts/repository/', '/contracts/obligations/']) {
    await page.goto(path);
    const widths = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
      body: document.body.scrollWidth,
    }));
    expect(widths.document, `${path} document overflow`).toBeLessThanOrEqual(widths.viewport);
    expect(widths.body, `${path} body overflow`).toBeLessThanOrEqual(widths.viewport);
  }

  await openRepositoryContract(page, 'Payrollminds Master Services Agreement');
  const widths = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
  }));
  expect(widths.document, 'contract detail document overflow').toBeLessThanOrEqual(widths.viewport);
  expect(widths.body, 'contract detail body overflow').toBeLessThanOrEqual(widths.viewport);

  await page.locator('#mobileNavToggle').click();
  await expect(page.locator('.sidebar-brand .logo-wordmark')).toBeHidden();
  await expect(page.locator('.sidebar-brand .logo-mark')).toBeVisible();
});
