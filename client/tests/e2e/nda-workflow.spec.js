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

test('NDA self-serve cockpit generates a governed workspace and dashboard row', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const counterparty = `E2E NDA Counterparty ${suffix}`;

  await page.goto('/contracts/new/start/');
  await page.locator('a[href="/contracts/new/nda/"]').click();

  await expect(page).toHaveURL(/\/contracts\/new\/nda\/?$/);
  await expect(page.getByRole('heading', { name: 'New NDA Draft' })).toBeVisible();
  await expect(page.getByText('AI Smart Questions')).toBeVisible();

  await page.fill('[data-field-key="counterparty"]', counterparty);
  await page.fill('[data-field-key="start_date"]', '2026-10-01');
  await page.fill('[data-field-key="contract_owner"]', 'Avery Brooks');
  await page.fill('[data-field-key="business_unit"]', 'Revenue Operations');
  await page.fill('[data-field-key="internal_reference"]', `NDA-E2E-${suffix}`);
  await page.selectOption('[data-field-key="nda_type"]', 'Mutual');
  await page.fill('[data-field-key="confidentiality_purpose"]', 'product diligence and commercial evaluation');
  await page.fill('[data-field-key="confidentiality_period"]', '2');
  await page.fill('[data-field-key="disclosure_scope"]', 'technical architecture and pricing details');
  await page.fill('[data-field-key="permitted_recipients"]', 'employees and external counsel with a need to know');
  await page.fill('[data-field-key="governing_law"]', 'Netherlands');
  await page.fill('[data-field-key="jurisdiction"]', 'Amsterdam');
  await page.check('[data-field-key="injunctive_relief_included"]');

  await expect(page.locator('#nda-draft-doc')).toContainText(counterparty);
  await expect(page.locator('#nda-progress-pct')).toHaveText('100%');
  await expect(page.locator('#nda-readiness-self-serve')).toHaveText('Eligible');
  await expect(page.locator('#nda-risk-signal-list')).toContainText('Self-serve eligible');
  await expect(page.locator('#nda-gov-approval-route')).toContainText('Contract Owner');
  await expect(page.locator('#nda-gov-approval-route')).toContainText('Signature');

  await page.locator('[data-clause-link="purpose"]').first().click();
  await expect(page.locator('#purpose')).toHaveClass(/is-linked/);

  await page.click('#submit-nda-btn');

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Workflow Timeline')).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
  await expect(page.locator('.nda-ws-card-head', { hasText: 'Generated NDA Draft' }).first()).toBeVisible();
  await expect(page.locator('.nda-ws-card-head', { hasText: 'Risk Signals' }).first()).toBeVisible();
  await expect(page.locator('.nda-ws-card-head', { hasText: 'Approval Route' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send for signature' })).toBeVisible();

  await page.goto('/dashboard/');
  const queueRow = page.locator('tr[data-queue-row]', { hasText: counterparty }).first();
  await expect(queueRow).toBeVisible();
  await expect(queueRow).toContainText('NDA');
  await expect(queueRow).toContainText('Self-serve eligible');
  await queueRow.getByRole('link', { name: 'NDA Self-Serve Workflow' }).click();

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
});
