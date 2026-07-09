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

test('MSA governed drafting cockpit generates a workflow workspace and dashboard queue row', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const counterparty = `E2E MSA Counterparty ${suffix}`;

  await page.goto('/contracts/new/start/');
  await expect(page.getByRole('heading', { name: 'What are you creating?' })).toBeVisible();
  await page.locator('a[href="/contracts/new/msa/"]').click();

  await expect(page).toHaveURL(/\/contracts\/new\/msa\/?$/);
  await expect(page.getByRole('heading', { name: 'New MSA Draft' })).toBeVisible();
  await expect(page.getByText('AI-assisted drafting from approved templates and playbooks.')).toBeVisible();
  await expect(page.getByText('MSA Commercial Review Workflow')).toBeVisible();
  await expect(page.getByText('Draft workspace')).toBeVisible();
  await expect(page.getByText('Workflow controls')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Review triggers' })).toBeVisible();

  await page.fill('[data-field-key="counterparty"]', counterparty);
  await page.fill('[data-field-key="start_date"]', '2026-10-01');
  await page.fill('[data-field-key="contract_owner"]', 'Avery Brooks');
  await page.fill('[data-field-key="business_unit"]', 'Revenue Operations');
  await page.fill('[data-field-key="internal_reference"]', `MSA-E2E-${suffix}`);
  await page.fill('[data-field-key="value"]', '350000');
  await page.selectOption('[data-field-key="currency"]', 'EUR');
  await page.fill('[data-field-key="payment_terms"]', 'Net 30');
  await page.fill('[data-field-key="initial_term"]', '24 months');
  await page.selectOption('[data-field-key="renewal_type"]', 'Auto-renew');
  await page.fill('[data-field-key="termination_notice_period"]', '60');
  await page.fill('[data-field-key="services_description"]', 'Managed logistics platform and support services.');
  await page.fill('[data-field-key="governing_law"]', 'Delaware');
  await page.fill('[data-field-key="jurisdiction"]', 'Amsterdam');
  await page.fill('[data-field-key="liability_cap"]', '2x annual fees');
  await page.fill('[data-field-key="confidentiality_period"]', '5 years');
  await page.selectOption('[data-field-key="ip_ownership"]', 'Customer');

  await page.check('[data-field-key="sow_required"]');
  await page.check('[data-field-key="deliverables_defined"]');
  await page.check('[data-field-key="acceptance_criteria_required"]');
  await page.check('[data-field-key="personal_data_involved"]');
  await page.check('[data-field-key="value_above_threshold_confirmed"]');
  await page.check('[data-field-key="liability_cap_nonstandard"]');
  await page.check('[data-field-key="services_involve_personal_data"]');
  await page.check('[data-field-key="auto_renewal_included"]');
  await page.check('[data-field-key="ip_ownership_nonstandard"]');
  await page.check('[data-field-key="governing_law_nonpreferred"]');

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
  await expect(page.locator('#msa-command-risk')).toContainText('High risk');
  await expect(page.locator('#msa-next-action')).toContainText('Review triggered approval route');

  await page.locator('[data-clause-link="data-protection"]').first().click();
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
  await expect(page.getByRole('button', { name: 'Generate MSA summary' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export Word' })).toBeVisible();

  await page.locator('[data-clause-link="data-protection"]').first().click();
  await expect(page.locator('#data-protection')).toHaveClass(/is-linked/);

  await page.goto('/dashboard/');
  const queueRow = page.locator('tr[data-queue-row]', { hasText: counterparty }).first();
  await expect(queueRow).toBeVisible();
  await expect(queueRow).toContainText('MSA');
  await expect(queueRow).toContainText('MSA Commercial Review Workflow');
  const openWorkspaceLink = queueRow.getByRole('link', { name: 'Open workspace' });
  await expect(openWorkspaceLink).toBeVisible();
  await openWorkspaceLink.scrollIntoViewIfNeeded();
  const workspaceHref = await openWorkspaceLink.getAttribute('href');
  expect(workspaceHref).toMatch(/\/contracts\/workflows\/\d+\/?$/);
  await openWorkspaceLink.evaluate((node) => node.click());

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Workflow Timeline')).toBeVisible();
  await expect(page.locator('.msa-ws-card-head', { hasText: 'Generated MSA Draft' }).first()).toBeVisible();
});
