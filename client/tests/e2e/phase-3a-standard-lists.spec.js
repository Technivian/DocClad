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

test.describe('Phase 3A standard lists and tables', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await login(page);
  });

  test('repository retains selection, async states, pagination, and mobile overflow', async ({ page }) => {
    await page.goto('/contracts/repository/');
    const table = page.locator('#contracts-table');
    await expect(table).toHaveClass(/dc-ds-table/);
    await expect(page.locator('.repo-filter-shell')).toHaveClass(/dc-ds-filterbar/);
    await expect(page.locator('.contract-row').first()).toBeVisible();

    const selectAll = page.locator('#select-all');
    await selectAll.focus();
    await page.keyboard.press('Space');
    await expect(page.locator('#selected-count')).toContainText('selected');
    await expect(page.locator('.contract-row[aria-selected="true"]').first()).toBeVisible();

    await page.evaluate(() => window.clmoneRepository.showLoading());
    await expect(table).toHaveAttribute('aria-busy', 'true');
    await expect(page.locator('.dc-ds-table-state[role="status"]')).toBeVisible();

    await page.evaluate(() => window.clmoneRepository.showError('Test transport failure'));
    await expect(page.locator('.repo-empty-state')).toContainText('could not be loaded');
    // The toast is intentionally transient. The durable recovery panel above
    // is the visual contract being captured, so exclude the toast timer from
    // this table-state baseline after it has been exercised.
    await page.locator('#clmone-toast-region .dc-toast').evaluateAll((toasts) => toasts.forEach((toast) => toast.remove()));
    await expect(page).toHaveScreenshot('phase-3a-repository-error.png', { fullPage: true, animations: 'disabled' });

    await page.evaluate(() => window.clmoneRepository.updatePagination({ page: 2, total_pages: 3, total_count: 60 }));
    const previousPage = page.locator('#repo-page-prev');
    await previousPage.focus();
    await expect(previousPage).toBeFocused();
    await expect(previousPage).toBeEnabled();
    await expect(page.locator('#repo-page-next')).toBeEnabled();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    const wrap = page.locator('.dc-ds-table-wrap').first();
    await expect(wrap).toBeVisible();
    expect(await wrap.evaluate((element) => element.scrollWidth > element.clientWidth)).toBeTruthy();
  });

  test('document and approval-admin list families retain canonical semantics and keyboard tabs', async ({ page }) => {
    await page.goto('/contracts/documents/');
    await expect(page.locator('.dc-ds-filterbar')).toHaveAttribute('aria-label', 'Filter documents');
    await expect(page.locator('.dc-ds-table caption')).toContainText('Document records');
    await expect(page.locator('#document-search')).toBeVisible();
    await expect(page.locator('.dc-ds-table .dc-ds-empty')).toBeVisible();
    await expect(page).toHaveScreenshot('phase-3a-document-empty.png', { fullPage: true, animations: 'disabled' });

    await page.goto('/contracts/approvals/');
    const firstTab = page.locator('[data-queue-tab]').first();
    await firstTab.focus();
    await expect(firstTab).toBeFocused();
    await expect(page.locator('.approvals-queue-body')).toHaveClass(/dc-ds-table-wrap/);
    await expect(page.locator('.approvals-queue-body .dc-ds-table caption').first()).toContainText('Approval requests');
    await expect(page).toHaveScreenshot('phase-3a-approval-admin.png', { fullPage: true, animations: 'disabled' });
  });

  test('clause-library administration retains its canonical empty table', async ({ page }) => {
    await page.goto('/contracts/clause-library/');
    await expect(page.locator('.dc-ds-table caption')).toContainText('Clause library records');
    await expect(page.locator('.dc-ds-table .dc-ds-empty')).toBeVisible();
    await expect(page).toHaveScreenshot('phase-3a-clause-library-empty.png', { fullPage: true, animations: 'disabled' });
  });
});
