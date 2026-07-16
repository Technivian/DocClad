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

async function reveal(locator) {
  const section = locator.locator('xpath=ancestor::details[1]');
  if (await section.count() && !(await section.evaluate((element) => element.open))) {
    await section.locator('summary').click();
  }
  await expect(locator).toBeVisible();
}

async function fillField(page, key, value) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.fill(value);
}

async function selectField(page, key, value) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.selectOption(value);
}

async function checkField(page, key) {
  const field = page.locator(`[data-field-key="${key}"]`);
  await reveal(field);
  await field.check();
}

test('MSA governed drafting cockpit generates a workflow workspace and dashboard queue row', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const counterparty = `E2E MSA Counterparty ${suffix}`;

  await page.goto('/contracts/new/start/');
  await expect(page.getByRole('heading', { name: 'New Contract' })).toBeVisible();
  await page.locator('a[href="/contracts/new/msa/"]').click();

  await expect(page).toHaveURL(/\/contracts\/new\/msa\/?$/);
  await expect(page.getByRole('heading', { name: 'New MSA Draft' })).toBeVisible();
  await expect(page.getByText('A focused, governed workspace for commercial terms, legal positions, and approval-ready drafting.')).toBeVisible();
  await expect(page.getByText('MSA Commercial Review Workflow')).toBeVisible();
  await expect(page.getByText('Live contract preview')).toBeVisible();
  await expect(page.getByText('Decision panel')).toBeVisible();
  await expect(page.getByText('Review and generate')).toBeVisible();

  await fillField(page, 'counterparty', counterparty);
  await fillField(page, 'start_date', '2026-10-01');
  await fillField(page, 'contract_owner', 'Avery Brooks');
  await fillField(page, 'business_unit', 'Revenue Operations');
  await fillField(page, 'internal_reference', `MSA-E2E-${suffix}`);
  await fillField(page, 'value', '350000');
  await selectField(page, 'currency', 'EUR');
  await fillField(page, 'payment_terms', 'Net 30');
  await fillField(page, 'initial_term', '24 months');
  await selectField(page, 'renewal_type', 'Auto-renew');
  await fillField(page, 'termination_notice_period', '60');
  await fillField(page, 'services_description', 'Managed logistics platform and support services.');
  await fillField(page, 'governing_law', 'Delaware');
  await fillField(page, 'jurisdiction', 'Amsterdam');
  await fillField(page, 'liability_cap', '2x annual fees');
  await fillField(page, 'confidentiality_period', '5 years');
  await selectField(page, 'ip_ownership', 'Customer');

  await checkField(page, 'sow_required');
  await checkField(page, 'deliverables_defined');
  await checkField(page, 'acceptance_criteria_required');
  await checkField(page, 'personal_data_involved');
  await checkField(page, 'value_above_threshold_confirmed');
  await checkField(page, 'liability_cap_nonstandard');
  await checkField(page, 'services_involve_personal_data');
  await checkField(page, 'auto_renewal_included');
  await checkField(page, 'ip_ownership_nonstandard');
  await checkField(page, 'governing_law_nonpreferred');

  await expect(page.locator('#msa-draft-doc')).toContainText(counterparty);
  await expect(page.locator('#msa-draft-doc')).toContainText('Managed logistics platform and support services.');

  const riskList = page.locator('#msa-risk-signal-list');
  await expect(riskList).toContainText('Finance approval signal');
  await expect(riskList).toContainText('Legal risk signal');
  await expect(riskList).toContainText('DPA/privacy review signal');
  await expect(riskList).toContainText('Renewal notice signal');

  await expect(page.locator('#msa-gov-approval-route')).toContainText('Contract Owner');
  await expect(page.locator('#msa-gov-approval-route')).toContainText('Finance');
  await expect(page.locator('#msa-gov-approval-route')).toContainText('Legal');
  await expect(page.locator('#msa-command-risk')).toContainText('active');
  await expect(page.locator('#msa-next-action')).toContainText(/Complete drafting inputs|Review triggered approval route/);

  await page.locator('[data-clause-link="data-protection"]:visible').first().click();
  await expect(page.locator('#data-protection')).toHaveClass(/is-linked/);

  await page.click('#submit-msa-btn');

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Workflow Timeline')).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Generated MSA Draft' }).first()).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Risk Signals' }).first()).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Approval Route' }).first()).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Audit Trail Preview' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send to Legal Review' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send to Finance' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download MSA summary' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export Word' })).toBeVisible();

  await page.locator('[data-clause-link="data-protection"]:visible').first().click();
  await expect(page.locator('#data-protection')).toHaveClass(/is-linked/);

  const workspaceHref = page.url();
  await page.goto('/contracts/workflows/');
  await page.goto(workspaceHref);
  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Workflow Timeline')).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Generated MSA Draft' }).first()).toBeVisible();
});
