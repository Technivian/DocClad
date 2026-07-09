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

test('New DPA Draft cockpit: fill, toggle smart questions, generate governed draft', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const counterparty = `E2E DPA Counterparty ${suffix}`;

  // 1. Open the cockpit.
  await page.goto('/contracts/new/dpa/');
  await expect(page.getByRole('heading', { name: 'New DPA Draft' })).toBeVisible();
  await expect(page.getByText('AI Smart Questions')).toBeVisible();

  // 3 of the 12 required fields are yes/no toggles, which always count as
  // "answered" (checked or not) — so the empty form starts at 25%, not 0%.
  const progressPct = page.locator('#dpa-progress-pct');
  await expect(progressPct).toHaveText('25%');

  // 2. Fill required fields.
  await page.fill('[data-field-key="counterparty"]', counterparty);
  await page.fill('[data-field-key="start_date"]', '2026-09-01');
  await page.fill('[data-field-key="contract_owner"]', 'Avery Brooks');
  await page.fill('[data-field-key="processing_purpose"]', 'Hosted logistics analytics.');
  await page.fill('[data-field-key="personal_data_categories"]', 'Business contact details.');
  await page.fill('[data-field-key="data_subjects"]', 'Customer administrators.');
  await page.fill('[data-field-key="governing_law"]', 'State of Delaware');
  await page.selectOption('[data-field-key="transfer_mechanism"]', 'SCC');
  await page.fill('[data-field-key="breach_notification_hours"]', '48');

  // Live draft should reflect the counterparty name as soon as it's typed.
  await expect(page.locator('#dpa-draft-doc')).toContainText(counterparty);

  // 3. Toggle the AI Smart Questions.
  await page.check('[data-field-key="personal_data_involved"]');
  await page.check('[data-field-key="cross_border_transfer"]');
  await page.check('[data-field-key="subprocessors_used"]');

  // Required fields now complete (all remaining requireds are booleans, always "answered").
  await expect(progressPct).toHaveText('100%');
  await expect(page.locator('#dpa-progress-copy')).toContainText('ready to generate');

  // 4. Risk cards update live.
  const riskList = page.locator('#dpa-risk-signal-list');
  await expect(riskList).toContainText('SCC / international transfer risk');
  await expect(riskList).toContainText('Subprocessor review signal');

  // 5. Approval route updates live, with a DPO reason.
  await expect(page.locator('#dpa-gov-approval-route')).toContainText('DPO');
  await expect(page.locator('#dpa-gov-approval-reasons')).toContainText('DPO required');

  // 6. Draft placeholders reflect the field values (no more red "missing" tokens for filled fields).
  await expect(page.locator('#dpa-draft-doc')).toContainText('Hosted logistics analytics.');
  await expect(page.locator('#dpa-draft-doc')).toContainText('State of Delaware');

  // Clicking a risk signal jumps to and highlights the matching draft clause.
  await page.locator('[data-clause-link="international-transfers"]').first().click();
  await expect(page.locator('#international-transfers')).toHaveClass(/is-linked/);

  // 7. Generate the governed draft.
  await page.click('#submit-dpa-btn');

  // 8. Redirect lands on the DPA Contract Workspace.
  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Workflow Timeline')).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
});
