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

async function submitOwningForm(page, fieldSelector) {
  await page.$eval(fieldSelector, (el) => {
    if (!el.form) {
      throw new Error(`No owning form for selector: ${fieldSelector}`);
    }
    el.form.requestSubmit();
  });
}

async function openPanel(page, collapsibleKey) {
  // contract_form.html's Legal posture / Lifecycle control / Draft brief
  // sections are collapsed <details> by default (opened automatically only
  // when the selected contract_type marks a field inside them as required).
  // Setting .open = true directly (rather than clicking the summary) is
  // idempotent — it won't toggle an already-open panel closed.
  await page.evaluate((key) => {
    const details = document.querySelector(`details[data-collapsible="${key}"]`);
    if (details) details.open = true;
  }, collapsibleKey);
}

async function selectOptionContainingText(page, selector, textFragment) {
  const value = await page.$eval(
    selector,
    (el, fragment) => {
      const options = Array.from(el.options || []);
      const match = options.find((opt) =>
        (opt.textContent || '').toLowerCase().includes(String(fragment).toLowerCase())
      );
      return match ? match.value : null;
    },
    textFragment
  );

  if (!value) {
    throw new Error(`No option containing '${textFragment}' for selector ${selector}`);
  }

  await page.selectOption(selector, value);
}

test('critical contract create and edit flow works', async ({ page }) => {
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const title = `E2E Contract ${suffix}`;

  await page.goto('/contracts/new/');
  await page.fill('input[name="title"]', title);
  await page.selectOption('select[name="contract_type"]', 'MSA');
  await page.fill('input[name="counterparty"]', 'E2E Counterparty');
  await openPanel(page, 'legal-posture');
  await page.fill('input[name="value"]', '10000');
  await page.selectOption('select[name="currency"]', 'USD');
  await page.fill('input[name="governing_law"]', 'State of Delaware');
  await page.fill('input[name="jurisdiction"]', 'New York');
  await page.selectOption('select[name="risk_level"]', 'LOW');
  await openPanel(page, 'lifecycle-control');
  await page.fill('input[name="start_date"]', '2026-04-12');
  await page.fill('input[name="end_date"]', '2026-12-31');
  await openPanel(page, 'draft-brief');
  await page.fill('textarea[name="content"]', 'Automated E2E contract body');
  await submitOwningForm(page, 'input[name="title"]');

  await expect(page).toHaveURL(/\/contracts\/repository\/?(\?.*)?$/);
  await expect(page.getByRole('link', { name: title })).toBeVisible();

  await page.getByRole('link', { name: title }).click();
  await expect(page).toHaveURL(/\/contracts\/\d+\/?$/);
  // Intentional product change: record shell uses dc-ds-workspace--record (not page-wrap/arch-detail-grid).
  await expect(page.locator('.dc-ds-workspace--record').first()).toBeVisible();
  await expect(page.getByText('Contract details').first()).toBeVisible();
  await expect(page.getByText('Contract lifecycle').first()).toBeVisible();
  await expect(page.getByText('View full workflow')).toHaveCount(0);
  // Compact header shows record status · workflow stage (never dual "Draft"/"Drafting").
  await expect(page.getByText('In progress · Drafting').first()).toBeVisible();
  const detailUrl = page.url().replace(/\/$/, '');
  await page.goto(`${detailUrl}/edit/`);
  await expect(page).toHaveURL(/\/contracts\/\d+\/edit\/?$/);

  // Status and lifecycle_stage are governed (not free-edited on the form).
  await page.fill('input[name="counterparty"]', 'E2E Counterparty Updated');
  await submitOwningForm(page, 'input[name="counterparty"]');
  await expect(page).toHaveURL(/\/contracts\/repository\/?(\?.*)?$/);
});

test('critical invoice and time-entry submissions accept valid precision', async ({ page }) => {
  await login(page);

  await page.goto('/contracts/invoices/new/');
  await page.selectOption('select[name="client"]', { index: 1 });
  await page.selectOption('select[name="matter"]', { index: 1 });
  await page.fill('input[name="issue_date"]', '2026-04-12');
  await page.fill('input[name="due_date"]', '2026-05-12');
  await page.fill('input[name="subtotal"]', '1200.00');
  await page.fill('input[name="tax_rate"]', '10.00');
  await page.fill('input[name="payment_terms"]', 'Net 30');
  await submitOwningForm(page, 'input[name="tax_rate"]');
  await expect(page).toHaveURL(/\/contracts\/invoices\/\d+\/?$/);

  await page.goto('/contracts/time/new/');
  await page.selectOption('select[name="matter"]', { index: 1 });
  await page.fill('input[name="date"]', '2026-04-12');
  await page.fill('input[name="hours"]', '2.50');
  await page.fill('textarea[name="description"]', 'E2E time entry');
  await page.selectOption('select[name="activity_type"]', 'REVIEW');
  await page.fill('input[name="rate"]', '250.00');
  await page.check('input[name="is_billable"]');
  await page.locator('form').filter({ has: page.locator('input[name="rate"]') }).evaluate((form) => form.submit());

  await expect(page).toHaveURL(/\/contracts\/time\/?$/);
});

