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

  test('repository rows retain compact, centered, and interactive table behavior', async ({ page }) => {
    await page.goto('/contracts/repository/');
    const firstRow = page.locator('.contract-row').first();
    await expect(firstRow).toBeVisible();

    const firstRowCellLayout = await firstRow.locator('td').evaluateAll((cells) => (
      cells
        .filter((cell) => getComputedStyle(cell).display !== 'none')
        .map((cell) => ({
          top: cell.getBoundingClientRect().top,
          display: getComputedStyle(cell).display,
          verticalAlign: getComputedStyle(cell).verticalAlign,
          paddingTop: getComputedStyle(cell).paddingTop,
          paddingBottom: getComputedStyle(cell).paddingBottom,
        }))
    ));
    expect(firstRowCellLayout.every((cell) => cell.display === 'table-cell')).toBeTruthy();
    expect(firstRowCellLayout.every((cell) => cell.verticalAlign === 'middle')).toBeTruthy();
    expect(firstRowCellLayout.every((cell) => cell.paddingTop === '8px' && cell.paddingBottom === '8px')).toBeTruthy();
    expect(Math.max(...firstRowCellLayout.map((cell) => cell.top)) - Math.min(...firstRowCellLayout.map((cell) => cell.top))).toBeLessThanOrEqual(1);
    expect((await firstRow.boundingBox()).height).toBeLessThanOrEqual(64);

    await expect(firstRow).toHaveAttribute('tabindex', '0');
    expect(await firstRow.evaluate((row) => getComputedStyle(row).cursor)).toBe('pointer');
    expect((await firstRow.locator('td[data-col="select"]').boundingBox()).width).toBeLessThanOrEqual(40);
    const statusDot = firstRow.locator('.repo-status-dot');
    await expect(statusDot).toBeVisible();
    await expect(statusDot).toHaveAttribute('title', /^Status: /);
    await expect(firstRow.locator('.repo-title-meta')).toHaveCount(0);
    const firstDataCell = firstRow.locator('td[data-col="type"]');
    const restingBackground = await firstDataCell.evaluate((cell) => getComputedStyle(cell).backgroundColor);
    await firstRow.hover();
    await page.waitForTimeout(200);
    const hoverBackground = await firstDataCell.evaluate((cell) => getComputedStyle(cell).backgroundColor);
    expect(hoverBackground).not.toBe(restingBackground);

    await firstRow.focus();
    await expect(firstRow).toBeFocused();
  });

  test('my work rows keep compact priority and action layouts', async ({ page }) => {
    await page.goto('/contracts/my-work/');
    const rows = page.locator('#my-work-active-body .my-work-row');
    expect(await rows.count()).toBeGreaterThan(0);
    const firstRow = rows.first();
    await expect(firstRow).toBeVisible();

    expect((await firstRow.boundingBox()).height).toBeLessThanOrEqual(64);
    await expect(firstRow.locator('.my-work-row-actions')).toBeVisible();
    await expect(firstRow.locator('.gov-priority__detail')).toHaveCount(0);

    const actionLayout = await firstRow.locator('.my-work-row-actions').evaluate((cluster) => {
      const visibleControls = Array.from(cluster.children).filter((element) => getComputedStyle(element).display !== 'none');
      return {
        display: getComputedStyle(cluster).display,
        flexWrap: getComputedStyle(cluster).flexWrap,
        topDelta: Math.max(...visibleControls.map((element) => element.getBoundingClientRect().top))
          - Math.min(...visibleControls.map((element) => element.getBoundingClientRect().top)),
      };
    });
    expect(actionLayout.display).toBe('flex');
    expect(actionLayout.flexWrap).toBe('nowrap');
    expect(actionLayout.topDelta).toBeLessThanOrEqual(4);
  });

  test('my work filter groups remain inline with grey quick-view count badges', async ({ page }) => {
    await page.goto('/contracts/my-work/');
    await page.getByRole('button', { name: 'Active work' }).click();
    const summary = page.locator('.my-work-inline-summary');
    const chips = summary.locator('.my-work-summary-chip');
    await expect(summary).toBeAttached();
    expect(await chips.count()).toBeGreaterThan(1);
    const firstSummaryChip = chips.first();
    const secondSummaryChip = chips.nth(1);
    expect((await firstSummaryChip.locator('.my-work-summary-chip__label').textContent()).trim()).not.toBe('');
    expect((await secondSummaryChip.locator('.my-work-summary-chip__label').textContent()).trim()).not.toBe('');
    expect((await firstSummaryChip.locator('.my-work-summary-chip__count').textContent()).trim()).toMatch(/^\d+$/);
    expect((await secondSummaryChip.locator('.my-work-summary-chip__count').textContent()).trim()).toMatch(/^\d+$/);
    await expect(firstSummaryChip.locator('.my-work-summary-chip__count')).toBeVisible();
    await expect(secondSummaryChip.locator('.my-work-summary-chip__count')).toBeVisible();

    const summaryLayout = await summary.evaluate((element) => ({
      display: getComputedStyle(element).display,
      gap: getComputedStyle(element).gap,
      precedingGroupSeparator: getComputedStyle(element, '::before').content,
      followingGroupSeparator: getComputedStyle(element.nextElementSibling, '::before').content,
    }));
    expect(summaryLayout.display).toBe('flex');
    expect(summaryLayout.gap).not.toBe('normal');
    expect(summaryLayout.precedingGroupSeparator).toBe('"|"');
    expect(summaryLayout.followingGroupSeparator).toBe('"|"');
    await expect(page.getByRole('link', { name: 'My queue' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Recently completed' })).toBeVisible();

    const toolbarActions = page.locator('.my-work-toolbar-actions');
    await expect(toolbarActions).toBeVisible();
    await expect(toolbarActions.getByRole('button', { name: 'Refresh work queue' })).toBeVisible();
    const [workStateBox, toolbarActionsBox] = await Promise.all([
      page.locator('.my-work-view-mode-tabs').boundingBox(),
      toolbarActions.boundingBox(),
    ]);
    expect(toolbarActionsBox.x).toBeGreaterThan(workStateBox.x + workStateBox.width);
  });

  test('operational tables render the canonical hierarchy and selection exceptions', async ({ page }) => {
    await page.goto('/contracts/repository/');
    await expect(page.locator('#contracts-table')).toBeVisible();
    await expect(page.locator('#select-all')).toBeVisible();
    await expect(page.locator('#repo-bulk-status')).toBeAttached();
    await expect(page.locator('#repo-bulk-export')).toBeAttached();
    await expect(page.locator('.repo-view-tabs a')).toHaveText([
      'All contracts', 'Active', 'Expiring', 'Completed', 'Archived',
    ]);
    await expect(page.locator('#contracts-table thead th')).toHaveText([
      '', 'Contract', 'Type', 'Counterparty', 'Stage', 'Status', 'Owner', 'Next key date', 'Latest activity', 'Value', 'Actions',
    ]);

    await page.goto('/contracts/my-work/');
    await expect(page.locator('#my-work-table')).toBeVisible();
    await expect(page.locator('#my-work-table thead th')).toHaveText([
      'Priority', 'Work item', 'Contract', 'Counterparty', 'Type', 'Status', 'Assigned on', 'Due', 'Action',
    ]);
    await expect(page.locator('#my-work-table input[type="checkbox"]')).toHaveCount(0);

    await page.goto('/contracts/risks/');
    await expect(page.locator('#legal-hub-table')).toBeVisible();
    await expect(page.locator('#legal-hub-table thead th')).toHaveText([
      'Severity', 'Signal', 'Source', 'Matter/Client', 'Status', 'Owner', 'Due/Age', 'Actions',
    ]);
    await expect(page.locator('#legal-hub-table input[type="checkbox"]')).toHaveCount(0);
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
    const table = page.locator('.dc-ds-table[data-table-core="server"]');
    await expect(table.locator('caption')).toContainText('Clause library records');
    const emptyState = page.locator('.dc-ds-empty').first();
    if (await emptyState.count()) {
      await expect(emptyState).toBeVisible();
    } else {
      await expect(table.locator('tbody tr').first()).toBeVisible();
    }
    await expect(page).toHaveScreenshot('phase-3a-clause-library-empty.png', { fullPage: true, animations: 'disabled' });
  });
});
