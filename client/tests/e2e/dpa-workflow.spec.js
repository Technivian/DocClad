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

async function expectNoHorizontalPageOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
}

async function fillField(page, key, value) {
  await page.locator(`[data-field-key="${key}"]`).fill(value);
}

async function continueStep(page) {
  await page.getByRole('button', { name: /^(Continue|Review and generate)$/ }).click();
}

test('DPA four-step builder validates, generates, and opens the contract record', async ({ page }) => {
  test.slow();
  await login(page);

  const suffix = Date.now().toString().slice(-6);
  const counterparty = `E2E DPA Counterparty ${suffix}`;

  await page.goto('/contracts/new/dpa/');
  await expect(page.getByRole('heading', { name: /^New DPA\b/ })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'DPA intake steps' })).toBeVisible();
  await expect(page.getByText('Step 1 of 4')).toBeVisible();

  // Validation: empty continue stays on step 1 with a required-field error.
  await continueStep(page);
  await expect(page).toHaveURL(/\/contracts\/new\/dpa\/?$/);
  await expect(page.locator('.dpa-field-error').first()).toBeVisible();

  await fillField(page, 'counterparty', counterparty);
  await fillField(page, 'contract_owner', 'Avery Brooks');
  await fillField(page, 'start_date', '2026-09-01');
  await continueStep(page);
  await expect(page).toHaveURL(/step=2/);
  await expect(page.getByText('Step 2 of 4')).toBeVisible();

  await fillField(page, 'processing_purpose', 'Hosted logistics analytics and support.');
  await continueStep(page);
  await expect(page).toHaveURL(/step=3/);
  await expect(page.getByText('Step 3 of 4')).toBeVisible();

  await page.locator('details.dpa-option-picker', { hasText: 'Choose data categories' }).locator('summary').click();
  await page.locator('label.dpa-option-picker-option', { hasText: 'Identity and contact details' }).click();
  await page.locator('details.dpa-option-picker', { hasText: 'Choose data categories' }).locator('summary').click();
  await page.locator('details.dpa-option-picker', { hasText: 'Choose data subjects' }).locator('summary').click();
  await page.locator('label.dpa-option-picker-option').filter({ hasText: /^Employees$/ }).click();
  await page.locator('details.dpa-option-picker', { hasText: 'Choose data subjects' }).locator('summary').click();
  await page.locator('input[name="step3_sensitive_data"][value="no"]').check();
  await page.locator('input[name="step3_subprocessors"][value="no"]').check();
  await page.locator('[data-multiselect-search]').fill('Netherlands');
  await page.locator('.dpa-multiselect-option', { hasText: 'Netherlands' }).click();
  await page.locator('[data-multiselect-search]').focus();
  await page.keyboard.press('Escape');
  await expect(page.locator('[data-multiselect-menu]')).toBeHidden();
  await continueStep(page);
  await expect(page).toHaveURL(/step=4/);
  await expect(page.getByText('Step 4 of 4')).toBeVisible();

  for (const name of [
    'step4_security_measures_provided',
    'step4_security_assurance_available',
    'step4_encryption_confirmed',
    'step4_access_controls_mfa_confirmed',
  ]) {
    await page.locator(`input[name="${name}"][value="yes"]`).check();
  }
  await page.fill('#step4-privacy-name', 'Jordan Lee');
  await page.fill('#step4-privacy-role', 'Privacy Officer');
  await page.fill('#step4-privacy-email', `privacy.${suffix}@example.com`);
  await page.locator('input[name="step4_breach_notification_commitment"][value="approved_standard"]').check();
  await page.locator('input[name="step4_governing_law_mode"][value="manual"]').check();
  await page.selectOption('#step4-governing-law', 'State of Delaware');
  for (const key of ['audit_rights', 'deletion_return', 'dpa_liability']) {
    await page.locator(`input[name="step4_${key}_position"][value="accepted"]`).check();
  }
  await page.getByRole('button', { name: 'Review and generate' }).click();

  await expect(page).toHaveURL(/\/contracts\/new\/dpa\/review\/?$/);
  await expect(page.getByRole('heading', { name: /Review and generate DPA/i })).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
  await expect(page.getByText('Governance results')).toBeVisible();
  await page.getByRole('button', { name: 'Generate DPA' }).click();

  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+\/?$/);
  await expect(page.getByText('Lifecycle')).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
  await expect(page.getByText('Guided drafting').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Resolve \d+ exceptions?/ })).toBeVisible();
  await expect(page.getByText('Send to Legal Review · blocked')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export Word' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Generate DPA review memo' })).toHaveCount(0);

  await page.getByRole('button', { name: /Resolve \d+ exceptions?|open exception/i }).first().click();
  const exceptionDrawer = page.getByRole('dialog', { name: 'Resolve exception' });
  await expect(exceptionDrawer.getByRole('link', { name: 'Open clause' })).toBeVisible();
  await exceptionDrawer.getByRole('button', { name: 'Close exception resolution' }).click();

  await page.locator('details.dc-ds-workspace__actions-menu summary').click();
  await page.getByRole('menuitem', { name: 'View contract record' }).click();
  await expect(page).toHaveURL(/\/contracts\/\d+\/?$/);
  await page.reload();
  await expect(page.getByText(counterparty).first()).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/contracts\/workflows\/\d+/);
  await page.locator('details.dc-ds-workspace__actions-menu summary').click();
  await expect(page.getByRole('menuitem', { name: 'View contract record' })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.dc-ds-workspace')).toBeVisible();
  await expectNoHorizontalPageOverflow(page);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('details.dc-ds-workspace__actions-menu summary').click();
  const recordLink = page.getByRole('menuitem', { name: 'View contract record' });
  await recordLink.focus();
  await expect(recordLink).toBeFocused();
  await recordLink.click();
  await expect(page).toHaveURL(/\/contracts\/\d+\/?$/);
  await expect(page.locator('.dc-ds-workspace--record')).toBeVisible();
  await expect(page.getByText(counterparty).first()).toBeVisible();
});