test('critical redesigned workflow path works end-to-end', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const contractTitle = `E2E Workflow Contract ${suffix}`;
  const workflowTitle = `E2E Workflow ${suffix}`;
  const templateName = `E2E Template ${suffix}`;
  const templateStepName = `Template Step ${suffix}`;

  await page.goto('/contracts/new/');
  await page.fill('input[name="title"]', contractTitle);
  await page.selectOption('select[name="contract_type"]', 'MSA');
  await page.fill('input[name="counterparty"]', 'Workflow Counterparty');
  await openPanel(page, 'legal-posture');
  await page.fill('input[name="value"]', '5000');
  await page.selectOption('select[name="currency"]', 'USD');
  await page.fill('input[name="governing_law"]', 'State of Delaware');
  await page.fill('input[name="jurisdiction"]', 'New York');
  await page.selectOption('select[name="risk_level"]', 'LOW');
  await openPanel(page, 'lifecycle-control');
  await page.fill('input[name="start_date"]', '2026-04-12');
  await page.fill('input[name="end_date"]', '2026-12-31');
  await openPanel(page, 'draft-brief');
  await page.fill('textarea[name="content"]', 'Workflow path contract body');
  await submitOwningForm(page, 'input[name="title"]');

  await expect(page).toHaveURL(/\/contracts\/repository\/?(\?.*)?$/);
  await expect(page.getByRole('link', { name: contractTitle })).toBeVisible();

  await page.goto('/contracts/workflows/');
  await expect(page.locator('#workflow-ops-root').first()).toBeVisible();
  await expect(page.getByText(/Active workflows/).first()).toBeVisible();
  const workflowCreateResponse = await page.goto('/contracts/workflows/create/');
  expect(workflowCreateResponse).not.toBeNull();
  expect(workflowCreateResponse.status()).toBeLessThan(400);

  await expect(page.locator('.workspace-main.hero-shell').first()).toBeVisible();
  await page.fill('input[name="title"]', workflowTitle);
  await selectOptionContainingText(page, 'select[name="contract"]', contractTitle);
  await submitOwningForm(page, 'input[name="title"]');

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.locator('.workspace-main.hero-shell').first()).toBeVisible();
  await expect(page.getByText(/Workflow Steps & Ownership/).first()).toBeVisible();

  await page.goto('/contracts/workflows/templates/');
  await expect(page.locator('.workflow-templates-page').first()).toBeVisible();
  await expect(page.getByText(/Templates/).first()).toBeVisible();
  const templateCreateResponse = await page.goto('/contracts/workflows/templates/create/');
  expect(templateCreateResponse).not.toBeNull();
  expect(templateCreateResponse.status()).toBeLessThan(400);

  await expect(page).toHaveURL(/\/contracts\/workflows\/templates\/create\/?$/);
  await expect(page.getByText(/Create template/).first()).toBeVisible();
  await page.fill('input[name="name"]', templateName);
  await page.fill('textarea[name="description"]', 'Automated template for redesigned path test');
  await page.selectOption('select[name="category"]', { index: 1 });
  await submitOwningForm(page, 'input[name="name"]');

  await expect(page).toHaveURL(/\/contracts\/workflows\/templates\/\d+\/?$/);
  await expect(page.locator('.workspace-main.hero-shell').first()).toBeVisible();
  await expect(page.getByText(/Version History/).first()).toBeVisible();

  await page.fill('input[name="name"]', templateStepName);
  await page.fill('textarea[name="description"]', 'Step created by e2e redesigned workflow path test');
  await page.selectOption('select[name="step_kind"]', { index: 1 });
  await page.fill('input[name="order"]', '1');
  await submitOwningForm(page, 'input[name="name"]');

  await expect(page.getByText(templateStepName).first()).toBeVisible();
});
